"""Draw measured, paginated content onto a real PDF canvas."""
from __future__ import annotations

import io

from reportlab.pdfgen import canvas

from .layout import (
    CONTENT_WIDTH,
    MARGIN,
    NOTE_GAP,
    NOTE_INDENT,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    RULE_GAP,
    RULE_WIDTH,
    Paragraph,
    footnote_block_height,
)
from .measure import (
    BODY_LEADING,
    BODY_SIZE,
    FONT_NAME,
    MARKER_RISE,
    MARKER_SIZE,
    NOTE_LEADING,
    NOTE_SIZE,
    marker_width,
    register_font,
)


def _dest_ref(fid: str) -> str:
    return f"fn_{fid}"


def _dest_marker(fid: str) -> str:
    return f"ref_{fid}"


def render_pdf(paragraphs: list[Paragraph], note_lines, pages, order) -> bytes:
    register_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    c.setTitle("Repair Manual")
    c.setAuthor("Manual Service")

    top = PAGE_HEIGHT - MARGIN
    bottom = MARGIN

    back_dest_made: set[str] = set()
    for page_index, page in enumerate(pages):
        y = top - BODY_SIZE

        for pi, li in page.body:
            x = MARGIN
            line = paragraphs[pi].lines[li]
            for kind, value, width in line.runs:
                if kind == "space":
                    c.setFont(FONT_NAME, BODY_SIZE)
                    x += width
                elif kind == "word":
                    c.setFont(FONT_NAME, BODY_SIZE)
                    c.drawString(x, y, value)
                    x += width
                else:
                    number = order[value]
                    label = str(number)
                    mw = marker_width(number)
                    c.setFont(FONT_NAME, MARKER_SIZE)
                    first = f"{page_index}_{pi}_{li}_{x:.2f}"
                    c.drawString(x, y + MARKER_RISE, label)
                    rect = (x, y - 2, x + mw, y + MARKER_SIZE + MARKER_RISE)
                    c.linkAbsolute("", _dest_ref(value), Rect=rect, name=f"lk_{first}")
                    if value not in back_dest_made:
                        c.bookmarkHorizontalAbsolute(_dest_marker(value), y + 6)
                        back_dest_made.add(value)
                    x += mw
            y -= BODY_LEADING

        if page.footnotes:
            counts = {fid: len(note_lines[fid]) for fid in page.footnotes}
            block = footnote_block_height(counts)
            block_top = bottom + block
            rule_y = block_top - RULE_GAP + 2
            c.setLineWidth(0.5)
            c.line(MARGIN, rule_y, MARGIN + RULE_WIDTH, rule_y)

            ny = rule_y - NOTE_LEADING + 2
            for fid in page.footnotes:
                number = order[fid]
                label = f"{number}"
                c.setFont(FONT_NAME, NOTE_SIZE)
                label_w = c.stringWidth(label + " ", FONT_NAME, NOTE_SIZE)
                lx = MARGIN + NOTE_INDENT - label_w
                c.bookmarkHorizontalAbsolute(_dest_ref(fid), ny + 3)
                c.drawString(lx, ny, label)
                c.linkAbsolute(
                    "",
                    _dest_marker(fid),
                    Rect=(lx, ny - 2, lx + label_w, ny + NOTE_SIZE),
                    name=f"fnlk_{fid}_{page_index}",
                )

                tx = MARGIN + NOTE_INDENT
                for index, line in enumerate(note_lines[fid]):
                    fx = MARGIN + NOTE_INDENT if index > 0 else tx
                    for kind, value, width in line.runs:
                        if kind == "space":
                            fx += width
                        else:
                            c.setFont(FONT_NAME, NOTE_SIZE)
                            c.drawString(fx, ny, value)
                            fx += width
                    ny -= NOTE_LEADING
                ny -= NOTE_GAP

        c.setFont(FONT_NAME, NOTE_SIZE)
        page_no = str(page_index + 1)
        c.drawCentredString(PAGE_WIDTH / 2, MARGIN / 2 - 2, page_no)
        c.showPage()

    c.save()
    return buf.getvalue()
