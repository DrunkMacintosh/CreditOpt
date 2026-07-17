from __future__ import annotations

import io
import zipfile
from uuid import UUID
from xml.etree import ElementTree

from creditops.application.stages.parse import ParsedDocument, ParsedRegion
from creditops.application.stages.security import SecureDocument

_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class XlsxParser:
    """Read worksheet values from XML without evaluating formulas or macros."""

    def parse(self, document_version_id: UUID, document: SecureDocument) -> ParsedDocument:
        if not document.content_type.endswith("spreadsheetml.sheet"):
            raise ValueError("XlsxParser received a non-XLSX document")
        try:
            with zipfile.ZipFile(io.BytesIO(document.content)) as archive:
                shared = self._shared_strings(archive)
                workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
                sheet_names = [
                    element.attrib.get("name", "Sheet")
                    for element in workbook.iter(f"{_MAIN_NS}sheet")
                ]
                sheet_files = sorted(
                    name
                    for name in archive.namelist()
                    if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
                )
                regions: list[ParsedRegion] = []
                for sheet_index, sheet_file in enumerate(sheet_files, start=1):
                    root = ElementTree.fromstring(archive.read(sheet_file))
                    for row_index, row in enumerate(root.iter(f"{_MAIN_NS}row"), start=1):
                        values = [
                            self._cell_value(cell, shared)
                            for cell in row.iter(f"{_MAIN_NS}c")
                        ]
                        text = " | ".join(value for value in values if value)
                        if text:
                            page = sheet_index
                            sheet_label = (
                                sheet_names[sheet_index - 1]
                                if sheet_index <= len(sheet_names)
                                else "Sheet"
                            )
                            regions.append(
                                ParsedRegion(
                                    page=page,
                                    text=(
                                        f"{sheet_label} "
                                        f"row {row_index}: {text}"
                                    )[:100_000],
                                    x=0,
                                    y=min((row_index - 1) * 0.02, 0.98),
                                    width=1,
                                    height=0.015,
                                )
                            )
        except (KeyError, ElementTree.ParseError, zipfile.BadZipFile) as exc:
            raise ValueError("XLSX parsing failed; document requires manual review") from exc
        return ParsedDocument(
            document_version_id=document_version_id,
            content_type=document.content_type,
            regions=tuple(regions[:50_000]),
            extraction_method="xlsx-xml-v1",
            parser_version="xlsx-parser-v1",
        )

    @staticmethod
    def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
        try:
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        except KeyError:
            return []
        return [
            "".join(node.text or "" for node in item.iter(f"{_MAIN_NS}t"))
            for item in root.iter(f"{_MAIN_NS}si")
        ]

    @staticmethod
    def _cell_value(cell: ElementTree.Element, shared: list[str]) -> str:
        value = cell.find(f"{_MAIN_NS}v")
        if value is None or value.text is None:
            return ""
        raw = value.text
        if cell.attrib.get("t") == "s":
            try:
                return shared[int(raw)]
            except (ValueError, IndexError):
                return ""
        return raw
