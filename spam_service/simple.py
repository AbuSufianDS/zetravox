import re

class SimpleSpamDetector:
    def check_post(self, text):
        spam_keywords = ['casino', 'viagra', 'lottery', 'winner', 'bitcoin', 'investment']
        text_lower = text.lower()
        score = sum(1 for word in spam_keywords if word in text_lower) / len(spam_keywords)
        is_spam = score > 0.3
        return is_spam, score, score > 0.2

spam_checker = SimpleSpamDetector()