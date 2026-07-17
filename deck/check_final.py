"""Finalization gate: fails while any [..] input slot remains in the deck.

Usage: python deck/check_final.py [path-to-pptx]
Run before submission. Exit 0 = ready; exit 1 = slots remain (listed).
"""
import re
import sys

from pptx import Presentation


def remaining_slots(path):
    prs = Presentation(path)
    found = []
    for idx, slide in enumerate(prs.slides, start=1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        texts.append(cell.text)
        for token in re.findall(r"\[[^\]]+\]", "\n".join(texts)):
            found.append((idx, token))
    return found


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "deck/output/deck.pptx"
    slots = remaining_slots(path)
    if not slots:
        print(f"OK: {path} contains no remaining input slots.")
        return 0
    print(f"NOT FINAL: {len(slots)} input slot(s) remain in {path}:")
    for idx, token in slots:
        print(f"  slide {idx}: {token}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
