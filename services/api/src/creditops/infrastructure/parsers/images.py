from __future__ import annotations

from uuid import UUID

from creditops.application.stages.parse import ParsedDocument, ParsedRegion
from creditops.application.stages.security import SecureDocument


class ImageParser:
    """Image metadata parser; OCR/vision is a separate configured FPT stage."""

    def parse(self, document_version_id: UUID, document: SecureDocument) -> ParsedDocument:
        if document.content_type not in {"image/jpeg", "image/png"}:
            raise ValueError("ImageParser received a non-image document")
        return ParsedDocument(
            document_version_id=document_version_id,
            content_type=document.content_type,
            regions=(
                ParsedRegion(
                    page=1,
                    text="[Hình ảnh chưa có văn bản trích xuất; cần kiểm tra thị giác]",
                    x=0,
                    y=0,
                    width=1,
                    height=1,
                ),
            ),
            extraction_method="image-metadata-v1",
            parser_version="image-parser-v1",
        )
