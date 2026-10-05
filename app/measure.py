"""Font metrics and word-wrap based on real DejaVuSerif glyph widths."""
from __future__ import annotations

import os
from dataclasses import dataclass

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_NAME = "DejaVuSerif"
FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "fonts", "DejaVuSerif.ttf")

BODY_SIZE = 11.0
BODY_LEADING = 15.0
NOTE_SIZE = 9.0
NOTE_LEADING = 12.0


def register_font() -> str:
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, os.path.abspath(FONT_PATH)))
    return FONT_NAME


def string_width(text: str, size: float) -> float:
    return pdfmetrics.stringWidth(text, FONT_NAME, size)


# A superscript marker occupies its real width: ~64.5% of the normal digit
# width, raised 3.2pt, at 7pt.
MARKER_SIZE = 7.0
MARKER_RISE = 3.2


def marker_width(number: int) -> float:
    return pdfmetrics.stringWidth(str(number), FONT_NAME, MARKER_SIZE)


@dataclass
class Atom:
    kind: str  # "text" or "ref"
    value: str


@dataclass
class Line:
    runs: list[tuple[str, str, float]]  # (kind, value, width)
    width: float


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    current = ""
    for ch in text:
        if ch == " ":
            if current:
                tokens.append(current)
                current = ""
            tokens.append(" ")
        else:
            current += ch
    if current:
        tokens.append(current)
    return tokens


def wrap_atoms(atoms: list[Atom], max_width: float, size: float,
               marker_numbers: dict[str, int]) -> list[Line]:
    """Greedy wrap. Whitespace tokens attach to the preceding word; whole
    words are preferred, over-wide words are character split. A reference
    marker is an unbreakable inline run sized by its real glyph width."""
    runs: list[tuple[str, str, float]] = []
    for atom in atoms:
        if atom.kind == "ref":
            width = marker_width(marker_numbers[atom.value])
            runs.append(("ref", atom.value, width))
        else:
            for token in _tokenize(atom.value):
                if token == " ":
                    runs.append(("space", " ", string_width(" ", size)))
                else:
                    width = string_width(token, size)
                    if width <= max_width:
                        runs.append(("word", token, width))
                    else:
                        piece = ""
                        piece_w = 0.0
                        for ch in token:
                            ch_w = string_width(ch, size)
                            if piece and piece_w + ch_w > max_width:
                                runs.append(("word", piece, piece_w))
                                piece = ch
                                piece_w = ch_w
                            else:
                                piece += ch
                                piece_w += ch_w
                        if piece:
                            runs.append(("word", piece, piece_w))

    lines: list[Line] = []
    current: list[tuple[str, str, float]] = []
    used = 0.0

    def emit() -> None:
        nonlocal current, used
        trimmed = list(current)
        while trimmed and trimmed[-1][0] == "space":
            trimmed.pop()
        width = sum(run[2] for run in trimmed)
        lines.append(Line(trimmed, width))
        current = []
        used = 0.0

    for run in runs:
        kind, _, width = run
        if not current and kind == "space":
            continue
        if current and used + width > max_width:
            emit()
            if kind == "space":
                continue
        current.append(run)
        used += width
    if current:
        emit()
    return lines
