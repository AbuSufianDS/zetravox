import joblib
import os
import re
import sys


class SpamDetector:
    def __init__(self, model_path=None, vectorizer_path=None):
        self.model = None
        self.vectorizer = None
        self.enabled = False
        self._load_model()

    def _load_model(self):
        is_render = os.environ.get('RENDER', False)

        if not is_render:
            try:
                from transformers import AutoTokenizer, AutoModelForSequenceClassification
                import torch
                self.transformer_tokenizer = AutoTokenizer.from_pretrained(
                    "mrm8488/bert-tiny-finetuned-sms-spam-detection")
                self.transformer_model = AutoModelForSequenceClassification.from_pretrained(
                    "mrm8488/bert-tiny-finetuned-sms-spam-detection")
                self.transformer_model.eval()
                self.use_transformer = True
                self.enabled = True
                print("Transformer spam detector loaded")
                return
            except Exception as e:
                print(f"Transformer failed: {e}")

        self.use_transformer = False
        model_path = 'spam_service/models/spam_model.pkl'
        vectorizer_path = 'spam_service/models/vectorizer.pkl'

        if os.path.exists(model_path) and os.path.exists(vectorizer_path):
            self.model = joblib.load(model_path)
            self.vectorizer = joblib.load(vectorizer_path)
            self.enabled = True
            print("Scikit-learn spam detector loaded")
        else:
            print("No spam detector available")

    def predict(self, text):
        if not self.enabled or not text:
            return False, 0.0

        if self.use_transformer:
            return self._predict_transformer(text)
        else:
            return self._predict_fallback(text)

    def _predict_transformer(self, text):
        import torch
        inputs = self.transformer_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = self.transformer_model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        spam_prob = probs[0][1].item()
        return spam_prob > 0.5, spam_prob

    def _predict_fallback(self, text):
        cleaned = re.sub(r'[^a-zA-Z\s]', '', text.lower())
        cleaned = ' '.join(cleaned.split())
        vec = self.vectorizer.transform([cleaned])
        proba = self.model.predict_proba(vec)[0]
        spam_idx = 0 if self.model.classes_[0] == 'spam' else 1
        confidence = proba[spam_idx]
        return confidence > 0.5, confidence

    def keyword_filter(self, text, spam_keywords=None):
        if spam_keywords is None:
            spam_keywords = ['free money', 'click here', 'winner', 'bitcoin', 'casino']
        text_lower = text.lower()
        for keyword in spam_keywords:
            if keyword in text_lower:
                return True, 0.9
        return False, 0.0