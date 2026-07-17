from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from creditops.application.stages.parse import ParsedDocument

DocumentFamily = Literal[
    "LEGAL",
    "CREDIT_REQUEST",
    "BUSINESS",
    "FINANCIAL",
    "COLLATERAL",
    "OTHER",
]


class Classification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    family: DocumentFamily
    confidence: float = Field(ge=0, le=1)
    method: Literal["filename-rules-v1", "manual-review"]


_RULES: tuple[tuple[DocumentFamily, tuple[str, ...]], ...] = (
    ("CREDIT_REQUEST", ("don de nghi", "vay von", "tin dung", "loan", "credit")),
    ("FINANCIAL", ("bao cao tai chinh", "financial", "balance", "income", "cashflow")),
    ("LEGAL", ("dang ky kinh doanh", "dieu le", "uy quyen", "legal", "charter")),
    ("BUSINESS", ("hop dong", "hoa don", "ke hoach", "purchase", "sales")),
    ("COLLATERAL", ("tai san dam bao", "the chap", "so hong", "collateral", "valuation")),
)


def classify_document(*, file_name: str, parsed: ParsedDocument) -> Classification:
    normalized = _normalize(file_name)
    for family, keywords in _RULES:
        if any(keyword in normalized for keyword in keywords):
            return Classification(family=family, confidence=0.85, method="filename-rules-v1")
    content = _normalize(" ".join(region.text for region in parsed.regions[:20]))
    for family, keywords in _RULES:
        if any(keyword in content for keyword in keywords):
            return Classification(family=family, confidence=0.65, method="filename-rules-v1")
    return Classification(family="OTHER", confidence=0.0, method="manual-review")


def _normalize(value: str) -> str:
    without_marks = "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    return re.sub(r"[_\-.]+", " ", without_marks)
