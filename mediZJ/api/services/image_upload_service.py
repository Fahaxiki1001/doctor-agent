"""Shared, ownership-aware image upload and retention service."""

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from mediZJ.memory.session_db import SessionDB


UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_EXTENSION_TYPES = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".gif": "gif",
    ".webp": "webp",
}
_MIME_TYPES = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


class ImageUploadError(ValueError):
    pass


@dataclass(frozen=True)
class SavedImage:
    url: str
    filename: str
    original_name: str
    size: int
    content_type: str
    expires_at: Optional[str]


def detect_image_type(data: bytes) -> Optional[str]:
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and len(data) > 11 and data[8:12] == b"WEBP":
        return "webp"
    return None


class ImageUploadService:
    def __init__(
        self,
        db: Optional[SessionDB] = None,
        upload_dir: Optional[Path] = None,
    ):
        self.db = db or SessionDB()
        self.upload_dir = upload_dir or UPLOAD_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        file: UploadFile,
        user_id: str,
        *,
        purpose: str = "chat",
        retention_days: Optional[int] = None,
    ) -> SavedImage:
        original_name = Path(file.filename or "").name
        if not original_name or original_name != file.filename:
            raise ImageUploadError("文件名无效")
        ext = Path(original_name).suffix.lower()
        expected_type = _EXTENSION_TYPES.get(ext)
        if expected_type is None:
            raise ImageUploadError("仅支持 JPEG、PNG、GIF 和 WebP 图片")
        content = await file.read()
        max_size = int(os.getenv("IMAGE_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
        if not content:
            raise ImageUploadError("文件为空")
        if len(content) > max_size:
            raise ImageUploadError(f"图片超过 {max_size // 1024 // 1024}MB 限制")
        detected = detect_image_type(content)
        if detected is None:
            raise ImageUploadError("无法识别图片格式")
        if detected != expected_type:
            raise ImageUploadError("文件扩展名与实际图片格式不一致")

        filename = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex}{ext}"
        path = self.upload_dir / filename
        path.write_bytes(content)
        expires_at = None
        if retention_days is not None:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(days=retention_days)
            ).isoformat()
        try:
            self.db.save_upload(
                filename=filename,
                user_id=user_id,
                original_name=original_name,
                content_type=_MIME_TYPES[detected],
                size=len(content),
                purpose=purpose,
                expires_at=expires_at,
            )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return SavedImage(
            url=f"/uploads/{filename}",
            filename=filename,
            original_name=original_name,
            size=len(content),
            content_type=_MIME_TYPES[detected],
            expires_at=expires_at,
        )

    def ensure_owned(self, image_url: str, user_id: str, is_admin: bool = False) -> None:
        filename = Path(image_url).name
        if filename != image_url.removeprefix("/uploads/"):
            raise FileNotFoundError(image_url)
        metadata = self.db.get_upload(filename)
        if metadata is None:
            if is_admin and (self.upload_dir / filename).is_file():
                return
            raise FileNotFoundError(image_url)
        if metadata["user_id"] != user_id and not is_admin:
            raise FileNotFoundError(image_url)

    def delete(self, filename: str, user_id: Optional[str] = None) -> bool:
        safe_name = Path(filename).name
        if safe_name != filename:
            return False
        metadata = self.db.get_upload(safe_name)
        if metadata is None or (
            user_id is not None and metadata["user_id"] != user_id
        ):
            return False
        (self.upload_dir / safe_name).unlink(missing_ok=True)
        self.db.delete_upload(safe_name, user_id)
        return True

    def cleanup_expired(self) -> int:
        cleaned = 0
        for item in self.db.list_expired_uploads():
            if self.delete(item["filename"], item["user_id"]):
                cleaned += 1
        return cleaned
