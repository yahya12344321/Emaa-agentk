from __future__ import annotations

import base64
import binascii
import mimetypes
import os
import re
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/octet-stream", ".task")

try:
    from keras.models import load_model
except ImportError:  # pragma: no cover
    from tensorflow.keras.models import load_model


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models_h5" / "model_norm_15class.h5"
POSE_POINTS = 33
HAND_POINTS = 21
FEATURE_VECTOR_LENGTH = (POSE_POINTS + HAND_POINTS * 2) * 2
SEQUENCE_LENGTH = 20
MIN_CONFIDENCE = 0.45
MIN_MARGIN = 0.08
PREDICTION_STREAK = 2
MAX_FRAME_WIDTH = 480
MAX_IMAGE_PAYLOAD_CHARS = 900_000
EMIT_COOLDOWN_SECONDS = 1.0
SEQUENCE_OVERLAP_FRAMES = 8
MISS_RESET_FRAMES = 3
MIN_HAND_SPAN_RATIO = 0.11
PROBABILITY_EMA_ALPHA = 0.35
SESSION_TTL_SECONDS = 180
SESSION_CLEANUP_INTERVAL_SECONDS = 30

ACTIONS = [
    "club",
    "father",
    "fine",
    "help",
    "hospital",
    "howareyou",
    "learn",
    "love",
    "mother",
    "need",
    "school",
    "sorry",
    "thanks",
    "whatisyourname",
    "where",
]

TRANSLATOR = {
    "howareyou": "كيف حالك؟",
    "fine": "جيد",
    "hospital": "مستشفى",
    "school": "مدرسة",
    "thanks": "شكرًا",
    "sorry": "آسف",
    "help": "مساعدة",
    "where": "أين",
    "learn": "يتعلم",
    "club": "نادي",
    "father": "أب",
    "mother": "أم",
    "love": "أحبك",
    "whatisyourname": "ما اسمك؟",
    "need": "أحتاج",
}

CLIENT_ID_PATTERN = re.compile(r"[^a-zA-Z0-9_-]+")


class FrameData(BaseModel):
    image_b64: str
    client_id: str | None = None


@dataclass
class RecognitionSession:
    holistic: object
    window: deque[np.ndarray] = field(default_factory=lambda: deque(maxlen=SEQUENCE_LENGTH))
    candidate_label: str | None = None
    candidate_streak: int = 0
    last_emitted_label: str | None = None
    cooldown_until: float = 0.0
    missed_frames: int = 0
    smoothed_probabilities: np.ndarray | None = None
    updated_at: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def clear_sequence(self, *, reset_probabilities: bool = False, keep_recent_frames: int = 0) -> None:
        preserved_frames: list[np.ndarray] = []
        if keep_recent_frames > 0 and self.window:
            preserved_frames = list(self.window)[-keep_recent_frames:]

        self.window.clear()
        if preserved_frames:
            self.window.extend(preserved_frames)
        self.candidate_label = None
        self.candidate_streak = 0
        if reset_probabilities:
            self.smoothed_probabilities = None

    def touch(self) -> None:
        self.updated_at = time.monotonic()

    def close(self) -> None:
        self.holistic.close()


@dataclass
class RuntimeResources:
    model: object
    sessions: dict[str, RecognitionSession] = field(default_factory=dict)
    sessions_lock: threading.Lock = field(default_factory=threading.Lock)
    model_lock: threading.Lock = field(default_factory=threading.Lock)
    last_cleanup_at: float = 0.0


