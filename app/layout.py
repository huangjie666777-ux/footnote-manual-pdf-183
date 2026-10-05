"""Footnoted pagination.

The body is measured first. Each page starts with the full text frame and
as soon as the first reference is placed on the page the complete footnote
block is reserved at the bottom, shrinking the body frame. If the next line
no longer fits after reserving its footnote, pagination is rolled back and
the citation moves to the next page together with the footnote.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .measure import (
    BODY_LEADING,
    NOTE_LEADING,
    Line,
    Atom,
    wrap_atoms,
)


class LayoutError(Exception):
    """Content cannot fit even on a fresh page."""


MM = 72.0 / 25.4
PAGE_WIDTH = 210.0 * MM
PAGE_HEIGHT = 297.0 * MM
MARGIN = 20.0 * MM

CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
CONTENT_HEIGHT = PAGE_HEIGHT - 2 * MARGIN

NOTE_INDENT = 12.0
NOTE_GAP = 4.0
RULE_WIDTH = 50.0
RULE_GAP = 8.0
FOOT_BOTTOM_PAD = 2.0


@dataclass
class Paragraph:
    atoms: list[Atom]
    lines: list[Line]


@dataclass
class Page:
    body: list[tuple[int, int]] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)


def footnote_block_height(note_line_counts: dict[str, int]) -> float:
    if not note_line_counts:
        return 0.0
    total = sum(cnt * NOTE_LEADING for cnt in note_line_counts.values())
    total += NOTE_GAP * (len(note_line_counts) - 1)
    return RULE_GAP + total + FOOT_BOTTOM_PAD


def paginate(paragraphs: list[Paragraph], note_lines: dict[str, list[Line]],
             order: dict[str, int]) -> list[Page]:
    pages: list[Page] = []
    page = Page()
    body_count = 0
    seen: set[str] = set()

    def refs_at(pi: int, li: int) -> list[str]:
        return [v for kind, v, _ in paragraphs[pi].lines[li].runs if kind == "ref"]

    def fits(pi: int, li: int, count: int, notes: set[str]) -> bool:
        extra = {rid for rid in refs_at(pi, li) if rid not in seen or rid not in notes}
        trial = set(notes) | (set(refs_at(pi, li)) - seen)
        reserve = footnote_block_height(
            {fid: len(note_lines[fid]) for fid in trial}
        )
        return (count + 1) * BODY_LEADING + reserve <= CONTENT_HEIGHT

    def commit(pi: int, li: int) -> None:
        nonlocal body_count
        page.body.append((pi, li))
        body_count += 1
        for rid in refs_at(pi, li):
            if rid not in seen:
                seen.add(rid)
                page.footnotes.append(rid)

    def flush() -> None:
        nonlocal page, body_count
        pages.append(page)
        page = Page()
        body_count = 0

    for pi, para in enumerate(paragraphs):
        start = 0
        total = len(para.lines)
        while start < total:
            candidate = start
            trial_notes = set(page.footnotes)
            while candidate < total and fits(pi, candidate, candidate - start + body_count, trial_notes):
                trial_notes |= set(refs_at(pi, candidate)) - seen
                candidate += 1

            taken = candidate - start
            left = total - candidate

            if left == 0:
                for li in range(start, candidate):
                    commit(pi, li)
                start = total
                continue

            if taken == 0:
                if body_count > 0:
                    flush()
                    continue
                raise LayoutError(
                    f"paragraph {pi} line {start} with its required footnote "
                    "does not fit on a single page"
                )

            if taken >= 2 and left >= 2:
                for li in range(start, candidate):
                    commit(pi, li)
                flush()
                start = candidate
                continue

            if body_count > 0:
                flush()
                continue

            raise LayoutError(
                f"paragraph {pi} cannot be split while keeping at least two "
                "lines on each page together with the required footnotes"
            )

    if pages or page.body:
        if page.body:
            flush()
    for p in pages:
        p.footnotes.sort(key=lambda fid: order[fid])
    return pages


def build_layout(req_atoms: list[list[Atom]], footnotes: dict[str, str]):
    from .measure import register_font

    register_font()
    order: dict[str, int] = {}
    for atoms in req_atoms:
        for atom in atoms:
            if atom.kind == "ref" and atom.value not in order:
                order[atom.value] = len(order) + 1

    paragraphs = [
        Paragraph(atoms, wrap_atoms(atoms, CONTENT_WIDTH, 11.0, order))
        for atoms in req_atoms
    ]
    note_lines: dict[str, list[Line]] = {}
    from .measure import NOTE_SIZE, string_width

    for fid, text in footnotes.items():
        if fid not in order:
            continue
        number = order[fid]
        prefix = f"{number} "
        first_width = CONTENT_WIDTH - NOTE_INDENT - string_width(prefix, NOTE_SIZE)
        rest_width = CONTENT_WIDTH - NOTE_INDENT
        first = wrap_atoms([Atom("text", text)], first_width, NOTE_SIZE, order)
        fit = "".join(value for kind, value, _ in first[0].runs if kind == "word")
        fit_with_spaces = "".join(value for _, value, _ in first[0].runs)
        lines = [first[0]]
        consumed = len(fit_with_spaces.rstrip(" "))
        if consumed < len(text):
            remainder = text[consumed:].lstrip(" ")
            lines.extend(
                wrap_atoms([Atom("text", remainder)], rest_width, NOTE_SIZE, order)
            )
        note_lines[fid] = lines
    pages = paginate(paragraphs, note_lines, order)
    return paragraphs, note_lines, pages, order
