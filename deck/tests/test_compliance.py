import pytest
from pptx import Presentation

from deck.compliance import FORBIDDEN, slot_tokens, spec_strings
from deck.content import DISCLAIMER_SLIDES, SLIDES
from deck.theme import DISCLAIMER_VN, DISCLAIMER_EN


@pytest.fixture(scope="session")
def prs():
    from deck.build import build_deck
    return Presentation(build_deck("deck/output/test_deck.pptx"))


def slide_text(slide):
    parts = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            parts.append(shape.text_frame.text)
        if shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    parts.append(cell.text)
    return "\n".join(parts)


def test_disclaimer_on_required_slides(prs):
    for idx, slide in enumerate(prs.slides, start=1):
        if idx in DISCLAIMER_SLIDES:
            text = slide_text(slide)
            assert DISCLAIMER_VN in text, f"slide {idx}: VN disclaimer missing"
            assert DISCLAIMER_EN in text, f"slide {idx}: EN disclaimer missing"


def test_no_forbidden_claims(prs):
    for idx, slide in enumerate(prs.slides, start=1):
        text = slide_text(slide).lower()
        for phrase in FORBIDDEN:
            assert phrase.lower() not in text, f"slide {idx}: forbidden '{phrase}'"


def test_rendered_slots_match_content_slots(prs):
    # The render pipeline must surface exactly the [..] slots that content.py
    # defines for each slide — no slot silently dropped by a layout, none
    # invented. Stays green when the team legitimately fills real values in
    # content.py, because both sides change together.
    for spec, slide in zip(SLIDES, prs.slides):
        expected = slot_tokens(spec_strings(spec))
        rendered = slot_tokens([slide_text(slide)])
        assert rendered == expected, f"slide {spec['n']}: {rendered} != {expected}"
