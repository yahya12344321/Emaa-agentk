#  Arabic Sign Language Recognition

A deep-learning project for recognizing **Arabic sign language letters**.  
This repository contains data processing, feature extraction using MediaPipe, and a trained deep model that achieves **96% accuracy** on the test set.

---

#  Project Overview

- **Dataset:** >7000 images of Arabic sign language letters captured under various angles and lighting conditions.  
- **Preprocessing:** Images processed with **OpenCV** and **MediaPipe** to extract hand landmark coordinates.  
- **Features:** Extracted 21 hand landmarks (x, y, z) per image and saved them to a CSV file.  
- **Model:** Deep learning model trained on landmark coordinates (not raw images).  
- **Performance:** **96% accuracy** on the test set.


---

# 📂 Repository Structure

Arabic-Sign-Language/
│
├── sign_language_data.csv # CSV with hand landmark features and labels
├── classes.npy # NumPy array containing the list of sign classes (e.g., Arabic letters)
├── sign_language_model.h5 # Trained deep learning model
├── Arabic Sign Language Dataset.ipynb # Notebook for data collection & CSV creation
├── train_model.ipynb # Notebook for training the model
├── test.py # Script for real-time inference/demo
├── requirements.txt # Project dependencies
└── README.md # Project documentation


---

#  How It Works

#  Data Processing
- Each image was passed through **MediaPipe Hands** to extract 21 landmarks.
- Each landmark includes X, Y, Z coordinates, totaling 63 values per sample.
- All features were saved in `sign_language_data.csv`, with the corresponding label.

#  Label Encoding
- All class labels (Arabic letters) were saved in a separate file: `classes.npy`
```python
import numpy as np
classes = np.load("classes.npy")
print(classes)
# Output: ['ا', 'ب', 'ت', ..., 'ي']
```

#   Model
A deep learning model (MLP) was trained on the extracted coordinates.

Achieved 96% accuracy on the validation/test set.

# classes.npy
This file stores the Arabic letters used for classification in the correct order.
It's used to decode predicted class indices into actual letters.

#  Technologies Used
- Python 3.8+

- OpenCV

- MediaPipe

- NumPy / Pandas

- TensorFlow / Keras

- Jupyter Notebook

# Setup & Usage
## 1. Install dependencies

     pip install -r requirements.txt

## 2. Run the real-time demo

     python test.py

## 3. Train the model (optional)

     Open train_model.ipynb and run all cells to retrain the model from scratch.

# Dataset Sample
Each row in sign_language_data.csv:

63 values: x, y, z for 21 hand landmarks

1 label: the corresponding Arabic letter

| x0  | y0  | z0  | ... | x20 | y20 | z20 | label |
| --- | --- | --- | --- | --- | --- | --- | ----- |
| 0.5 | 0.4 | ... | ... | ... | ... | ... | 'س'   |

#  Results

| Metric   | Value             |
| -------- | ----------------- |
| Accuracy | 96%               |
| Classes  | 31 Arabic letters |
| Samples  | > 7,000 images    |

# Contributing
Contributions are welcome!
If you'd like to suggest improvements or extend the model to support full words/phrases, feel free to open an issue or pull request.


# 📬 Contact
📧 Email: mohamedibraham770@gmail.com

💼 LinkedIn: www.linkedin.com/in/mohamed-ibrahim-abdel-aal-8330a1341









