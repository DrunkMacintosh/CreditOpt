"""Shared compliance definitions: forbidden claims, slot detection, spec text walking."""
import re

SLOT_RE = re.compile(r"\[[^\]]+\]")

# Claim phrases the deck must never contain (design spec section 3.3).
FORBIDDEN = [
    "đầu tiên của SHB",
    "được SHB phê duyệt",
    "SHB đã phê duyệt",
    "SHB chứng thực",
    "production-ready",
    "sẵn sàng production",
    "đã được chứng nhận bảo mật",
]


def flat_strings(value):
    """Recursively collect the strings inside a nested list/tuple structure."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(flat_strings(item))
        return out
    return []


def spec_strings(spec):
    """All strings of a slide spec that are rendered on the slide (notes excluded)."""
    chunks = [spec["title"], spec.get("killer", "")] + list(spec.get("bullets", []))
    for value in (spec.get("extra") or {}).values():
        chunks.extend(flat_strings(value))
    return chunks


def slot_tokens(texts):
    """Sorted list of [..] slot tokens found across the given strings."""
    return sorted(token for text in texts for token in SLOT_RE.findall(text))
