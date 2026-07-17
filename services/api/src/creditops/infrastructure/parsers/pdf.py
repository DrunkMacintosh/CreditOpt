from __future__ import annotations

import re
from uuid import UUID

from creditops.application.stages.parse import ParsedDocument, ParsedRegion
from creditops.application.stages.security import SecureDocument


class PdfParser:
    """Extract text from PDF without executing annotations, scripts, or actions."""

    def parse(self, document_version_id: UUID, document: SecureDocument) -> ParsedDocument:
        if document.content_type != "application/pdf":
            raise ValueError("PdfParser received a non-PDF document")
        regions: list[ParsedRegion] = []
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]

            reader = PdfReader(document.content)
            for number, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    regions.append(
                        ParsedRegion(page=number, text=text[:100_000], x=0, y=0, width=1, height=1)
                    )
        except ImportError:
            # Keep the local walking skeleton usable without optional PDF
            # wheels.  This is intentionally a tiny literal-string reader for
            # test fixtures; production images must include pypdf.
            for number, page_bytes in enumerate(document.content.split(b"/Type /Page"), start=1):
                text = " ".join(
                    match.decode("utf-8", errors="ignore")
                    for match in re.findall(rb"\(([^()]*)\)", page_bytes)
                ).strip()
                if text:
                    regions.append(
                        ParsedRegion(page=number, text=text[:100_000], x=0, y=0, width=1, height=1)
                    )
        except Exception as exc:
            raise ValueError("PDF parsing failed; document requires manual review") from exc
        return ParsedDocument(
            document_version_id=document_version_id,
            content_type=document.content_type,
            regions=tuple(regions),
            extraction_method="pypdf-text-v1",
            parser_version="pdf-parser-v1",
        )
