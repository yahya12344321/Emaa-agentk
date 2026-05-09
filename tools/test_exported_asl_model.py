import csv
import json
import sys
from pathlib import Path

import numpy as np


def relu(values: np.ndarray) -> np.ndarray:
    return np.maximum(values, 0)


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    exponents = np.exp(shifted)
    return exponents / np.sum(exponents)


def predict(model: dict, vector: np.ndarray) -> int:
    activations = vector.astype(np.float32)
    last_index = len(model["layers"]) - 1
    for index, layer in enumerate(model["layers"]):
        kernel = np.array(layer["kernel"], dtype=np.float32)
        bias = np.array(layer["bias"], dtype=np.float32)
        activations = np.matmul(activations, kernel) + bias
        if layer["activation"] == "relu":
            activations = relu(activations)
        elif layer["activation"] == "softmax" or index == last_index:
            activations = softmax(activations)
    return int(np.argmax(activations))


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: test_exported_asl_model.py <model.json> <dataset.csv>")
        return 1

    model = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    dataset_path = Path(sys.argv[2])

    correct = 0
    total = 0
    classes = model["classes"]

    with dataset_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for row in reader:
            label = row[0]
            vector = np.array([float(value) for value in row[1:]], dtype=np.float32)
            prediction = classes[predict(model, vector)]
            correct += int(prediction == label)
            total += 1

    accuracy = correct / total if total else 0.0
    print(json.dumps({"samples": total, "correct": correct, "accuracy": round(accuracy, 6)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
