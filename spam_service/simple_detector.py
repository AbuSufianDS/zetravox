import re


class SimpleSpamDetector:
    def __init__(self):
        self.spam_patterns = [
            (r'casino|viagra|lottery|winner|bitcoin|crypto|investment', 0.3),
            (r'earn money|free money|click here|subscribe|follow me', 0.3),
            (r'http://|https://|www\.', 0.1),
            (r'!!!+|\?{3,}', 0.1),
        ]

    def check_post(self, text):
        text_lower = text.lower()
        spam_score = 0.0
        for pattern, weight in self.spam_patterns:
            if re.search(pattern, text_lower):
                spam_score += weight
        spam_score = min(spam_score, 1.0)
        is_spam = spam_score > 0.5
        should_warn = spam_score > 0.3
        return is_spam, spam_score, should_warn


spam_checker = SimpleSpamDetector()
