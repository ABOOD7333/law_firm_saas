"""Bounded, path-safe storage for user supplied uploads."""
import os
import secrets
import codecs

from fastapi import HTTPException, UploadFile


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".gif", ".txt"}


def save_upload(upload: UploadFile, directory: str, max_bytes: int = MAX_UPLOAD_BYTES) -> str:
    """Save an upload under a generated name and enforce a strict byte limit."""
    os.makedirs(directory, exist_ok=True)
    original_name = os.path.basename(upload.filename or "")
    suffix = os.path.splitext(original_name)[1].lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="نوع الملف غير مدعوم")

    filename = f"{secrets.token_hex(16)}{suffix}"
    destination = os.path.join(directory, filename)
    size = 0
    signature = bytearray()
    text_decoder = codecs.getincrementaldecoder("utf-8")() if suffix == ".txt" else None
    try:
        with open(destination, "xb") as target:
            while True:
                chunk = upload.file.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="حجم الملف يتجاوز الحد المسموح (25 ميغابايت)")
                if text_decoder:
                    try:
                        text_decoder.decode(chunk, final=False)
                    except UnicodeDecodeError as exc:
                        raise HTTPException(status_code=400, detail="محتوى الملف النصي غير صالح") from exc
                if len(signature) < 8192:
                    signature.extend(chunk[:8192 - len(signature)])
                target.write(chunk)
        from core.security import validate_file_signature
        if text_decoder:
            try:
                text_decoder.decode(b"", final=True)
            except UnicodeDecodeError as exc:
                raise HTTPException(status_code=400, detail="محتوى الملف النصي غير صالح") from exc
        valid_signature = suffix == ".txt" or validate_file_signature(bytes(signature), suffix[1:])
        if not valid_signature:
            raise HTTPException(status_code=400, detail="محتوى الملف لا يطابق نوعه المسموح")
    except Exception:
        try:
            os.remove(destination)
        except OSError:
            pass
        raise
    finally:
        upload.file.seek(0)
    return filename
