import joblib
import os
import re
from pathlib import Path


class SpamDetector:
    def __init__(self, model_path=None, vectorizer_path=None):
        if model_path is None:
            model_path = 'spam_service/models/spam_model.pkl'
        if vectorizer_path is None:
            vectorizer_path = 'spam_service/models/vectorizer.pkl'

        self.model_path = model_path
        self.vectorizer_path = vectorizer_path
        self.model = None
        self.vectorizer = None
        self.enabled = False
        if os.path.exists(model_path) and os.path.exists(vectorizer_path):
            self._load_model()
        else:
            print("⚠️ Spam detection model not found. Will create during training.")

    def _load_model(self):
        try:
            self.model = joblib.load(self.model_path)
            self.vectorizer = joblib.load(self.vectorizer_path)
            self.enabled = True
            print(" Spam detector loaded successfully")
        except Exception as e:
            print(f" Failed to load spam detector: {e}")
            self.enabled = False

    def predict(self, text):
        if not self.enabled or not text or not text.strip():
            return False, 0.0

        try:
            cleaned = self._clean_text(text)
            text_vectorized = self.vectorizer.transform([cleaned])
            prediction = self.model.predict(text_vectorized)[0]
            probabilities = self.model.predict_proba(text_vectorized)[0]

            confidence = float(max(probabilities))
            is_spam = bool(prediction)

            return is_spam, confidence

        except Exception as e:
            print(f"Prediction error: {e}")
            return False, 0.0

    def keyword_filter(self, text, spam_keywords=None):
        if spam_keywords is None:
            spam_keywords = [
                'free money', 'click here', 'winner', 'congratulations',
                'bitcoin', 'casino', 'viagra', 'earn money', 'lottery',
                'make money', 'fast cash', 'work from home', 'investment',
                'crypto', 'discount', 'offer', 'limited time', 'urgent',
                'prize', 'lottery winner', 'get rich', 'no cost'
            ]

        text_lower = text.lower()
        for keyword in spam_keywords:
            if keyword in text_lower:
                return True, 0.9
        return False, 0.0

    def _clean_text(self, text):
        text = text.lower()
        text = re.sub(r'[^a-zA-Z\s]', '', text)

        text = ' '.join(text.split())

        return text