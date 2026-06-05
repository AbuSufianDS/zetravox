import joblib
import os
import re
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch


class SpamDetector:
    def __init__(self, model_path=None, vectorizer_path=None):
        self.model = None
        self.tokenizer = None
        self.enabled = False
        self.device = torch.device("cpu")
        self._load_transformer_model()

    def _load_transformer_model(self):
        try:
            model_name = "mrm8488/bert-tiny-finetuned-sms-spam-detection"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            self.enabled = True
            print("Transformer spam detector loaded successfully")
        except Exception as e:
            print(f"Transformer model failed: {e}")
            self._load_fallback()

    def _load_fallback(self):
        try:
            model_path = 'spam_service/models/spam_model.pkl'
            vectorizer_path = 'spam_service/models/vectorizer.pkl'
            if os.path.exists(model_path) and os.path.exists(vectorizer_path):
                self.model = joblib.load(model_path)
                self.vectorizer = joblib.load(vectorizer_path)
                self.enabled = True
                print("Fallback spam detector loaded")
        except Exception as e:
            print(f"No spam detector available: {e}")
            self.enabled = False

    def predict(self, text):
        if not self.enabled or not text or not text.strip():
            return False, 0.0

        try:
            if hasattr(self, 'tokenizer') and self.tokenizer:
                return self._predict_transformer(text)
            else:
                return self._predict_fallback(text)
        except Exception as e:
            print(f"Prediction error: {e}")
            return False, 0.0

    def _predict_transformer(self, text):
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        spam_prob = probs[0][1].item()
        is_spam = spam_prob > 0.5
        return is_spam, spam_prob

    def _predict_fallback(self, text):
        cleaned = re.sub(r'[^a-zA-Z\s]', '', text.lower())
        cleaned = ' '.join(cleaned.split())
        vec = self.vectorizer.transform([cleaned])
        proba = self.model.predict_proba(vec)[0]
        spam_idx = 0 if self.model.classes_[0] == 'spam' else 1
        confidence = proba[spam_idx]
        is_spam = confidence > 0.5
        return is_spam, confidence

    def keyword_filter(self, text, spam_keywords=None):
        if spam_keywords is None:
            spam_keywords = ['free money', 'click here', 'winner', 'bitcoin', 'casino']
        text_lower = text.lower()
        for keyword in spam_keywords:
            if keyword in text_lower:
                return True, 0.9
        return False, 0.0