"""
Product and carousel image upload helper.

Images are stored in MongoDB GridFS (default 'fs' bucket).
Save functions return a GridFS file ID (str of ObjectId).
Delete functions accept that same ID string.
"""
import io
from bson import ObjectId

import gridfs
from PIL import Image, ImageOps
from flask import current_app

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}


def _allowed(filename: str) -> bool:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS


def _get_fs():
    from app.extensions import mongo
    return gridfs.GridFS(mongo.db)


def save_product_image(file_storage, old_file_id: str | None = None) -> str:
    """
    Validate, resize, and store a product image in GridFS.

    - Enforces ALLOWED_EXTENSIONS and PRODUCT_IMAGE_MAX_BYTES.
    - Crops the image to PRODUCT_IMAGE_SIZE (cover strategy, no distortion).
    - Saves as JPEG quality=85.
    - Deletes old_file_id from GridFS when replacing an existing image.

    Returns the new GridFS file ID as a string.
    Raises ValueError with a user-facing message on any validation error.
    """
    if not file_storage or not getattr(file_storage, 'filename', ''):
        raise ValueError('Aucun fichier sélectionné.')

    if not _allowed(file_storage.filename):
        raise ValueError('Format non supporté. Utilisez JPG, PNG ou WebP.')

    file_storage.seek(0, 2)
    size_bytes = file_storage.tell()
    file_storage.seek(0)

    max_bytes = current_app.config.get('PRODUCT_IMAGE_MAX_BYTES', 5 * 1024 * 1024)
    if size_bytes > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise ValueError(
            f"Image trop volumineuse (max {max_mb} Mo, reçu {size_bytes // 1024} Ko)."
        )

    target = current_app.config.get('PRODUCT_IMAGE_SIZE', (400, 400))
    try:
        img = Image.open(file_storage.stream)
        img = img.convert('RGB')
        img = ImageOps.fit(img, target, Image.LANCZOS)
    except Exception:
        raise ValueError('Impossible de lire le fichier image. Vérifiez que le fichier est valide.')

    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=85, optimize=True)
    buf.seek(0)

    fs = _get_fs()
    if old_file_id:
        _delete_from_gridfs(old_file_id, fs)

    file_id = fs.put(buf, content_type='image/jpeg', metadata={'type': 'product'})
    return str(file_id)


def save_carousel_image(file_storage, old_file_id: str | None = None) -> str:
    """
    Validate, resize (1400×700 landscape cover-crop), and store in GridFS.
    Returns the new file ID. Raises ValueError on validation error.
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

    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=88, optimize=True)
    buf.seek(0)

    fs = _get_fs()
    if old_file_id:
        _delete_from_gridfs(old_file_id, fs)

    file_id = fs.put(buf, content_type='image/jpeg', metadata={'type': 'carousel'})
    return str(file_id)


def delete_product_image(file_id: str | None) -> None:
    """Remove a product image from GridFS. Silently ignores missing files."""
    if not file_id:
        return
    _delete_from_gridfs(file_id, _get_fs())


def delete_carousel_image(file_id: str | None) -> None:
    """Remove a carousel image from GridFS. Silently ignores missing files."""
    if not file_id:
        return
    _delete_from_gridfs(file_id, _get_fs())


def _delete_from_gridfs(file_id: str, fs) -> None:
    try:
        fs.delete(ObjectId(file_id))
    except Exception:
        pass
