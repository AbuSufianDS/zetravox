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

    if old_filename and old_filename not in ['default.jpg', 'default_cover.jpg', 'None', '']:
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

        if ext.lower() == 'png':
            img.save(filepath, optimize=True, quality=85)
        else:
            img.save(filepath, optimize=True, quality=85)

        return filename
    except Exception as e:
        print(f"Error saving profile picture: {e}")
        return old_filename if old_filename else 'default.jpg'


def save_cover_picture(file, old_filename=None):
    if not file or not file.filename:
        return 'default_cover.jpg'

    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'gif']:
        return 'default_cover.jpg'

    filename = str(uuid.uuid4()) + '.' + ext

    cover_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'covers')
    os.makedirs(cover_dir, exist_ok=True)

    if old_filename and old_filename not in ['default_cover.jpg', 'default.jpg', 'None', '']:
        old_path = os.path.join(cover_dir, old_filename)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except:
                pass

    filepath = os.path.join(cover_dir, filename)

    try:
        img = Image.open(file)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        img.thumbnail((1500, 500))
        img.save(filepath, optimize=True, quality=85)
        return filename
    except Exception as e:
        print(f"Error saving cover picture: {e}")
        return old_filename if old_filename else 'default_cover.jpg'


def delete_profile_picture(filename):
    if filename and filename not in ['default.jpg', 'default_cover.jpg', 'None', '']:
        profile_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
        filepath = os.path.join(profile_dir, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass


def delete_cover_picture(filename):
    if filename and filename not in ['default_cover.jpg', 'default.jpg', 'None', '']:
        cover_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'covers')
        filepath = os.path.join(cover_dir, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass