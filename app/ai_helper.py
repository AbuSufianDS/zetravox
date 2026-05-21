import requests
from flask import current_app
import json


class OpenRouterAI:
    def __init__(self):
        self.api_key = None
        self.base_url = "https://openrouter.ai/api/v1"

    def set_api_key(self, api_key):
        self.api_key = api_key
        print(f"✅ API Key set: {api_key[:20]}...")
        return self

    def chat(self, message, system_prompt=None):
        print(f"🤖 Sending message: {message[:50]}...")

        if not self.api_key:
            print("❌ No API key set!")
            return "Error: API key not configured. Please add OPENROUTER_API_KEY to .env file."

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})

            data = {
                "model": "deepseek/deepseek-r1-distill-qwen-32b:free",
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.7
            }

            print("📡 Calling OpenRouter API...")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )

            print(f"📡 Response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f" AI Response: {content[:50]}...")
                return content
            else:
                print(f" API Error: {response.status_code} - {response.text[:200]}")
                return f"API Error: {response.status_code}. Trying alternative model..."

        except Exception as e:
            print(f" Exception: {str(e)}")
            return f"Error: {str(e)}"

    def generate_post(self, topic, tone="casual"):
        prompt = f"Write a {tone} social media post about: {topic}. Keep it under 280 characters. Add 2-3 hashtags. Only return the post text."
        return self.chat(prompt)

    def improve_text(self, text, instruction="improve this text"):
        prompt = f"{instruction}: {text}\n\nOnly return the improved text, no explanations."
        return self.chat(prompt)


# Create global instance
ai = OpenRouterAI()