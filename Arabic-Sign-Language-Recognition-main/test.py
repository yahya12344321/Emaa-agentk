import cv2
import numpy as np
import mediapipe as mp
from tensorflow.keras.models import load_model
from sklearn.preprocessing import LabelEncoder
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display



encoder = LabelEncoder()
encoder.classes_ = np.load('classes.npy', allow_pickle=True)


letters_mapping = {
    "Ain": "ع", "Al": "ال", "Alef": "أ", "Beh": "ب", "Dad": "ض", "Dal": "د",
    "Feh": "ف", "Ghain": "غ", "Hah": "ح", "Heh": "ه", "Jeem": "ج", "Kaf": "ك",
    "Khah": "خ", "Laa": "لا", "Lam": "ل", "Meem": "م", "Noon": "ن", "Qaf": "ق",
    "Reh": "ر", "Sad": "ص", "Seen": "س", "Sheen": "ش", "Tah": "ط", "Teh": "ت",
    "Teh_Marbuta": "ة", "Theh": "ث", "Waw": "و", "Yeh": "ي", "Zah": "ظ",
    "Zain": "ز", "thal": "ذ"
}


model = load_model('sign_language_model.h5')

def put_arabic_text(image, text, position, font_path="arial.ttf", font_size=32, color=(0, 255, 0)):
    
    
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)

    
    font = ImageFont.truetype(font_path, font_size)

   
    image_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image_pil)
    draw.text(position, bidi_text, font=font, fill=color)

    return cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)



mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)
mp_draw = mp.solutions.drawing_utils


cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    
    frame = cv2.flip(frame, 1)


    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    
    results = hands.process(rgb_frame)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            
            landmarks = []
            for landmark in hand_landmarks.landmark:
                landmarks.extend([landmark.x, landmark.y, landmark.z])

            
            X_input = np.array(landmarks).reshape(1, -1)

            
            predictions = model.predict(X_input)
            predicted_index = np.argmax(predictions)  
            predicted_letter = encoder.inverse_transform([predicted_index])[0]  
            predicted_letter_arabic = letters_mapping.get(predicted_letter, predicted_letter)  

            
            frame = put_arabic_text(frame, f'التوقع: {predicted_letter_arabic}', (50, 50))


           
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

    
    cv2.imshow("التعرف على لغة الإشارة", frame)

    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break


cap.release()
cv2.destroyAllWindows()
