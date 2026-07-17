from __future__ import annotations

import io
import zipfile
from hashlib import sha256
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

_MAX_FILE_BYTES: Final = 100 * 1024 * 1024
_ALLOWED_MIME: Final = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/jpeg",
        "image/png",
    }
)


class SecureDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    content: bytes
    content_type: str
    size_bytes: int = Field(gt=0, le=_MAX_FILE_BYTES)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _zip_is_supported(data: bytes, content_type: str) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            forbidden_parts = (
                "vbaProject.bin",
                "vbaData.xml",
                "activeX/",
                "embeddings/",
                "externalLinks/",
            )
            contains_forbidden = any(
                any(name.startswith(part) or part in name for part in forbidden_parts)
                for name in names
            )
            if contains_forbidden:
                raise ValueError("Office document contains macros or executable embedded parts")
            if len(names) > 10_000:
                raise ValueError("archive contains too many entries")
            total_uncompressed = sum(info.file_size for info in archive.infolist())
            if total_uncompressed > 500 * 1024 * 1024:
                raise ValueError("archive expands beyond the resource limit")
            if content_type.endswith("wordprocessingml.document"):
                return "word/document.xml" in names and "[Content_Types].xml" in names
            return "xl/workbook.xml" in names and "[Content_Types].xml" in names
    except zipfile.BadZipFile as exc:
        raise ValueError("Office document is not a valid package") from exc


def _magic_matches(data: bytes, content_type: str) -> bool:
    if content_type == "application/pdf":
        return data.startswith(b"%PDF-")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        return _zip_is_supported(data, content_type)
    return False


def validate_document_bytes(
    data: bytes,
    *,
    content_type: str,
    max_bytes: int = _MAX_FILE_BYTES,
) -> SecureDocument:
    """Validate size, declared MIME and magic bytes before parser dispatch.

    This function never executes a document package.  Office package checks use
    only central-directory metadata and reject macros/unsupported containers.
    """

    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type not in _ALLOWED_MIME:
        raise ValueError("document content type is not allowed")
    if max_bytes <= 0 or len(data) == 0 or len(data) > min(max_bytes, _MAX_FILE_BYTES):
        raise ValueError("document exceeds the configured size limit")
    if not _magic_matches(data, normalized_type):
        raise ValueError(f"document bytes do not match declared {normalized_type.upper()} type")
    digest = sha256(data).hexdigest()
    return SecureDocument(
        content=data,
        content_type=normalized_type,
        size_bytes=len(data),
        sha256=digest,
    )
