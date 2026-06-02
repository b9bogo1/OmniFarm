"""
Product image upload helper.

Handles validation, Pillow resize (cover-crop to PRODUCT_IMAGE_SIZE),
and disk I/O for the product photo feature.
"""
import os
import uuid

from PIL import Image, ImageOps
from flask import current_app

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}


def _allowed(filename: str) -> bool:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS


def save_product_image(file_storage, old_filename: str | None = None) -> str:
    """
    Validate, resize, and persist an uploaded image file.

    - Enforces ALLOWED_EXTENSIONS and PRODUCT_IMAGE_MAX_BYTES.
    - Crops the image to PRODUCT_IMAGE_SIZE (cover strategy, no distortion).
    - Saves as JPEG quality=85 with a UUID-based filename.
    - Deletes old_filename from disk when replacing an existing image.

    Returns the new filename (basename only).
    Raises ValueError with a user-facing message on any validation error.
    """
    if not file_storage or not getattr(file_storage, 'filename', ''):
        raise ValueError('Aucun fichier sélectionné.')

    if not _allowed(file_storage.filename):
        raise ValueError(
            'Format non supporté. Utilisez JPG, PNG ou WebP.'
        )

    # Check file size before fully reading the stream
    file_storage.seek(0, 2)
    size_bytes = file_storage.tell()
    file_storage.seek(0)

    max_bytes = current_app.config.get('PRODUCT_IMAGE_MAX_BYTES', 5 * 1024 * 1024)
    if size_bytes > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise ValueError(
            f"Image trop volumineuse (max {max_mb} Mo, reçu {size_bytes // 1024} Ko)."
        )

    # Open, convert to RGB (handles PNG/WebP transparency), cover-crop
    target = current_app.config.get('PRODUCT_IMAGE_SIZE', (400, 400))
    try:
        img = Image.open(file_storage.stream)
        img = img.convert('RGB')
        img = ImageOps.fit(img, target, Image.LANCZOS)
    except Exception:
        raise ValueError('Impossible de lire le fichier image. Vérifiez que le fichier est valide.')

    # Persist with unique name
    new_filename = f"{uuid.uuid4().hex}.jpg"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    img.save(
        os.path.join(upload_folder, new_filename),
        'JPEG',
        quality=85,
        optimize=True,
    )

    # Remove the old image file if we're replacing it
    if old_filename:
        _delete_file(old_filename, upload_folder)

    return new_filename


def save_carousel_image(file_storage, old_filename: str | None = None) -> str:
    """
    Validate, resize (1400×700 landscape cover-crop), and persist a carousel image.
    Returns the new filename. Raises ValueError on validation error.
    """
    if not file_storage or not getattr(file_storage, 'filename', ''):
        raise ValueError('Aucun fichier sélectionné.')

    if not _allowed(file_storage.filename):
        raise ValueError('Format non supporté. Utilisez JPG, PNG ou WebP.')

    file_storage.seek(0, 2)
    size_bytes = file_storage.tell()
    file_storage.seek(0)

    max_bytes = current_app.config.get('CAROUSEL_IMAGE_MAX_BYTES', 8 * 1024 * 1024)
    if size_bytes > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise ValueError(f"Image trop volumineuse (max {max_mb} Mo, reçu {size_bytes // 1024} Ko).")

    target = current_app.config.get('CAROUSEL_IMAGE_SIZE', (1400, 700))
    try:
        img = Image.open(file_storage.stream)
        img = img.convert('RGB')
        img = ImageOps.fit(img, target, Image.LANCZOS)
    except Exception:
        raise ValueError('Impossible de lire le fichier image. Vérifiez que le fichier est valide.')

    new_filename = f"carousel_{uuid.uuid4().hex}.jpg"
    upload_folder = current_app.config['CAROUSEL_UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    img.save(os.path.join(upload_folder, new_filename), 'JPEG', quality=88, optimize=True)

    if old_filename:
        _delete_file(old_filename, upload_folder)

    return new_filename


def delete_carousel_image(filename: str | None) -> None:
    """Remove a carousel image from disk. Silently ignores missing files."""
    if not filename:
        return
    folder = current_app.config.get('CAROUSEL_UPLOAD_FOLDER', '')
    _delete_file(filename, folder)


def delete_product_image(filename: str | None) -> None:
    """Remove a product image from disk. Silently ignores missing files."""
    if not filename:
        return
    upload_folder = current_app.config.get('UPLOAD_FOLDER', '')
    _delete_file(filename, upload_folder)


def _delete_file(filename: str, folder: str) -> None:
    try:
        path = os.path.join(folder, filename)
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