def build_holistic():
    return mp.solutions.holistic.Holistic(
        static_image_mode=False,
        model_complexity=0,
        smooth_landmarks=True,
        enable_segmentation=False,
        refine_face_landmarks=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


def normalize_client_id(client_id: str | None) -> str:
    if not client_id:
        return "default"
    normalized = CLIENT_ID_PATTERN.sub("", client_id)[:64]
    return normalized or "default"


def cleanup_expired_sessions(resources: RuntimeResources, *, force: bool = False) -> None:
    now = time.monotonic()
    if not force and now - resources.last_cleanup_at < SESSION_CLEANUP_INTERVAL_SECONDS:
        return

    expired_sessions: list[RecognitionSession] = []
    with resources.sessions_lock:
        resources.last_cleanup_at = now
        for client_id, session in list(resources.sessions.items()):
            if now - session.updated_at > SESSION_TTL_SECONDS:
                expired_sessions.append(resources.sessions.pop(client_id))

    for session in expired_sessions:
        session.close()


def get_or_create_session(resources: RuntimeResources, client_id: str) -> RecognitionSession:
    cleanup_expired_sessions(resources)

    with resources.sessions_lock:
        session = resources.sessions.get(client_id)
        if session is None:
            session = RecognitionSession(holistic=build_holistic())
            resources.sessions[client_id] = session
        return session


def decode_frame(image_b64: str) -> np.ndarray:
    encoded_data = image_b64.split(",", 1)[1] if "," in image_b64 else image_b64
    if len(encoded_data) > MAX_IMAGE_PAYLOAD_CHARS:
        raise HTTPException(status_code=413, detail="Image payload is too large.")

    try:
        raw = base64.b64decode(encoded_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload.") from exc

    frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Unable to decode image payload.")

    height, width = frame.shape[:2]
    if width > MAX_FRAME_WIDTH:
        scale = MAX_FRAME_WIDTH / width
        frame = cv2.resize(
            frame,
            (MAX_FRAME_WIDTH, max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    return frame


def extract_landmarks(landmarks, width: int, height: int, expected_points: int) -> np.ndarray:
    points = np.zeros((expected_points, 2), dtype=np.float32)
    if not landmarks:
        return points

    for index, point in enumerate(landmarks.landmark):
        if index >= expected_points:
            break
        points[index, 0] = np.clip(point.x, 0.0, 0.999999) * width
        points[index, 1] = np.clip(point.y, 0.0, 0.999999) * height

    return points


def extract_keypoints(frame: np.ndarray, results) -> np.ndarray:
    height, width = frame.shape[:2]
    pose = extract_landmarks(results.pose_landmarks, width, height, 33)
    left_hand = extract_landmarks(results.left_hand_landmarks, width, height, 21)
    right_hand = extract_landmarks(results.right_hand_landmarks, width, height, 21)
    return np.vstack((pose, left_hand, right_hand))


def pre_process_keypoints(keypoints: np.ndarray) -> np.ndarray:
    normalized = keypoints.astype(np.float32, copy=True)
    normalized -= normalized[0]
    flattened = normalized.reshape(-1)
    scale = float(np.max(np.abs(flattened)))
    if scale == 0:
        scale = 1.0
    return flattened / scale


def warmup_model(model) -> None:
    try:
        input_shape = getattr(model, "input_shape", None) or (None, SEQUENCE_LENGTH, FEATURE_VECTOR_LENGTH)
        sequence_length = int(input_shape[1] or SEQUENCE_LENGTH)
        feature_size = int(input_shape[2] or FEATURE_VECTOR_LENGTH)
        sample = np.zeros((1, sequence_length, feature_size), dtype=np.float32)
        if hasattr(model, "predict_on_batch"):
            model.predict_on_batch(sample)
        else:
            model.predict(sample, verbose=0)
        print(f"Model warm-up completed with shape (1, {sequence_length}, {feature_size})")
    except Exception as exc:  # pragma: no cover
        print(f"Model warm-up skipped: {exc}")


def compute_hand_span_ratio(results) -> float:
    best_span = 0.0
    for hand_landmarks in (results.left_hand_landmarks, results.right_hand_landmarks):
        if not hand_landmarks:
            continue
        xs = [point.x for point in hand_landmarks.landmark]
        ys = [point.y for point in hand_landmarks.landmark]
        best_span = max(best_span, max(max(xs) - min(xs), max(ys) - min(ys)))
    return best_span


def update_candidate(state: RecognitionSession, label: str) -> None:
    if state.candidate_label == label:
        state.candidate_streak += 1
    else:
        state.candidate_label = label
        state.candidate_streak = 1


def reset_for_missed_frame(state: RecognitionSession) -> None:
    state.missed_frames += 1
    if state.missed_frames >= MISS_RESET_FRAMES:
        state.clear_sequence(reset_probabilities=True)


def smooth_probabilities(state: RecognitionSession, probabilities: np.ndarray) -> np.ndarray:
    current = probabilities.astype(np.float32)
    if state.smoothed_probabilities is None or state.smoothed_probabilities.shape != current.shape:
        state.smoothed_probabilities = current
    else:
        state.smoothed_probabilities = (
            state.smoothed_probabilities * (1.0 - PROBABILITY_EMA_ALPHA) +
            current * PROBABILITY_EMA_ALPHA
        )

    total = float(np.sum(state.smoothed_probabilities))
    if total <= 0:
        return current
    return state.smoothed_probabilities / total


def predict_probabilities(resources: RuntimeResources, sequence: np.ndarray) -> np.ndarray:
    with resources.model_lock:
        if hasattr(resources.model, "predict_on_batch"):
            return resources.model.predict_on_batch(sequence)[0]
        return resources.model.predict(sequence, verbose=0)[0]


def predict_word(session: RecognitionSession, resources: RuntimeResources, frame: np.ndarray) -> dict[str, float | str] | None:
    session.touch()

    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image.flags.writeable = False
    results = session.holistic.process(image)

    if not any((results.left_hand_landmarks, results.right_hand_landmarks, results.pose_landmarks)):
        reset_for_missed_frame(session)
        return None

    if compute_hand_span_ratio(results) < MIN_HAND_SPAN_RATIO:
        reset_for_missed_frame(session)
        return None

    session.missed_frames = 0
    session.window.append(pre_process_keypoints(extract_keypoints(frame, results)))

    if len(session.window) < SEQUENCE_LENGTH:
        return None

    sequence = np.expand_dims(np.asarray(session.window, dtype=np.float32), axis=0)
    probabilities = predict_probabilities(resources, sequence)
    smoothed_probabilities = smooth_probabilities(session, probabilities)
    if smoothed_probabilities.size > 1:
        top_indices = np.argpartition(smoothed_probabilities, -2)[-2:]
        top_indices = top_indices[np.argsort(smoothed_probabilities[top_indices])][::-1]
    else:
        top_indices = np.array([0])
    best_index = int(top_indices[0])
    second_index = int(top_indices[1]) if len(top_indices) > 1 else best_index

    confidence = float(smoothed_probabilities[best_index])
    margin = float(confidence - smoothed_probabilities[second_index])
    predicted_action = ACTIONS[best_index]

    if confidence < MIN_CONFIDENCE or margin < MIN_MARGIN:
        session.candidate_label = None
        session.candidate_streak = 0
        return None

    update_candidate(session, predicted_action)
    if session.candidate_streak < PREDICTION_STREAK:
        return None

    now = time.monotonic()
    if predicted_action == session.last_emitted_label and now < session.cooldown_until:
        return None

    session.last_emitted_label = predicted_action
    session.cooldown_until = now + EMIT_COOLDOWN_SECONDS
    session.clear_sequence(
        reset_probabilities=True,
        keep_recent_frames=min(SEQUENCE_OVERLAP_FRAMES, SEQUENCE_LENGTH - 1),
    )

    return {
        "word": TRANSLATOR.get(predicted_action, predicted_action),
        "confidence": round(confidence, 4),
        "label": predicted_action,
        "margin": round(margin, 4),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading EMAA sequence model...")
    if not MODEL_PATH.exists():
        raise RuntimeError(f"Model file was not found: {MODEL_PATH}")
    model = load_model(MODEL_PATH)
    warmup_model(model)
    app.state.resources = RuntimeResources(model=model)
    print(f"Model loaded successfully from {MODEL_PATH}")

    try:
        yield
    finally:
        resources: RuntimeResources = app.state.resources
        cleanup_expired_sessions(resources, force=True)
        with resources.sessions_lock:
            remaining_sessions = list(resources.sessions.values())
            resources.sessions.clear()
        for session in remaining_sessions:
            session.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str | bool | int]:
    resources: RuntimeResources = app.state.resources
    cleanup_expired_sessions(resources)
    with resources.sessions_lock:
        active_sessions = len(resources.sessions)
    return {
        "status": "ok",
        "modelLoaded": hasattr(app.state, "resources"),
        "modelPath": str(MODEL_PATH.name),
        "activeSessions": active_sessions,
    }


@app.post("/predict/frame")
async def predict_frame(data: FrameData):
    resources: RuntimeResources = app.state.resources
    frame = decode_frame(data.image_b64)
    client_id = normalize_client_id(data.client_id)
    session = get_or_create_session(resources, client_id)

    try:
        with session.lock:
            result = predict_word(session, resources, frame)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        print(f"Prediction error: {exc}")
        return {"word": None, "confidence": 0.0, "error": str(exc)}

    return result or {"word": None, "confidence": 0.0}


app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
