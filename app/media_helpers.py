import os
import uuid
from PIL import Image
from flask import current_app


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def get_file_size(file):
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size


def is_video(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ['mp4', 'mov', 'avi', 'webm', 'mkv']


def is_image(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ['png', 'jpg', 'jpeg', 'gif']


def save_media(file, subfolder=''):
    if not file or not file.filename:
        return None, None

    if not allowed_file(file.filename):
        return None, None

    size = get_file_size(file)
    if is_image(file.filename) and size > current_app.config['MAX_IMAGE_SIZE']:
        return None, None
    if is_video(file.filename) and size > current_app.config['MAX_VIDEO_SIZE']:
        return None, None

    media_type = 'image' if is_image(file.filename) else 'video' if is_video(file.filename) else None

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = str(uuid.uuid4()) + '.' + ext

    if subfolder:
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    else:
        upload_folder = current_app.config['UPLOAD_FOLDER']

    os.makedirs(upload_folder, exist_ok=True)

    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)

    if media_type == 'image':
        create_thumbnail(filepath, upload_folder, filename)

    return filename, media_type


def create_thumbnail(filepath, upload_folder, filename):
    try:
        img = Image.open(filepath)
        img.thumbnail((300, 300))
        thumbnail_name = f"thumb_{filename}"
        thumbnail_path = os.path.join(upload_folder, thumbnail_name)
        img.save(thumbnail_path, optimize=True, quality=85)
    except Exception as e:
        print(f"Thumbnail creation failed: {e}")


def get_media_url(filename, subfolder=''):
    if filename:
        if subfolder:
            return f"/static/uploads/{subfolder}/{filename}"
        return f"/static/uploads/{filename}"
    return None


def get_thumbnail_url(filename, subfolder=''):
    if filename and is_image(filename):
        if subfolder:
            thumb_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, f"thumb_{filename}")
            if os.path.exists(thumb_path):
                return f"/static/uploads/{subfolder}/thumb_{filename}"
        else:
            thumb_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"thumb_{filename}")
            if os.path.exists(thumb_path):
                return f"/static/uploads/thumb_{filename}"
    return get_media_url(filename, subfolder)


def delete_media(filename, subfolder=''):
    if filename:
        try:
            if subfolder:
                upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
            else:
                upload_folder = current_app.config['UPLOAD_FOLDER']

            filepath = os.path.join(upload_folder, filename)
            if os.path.exists(filepath):
                os.remove(filepath)

            thumbpath = os.path.join(upload_folder, f"thumb_{filename}")
            if os.path.exists(thumbpath):
                os.remove(thumbpath)
        except Exception as e:
            print(f"Failed to delete media: {e}")