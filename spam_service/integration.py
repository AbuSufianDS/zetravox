from spam_service.detector import SpamDetector
import os


class SafeSpamChecker:
    def __init__(self):
        self.detector = None
        self.enabled = False
        self._initialize()

    def _initialize(self):
        try:
            model_path = 'spam_service/models/spam_model.pkl'
            vectorizer_path = 'spam_service/models/vectorizer.pkl'

            if os.path.exists(model_path) and os.path.exists(vectorizer_path):
                self.detector = SpamDetector(model_path, vectorizer_path)
                self.enabled = True
                print(" Spam detection is ACTIVE")
            else:
                print(" Spam detection INACTIVE (run python spam_service/train.py first)")
        except Exception as e:
            print(f" Spam detection disabled: {e}")
            self.enabled = False

    def check_post(self, content):
        if not self.enabled or not content:
            return False, 0.0, False

        try:
            is_spam_ml, confidence = self.detector.predict(content)
            is_keyword_spam, keyword_confidence = self.detector.keyword_filter(content)
            is_spam = is_spam_ml or is_keyword_spam
            final_confidence = max(confidence, keyword_confidence)
            should_warn = is_spam and final_confidence > 0.9

            return is_spam, final_confidence, should_warn

        except Exception as e:
            print(f"Error checking spam: {e}")
            return False, 0.0, False
spam_checker = SafeSpamChecker()