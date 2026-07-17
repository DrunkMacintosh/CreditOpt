from deck.compliance import slot_tokens, spec_strings
from deck.content import SLIDES, DISCLAIMER_SLIDES, LAYOUTS


def test_eighteen_slides_numbered_in_order():
    assert [s["n"] for s in SLIDES] == list(range(1, 19))


def test_required_fields():
    for s in SLIDES:
        assert s["title"].strip(), f"slide {s['n']} missing title"
        assert s["layout"] in LAYOUTS, f"slide {s['n']} bad layout {s['layout']}"
        assert isinstance(s["disclaimer"], bool)


def test_disclaimer_flags_match_spec():
    flagged = {s["n"] for s in SLIDES if s["disclaimer"]}
    assert flagged == DISCLAIMER_SLIDES == {1, 4, 5, 6, 8, 13}


def test_input_slots_only_where_expected():
    # Slots [..] are deliberate data slots (spec 3.3): metrics 13/15, team 17,
    # QR 18, screenshot labels 4/6/8. Nowhere else.
    with_slots = {s["n"] for s in SLIDES if slot_tokens(spec_strings(s))}
    assert with_slots == {4, 6, 8, 13, 15, 17, 18}


def test_phrasing_rule_cho_shb():
    all_text = str(SLIDES)
    assert "đầu tiên cho SHB" in all_text
    assert "đầu tiên của SHB" not in all_text


def test_em_dash_always_spaced():
    # Guards against transcription drift: every em dash in final copy is " — ".
    for s in SLIDES:
        for text in spec_strings(s):
            # A lone "—" is a deliberate table-cell "not applicable" marker
            # (spec §4 slide 11 compare_table), not a prose em dash needing
            # surrounding spaces.
            if text == "—":
                continue
            for i, ch in enumerate(text):
                if ch == "—":
                    assert 0 < i < len(text) - 1, f"slide {s['n']}: em dash at edge in {text!r}"
                    assert text[i - 1] == " " and text[i + 1] == " ", \
                        f"slide {s['n']}: unspaced em dash in {text!r}"
