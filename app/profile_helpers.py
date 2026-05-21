import os
import uuid
from PIL import Image
from flask import current_app


def save_profile_picture(file, old_filename=None):
    if not file or not file.filename:
        return 'default.jpg'

    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'gif']:
        return 'default.jpg'

    filename = str(uuid.uuid4()) + '.' + ext

    profile_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
    os.makedirs(profile_dir, exist_ok=True)

    if old_filename and old_filename != 'default.jpg':
        old_path = os.path.join(profile_dir, old_filename)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except:
                pass

    filepath = os.path.join(profile_dir, filename)

    try:
        img = Image.open(file)

        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        img.thumbnail((200, 200))
        img.save(filepath, optimize=True, quality=85)

        return filename
    except Exception as e:
        print(f"Error saving profile picture: {e}")
        return 'default.jpg'


def delete_profile_picture(filename):
    if filename and filename != 'default.jpg':
        profile_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
        filepath = os.path.join(profile_dir, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass