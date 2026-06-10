import os
import json
import requests


class AIService:
    def __init__(self):
        self.api_key = os.environ.get('AI_API_KEY', '')
        self.api_url = os.environ.get('AI_API_URL', 'https://api.openai.com/v1/chat/completions')

    def chat(self, message, history=None):
        if not self.api_key:
            return self.get_fallback_response(message)

        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            messages = [
                {'role': 'system',
                 'content': 'You are Zetravox AI, a helpful assistant for a social media platform. Help users with posting, connecting, privacy settings, and general questions.'}
            ]

            if history:
                messages.extend(history)

            messages.append({'role': 'user', 'content': message})

            data = {
                'model': 'gpt-3.5-turbo',
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 500
            }

            response = requests.post(self.api_url, headers=headers, json=data)

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return self.get_fallback_response(message)

        except Exception as e:
            print(f"AI API Error: {e}")
            return self.get_fallback_response(message)

    def get_fallback_response(self, message):
        responses = {
            'post': "To create a post, click the 'Create Post' button on your homepage. You can add text, images, videos, and set privacy preferences.",
            'connect': "To connect with friends, visit their profile and click 'Connect'. You can also discover people in the Discover section.",
            'privacy': "Privacy settings can be found in Settings > Privacy. You can control who sees your posts and who can message you.",
            'message': "You can send private messages by clicking the message icon on someone's profile or in the messages section."
        }

        for key, response in responses.items():
            if key in message.lower():
                return response

        return "Welcome to Zetravox! I'm your AI assistant. I can help you with creating posts, connecting with friends, privacy settings, and more. What would you like to know?"
