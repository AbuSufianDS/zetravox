from spam_service.detector import SpamDetector
import os

class SafeSpamChecker:
    def __init__(self):
        self.detector = None
        self.enabled = False
        self._initialize()

    def _initialize(self):
        try:
            self.detector = SpamDetector()
            self.enabled = self.detector.enabled
            if self.enabled:
                print("Spam detection is ACTIVE")
        except Exception as e:
            print(f"Spam detection disabled: {e}")
            self.enabled = False

    def check_post(self, content):
        if not self.enabled or not content:
            return False, 0.0, False

        try:
            is_spam_ml, confidence = self.detector.predict(content)
            is_keyword_spam, keyword_confidence = self.detector.keyword_filter(content)

            final_confidence = max(confidence, keyword_confidence)
            is_spam = final_confidence > 0.5
            should_warn = final_confidence > 0.85

            return is_spam, final_confidence, should_warn

        except Exception as e:
            print(f"Error checking spam: {e}")
            return False, 0.0, False


spam_checker = SafeSpamChecker()



