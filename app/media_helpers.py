import os
import uuid
from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}
MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_FILES = 10


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_media(file, folder='posts'):
    if not file or not file.filename:
        return None, None

    if not allowed_file(file.filename):
        return None, None

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = str(uuid.uuid4()) + '.' + ext

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', folder)
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)

    media_type = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'video'

    try:
        if media_type == 'image':
            img = Image.open(file)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail((1200, 1200))
            img.save(filepath, optimize=True, quality=85)
        else:
            file.save(filepath)

        return filename, media_type
    except Exception as e:
        current_app.logger.error(f"Error saving media {file.filename}: {e}")
        return None, None


def save_multiple_media(files, folder='posts'):
    saved_files = []

    if not files:
        return saved_files

    if not isinstance(files, list):
        files = [files]

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', folder)
    os.makedirs(upload_dir, exist_ok=True)

    for file in files:
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = str(uuid.uuid4()) + '.' + ext
            filepath = os.path.join(upload_dir, filename)

            media_type = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'video'

            try:
                if media_type == 'image':
                    img = Image.open(file)
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    img.thumbnail((1200, 1200))
                    img.save(filepath, optimize=True, quality=85)
                else:
                    file.save(filepath)

                saved_files.append({
                    'filename': filename,
                    'media_type': media_type,
                    'folder': folder
                })
            except Exception as e:
                current_app.logger.error(f"Error saving media {file.filename}: {e}")
                continue

    return saved_files

def delete_media(filename, folder='posts'):
    if filename and filename not in ['default.jpg', 'default_cover.jpg', 'None', '']:
        try:
            filepath = os.path.join(current_app.root_path, 'static', 'uploads', folder, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                current_app.logger.info(f"Deleted file: {filepath}")
            else:
                current_app.logger.warning(f"File not found: {filepath}")
        except Exception as e:
            current_app.logger.error(f"Error deleting file {filename}: {e}")


def delete_multiple_media(filenames, folder='posts'):
    for filename in filenames:
        delete_media(filename, folder)
