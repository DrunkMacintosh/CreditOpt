from __future__ import annotations

import io
import zipfile
from uuid import UUID
from xml.etree import ElementTree

from creditops.application.stages.parse import ParsedDocument, ParsedRegion
from creditops.application.stages.security import SecureDocument

_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxParser:
    """Read WordprocessingML text only; macros and embedded objects are ignored."""

    def parse(self, document_version_id: UUID, document: SecureDocument) -> ParsedDocument:
        if not document.content_type.endswith("wordprocessingml.document"):
            raise ValueError("DocxParser received a non-DOCX document")
        try:
            with zipfile.ZipFile(io.BytesIO(document.content)) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
        except (KeyError, ElementTree.ParseError, zipfile.BadZipFile) as exc:
            raise ValueError("DOCX parsing failed; document requires manual review") from exc
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{_WORD_NS}p"):
            text = "".join(node.text or "" for node in paragraph.iter(f"{_WORD_NS}t")).strip()
            if text:
                paragraphs.append(text)
        regions = tuple(
            ParsedRegion(
                page=1,
                text=text[:100_000],
                x=0,
                y=min(i * 0.05, 0.95),
                width=1,
                height=0.04,
            )
            for i, text in enumerate(paragraphs[:2_000])
        )
        return ParsedDocument(
            document_version_id=document_version_id,
            content_type=document.content_type,
            regions=regions,
            extraction_method="docx-xml-v1",
            parser_version="docx-parser-v1",
        )
