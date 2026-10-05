# Repair Manual PDF Service

Pure-backend service (Python 3.10.12, FastAPI 0.115.12, ReportLab 4.4.5)
that renders an English repair manual PDF with true same-page footnotes.

## Run

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Generate the bundled multi-page example:

```bash
curl -sS -X POST http://127.0.0.1:8000/manual.pdf \
  -H 'Content-Type: application/json' \
  --data @examples/sample_request.json -o /tmp/manual.pdf
```

## Request format

`POST /manual.pdf` accepts JSON:

```json
{
  "paragraphs": [
    [
      {"type": "text", "text": "Disconnect power."},
      {"type": "ref", "ref": "safety"}
    ]
  ],
  "footnotes": {"safety": "Lock out the breaker first."}
}
```

- `paragraphs` is an ordered list; each paragraph is an ordered list of items.
- A `text` item holds literal text. HTML is not interpreted. Only printable
  ASCII (plus tab/CR/LF) is accepted.
- A `ref` item inserts a superscript footnote marker. The id must exist in
  `footnotes`; unknown ids are rejected (HTTP 422).
- Empty paragraphs, empty/whitespace footnotes and whitespace-only paragraphs
  are rejected.
- At most 100 paragraphs and 20000 characters of text (body + footnotes).
- Footnotes that are never referenced are validated but never printed.

## Layout rules

- A4, single column, 20 mm margins; body 11 pt / 15 pt leading; footnotes
  9 pt / 12 pt leading; page number centered at the bottom.
- Line breaking uses real DejaVuSerif glyph widths. Whole words are preferred;
  words wider than the frame are character-split. The superscript marker
  occupies its measured width, so lines never overflow or drop characters.
- Footnotes are numbered 1.. by first reference order; repeats reuse the
  number. A footnote is typeset once, fully, at the bottom of the page of its
  first reference, separated by a rule, and never splits across pages.
- The footnote area is deducted from that page body capacity; when a line plus
  its new footnote no longer fits, the line, citation and footnote move to the
  next page. Paragraph splits keep at least two lines on each page (single-line
  paragraphs excepted). If a citation and its footnote cannot fit even on an
  empty page, the request is rejected with HTTP 422 rather than clipped.
- The embedded DejaVuSerif font keeps all text searchable. Clicking a body
  marker jumps to the footnote; clicking the footnote number returns to the
  first reference.

## Tests

```bash
.venv/bin/python -m pytest -q
```
