from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
IMAGE_SIGNATURE_EXTENSIONS = {"jpg": {"jpg", "jpeg"}, "png": {"png"}, "webp": {"webp"}}


class ImageValidationError(ValueError):
    pass


def validate_password_strength(password):
    errors = []
    if len(password or "") < 8:
        errors.append("비밀번호는 8자 이상이어야 합니다.")
    if not any(char.islower() for char in password or ""):
        errors.append("비밀번호에는 영문 소문자가 포함되어야 합니다.")
    if not any(char.isupper() for char in password or ""):
        errors.append("비밀번호에는 영문 대문자가 포함되어야 합니다.")
    if not any(char.isdigit() for char in password or ""):
        errors.append("비밀번호에는 숫자가 포함되어야 합니다.")
    if not any(not char.isalnum() for char in password or ""):
        errors.append("비밀번호에는 특수문자가 포함되어야 합니다.")
    return errors


def detect_image_extension(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_validated_image(file_storage, upload_folder, max_bytes, max_pixels=12_000_000):
    if not isinstance(file_storage, FileStorage) or not file_storage.filename:
        raise ImageValidationError("이미지 파일을 선택해 주세요.")

    original_ext = Path(file_storage.filename).suffix.lower().lstrip(".")
    if original_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ImageValidationError("jpg, jpeg, png, webp 이미지만 업로드할 수 있습니다.")

    data = file_storage.stream.read(max_bytes + 1)
    file_storage.stream.seek(0)
    if not data:
        raise ImageValidationError("빈 파일은 업로드할 수 없습니다.")
    if len(data) > max_bytes:
        raise ImageValidationError("이미지 파일이 너무 큽니다.")

    detected_ext = detect_image_extension(data)
    if detected_ext is None:
        raise ImageValidationError("실제 이미지 형식을 확인할 수 없습니다.")
    if original_ext not in IMAGE_SIGNATURE_EXTENSIONS[detected_ext]:
        raise ImageValidationError("파일 확장자와 실제 이미지 형식이 일치하지 않습니다.")
    sanitized = sanitize_image(data, detected_ext, max_pixels)

    upload_path = Path(upload_folder).resolve()
    upload_path.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}.{detected_ext}"
    destination = (upload_path / stored_filename).resolve()
    if destination.parent != upload_path:
        raise ImageValidationError("업로드 경로가 올바르지 않습니다.")

    destination.write_bytes(sanitized)
    return stored_filename


def sanitize_image(data, detected_ext, max_pixels):
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise ImageValidationError("이미지 해상도가 허용 범위를 초과했습니다.")
            output = BytesIO()
            if detected_ext == "jpg":
                image.convert("RGB").save(output, format="JPEG", quality=88, optimize=True)
            elif detected_ext == "png":
                image.save(output, format="PNG", optimize=True)
            elif detected_ext == "webp":
                image.save(output, format="WEBP", quality=88, method=4)
            else:
                raise ImageValidationError("지원하지 않는 이미지 형식입니다.")
            return output.getvalue()
    except (ImageValidationError, UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        if isinstance(exc, ImageValidationError):
            raise
        raise ImageValidationError("이미지 파일을 안전하게 처리할 수 없습니다.") from exc


def remove_uploaded_file(upload_folder, stored_filename):
    if not stored_filename:
        return
    upload_path = Path(upload_folder).resolve()
    destination = (upload_path / stored_filename).resolve()
    if destination.parent == upload_path and destination.exists():
        destination.unlink()
