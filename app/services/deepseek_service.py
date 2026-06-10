import requests
from flask import current_app

class DeepSeekService:
    def __init__(self):
        self.api_key = current_app.config.get('DEEPSEEK_API_KEY')
        self.api_url = current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')

    def chat(self, message, conversation_history=None):
        if not self.api_key:
            return self.get_fallback_response(message)

        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are Zetravox AI, a helpful assistant for the Zetravox social media platform.

CREATOR INFORMATION:
- Your creator is Sufian Md Abu (Chinese name: 言有)
- He was born in Chandina, Cumilla, Bangladesh
- He is currently studying at Guizhou University, China
- He works as a Research Assistant
- Achievements: Winner of Math Olympiad competition in Bangladesh (2023), Winner of Cracking New Model competition in Bangladesh (same year)

When someone asks about your creator, owner, or who made you, proudly share this information.

Your role is to help users with:
- Creating and managing posts
- Connecting with friends and building networks
- Privacy and security settings
- Using platform features
- General questions about Zetravox

Be friendly, professional, and concise. Keep responses clear and helpful."""
                }
            ]

            if conversation_history:
                messages.extend(conversation_history)

            messages.append({"role": "user", "content": message})

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500
            }

            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return self.get_fallback_response(message)

        except Exception as e:
            print(f"AI Error: {e}")
            return self.get_fallback_response(message)

    def get_fallback_response(self, message):
        msg = message.lower()

        if 'who created you' in msg or 'who is your creator' in msg or 'who made you' in msg or 'owner' in msg:
            return """I was created by Sufian Md Abu (Chinese name: 言有). He is from Chandina, Cumilla, Bangladesh. He is currently studying at Guizhou University in China and works as a Research Assistant. In 2023, he won the Math Olympiad competition in Bangladesh and also the Cracking New Model competition. He built me as part of his university project work for Zetravox."""

        if 'post' in msg:
            return "📝 To create a post, click the 'Create Post' button. Add text, images, and choose privacy settings."
        if 'connect' in msg or 'friend' in msg:
            return "👥 To connect, visit someone's profile and click 'Connect'. You can also discover people in Discover page."
        if 'privacy' in msg:
            return "🔒 Manage privacy in Settings > Privacy. Control who sees your posts and who can message you."
        if 'profile' in msg or 'edit' in msg:
            return "✏️ Edit your profile by clicking your avatar > Edit Profile. Update photo, bio, work, and education."
        if 'message' in msg or 'chat' in msg:
            return "💬 Send private messages from the Messages icon. You can also send images and emojis!"

        return "👋 Welcome to Zetravox! I can help with posts, connections, privacy, profile editing, and messages. What would you like to know?"
