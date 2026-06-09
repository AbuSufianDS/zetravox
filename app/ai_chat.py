import os
import requests
import json
from flask import current_app
import google.generativeai as genai


class AIChatbot:
    def __init__(self):
        self.api_type = current_app.config.get('AI_API_TYPE', 'gemini')
        self.setup_client()

    def setup_client(self):
        if self.api_type == 'gemini':
            genai.configure(api_key=current_app.config.get('GEMINI_API_KEY'))
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        elif self.api_type == 'deepseek':
            self.api_key = current_app.config.get('DEEPSEEK_API_KEY')
            self.api_url = "https://api.deepseek.com/v1/chat/completions"
        elif self.api_type == 'openai':
            import openai
            openai.api_key = current_app.config.get('OPENAI_API_KEY')
            self.client = openai.OpenAI()

    def chat(self, message, context=None):
        try:
            if self.api_type == 'gemini':
                response = self.model.generate_content(message)
                return response.text

            elif self.api_type == 'deepseek':
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": message}],
                    "stream": False
                }
                response = requests.post(self.api_url, headers=headers, json=data)
                return response.json()['choices'][0]['message']['content']

            elif self.api_type == 'openai':
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": message}]
                )
                return response.choices[0].message.content

        except Exception as e:
            return f"AI Error: {str(e)}"

    def suggest_post(self, topic, tone='casual'):
        prompt = f"Write a {tone} social media post about: {topic}. Keep it under 280 characters."
        return self.chat(prompt)

    def moderate_comment(self, comment):
        prompt = f"Analyze this comment for spam, hate speech, or inappropriate content. Respond with only 'safe' or 'flag': {comment}"
        result = self.chat(prompt)
        return result.lower().strip() == 'safe'


ai_chatbot = AIChatbot()