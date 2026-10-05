from fastapi.testclient import TestClient

from app.layout import CONTENT_WIDTH, LayoutError, build_layout
from app.main import app
from app.measure import Atom, register_font
from app.models import ManualRequest, ValidationError, validate_request
from app.renderer import render_pdf

register_font()
client = TestClient(app)


def _atoms(paras):
    out = []
    for para in paras:
        row = []
        for item in para:
            if item["type"] == "text":
                row.append(Atom("text", item["text"]))
            else:
                row.append(Atom("ref", item["ref"]))
        out.append(row)
    return out


def _build(paras, fns):
    return build_layout(_atoms(paras), fns)


def test_validation_rejects_bad_input():
    import pytest

    cases = [
        ([[{"type": "text", "text": "x"}, {"type": "ref", "ref": "n"}]], {}),
        ([[]], {"a": "note"}),
        ([[{"type": "text", "text": "   "}]], {"a": "note"}),
        ([[{"type": "text", "text": "caf\u00e9"}]], {"a": "note"}),
        ([[{"type": "text", "text": "x"}]], {"a": ""}),
    ]
    for paras, fns in cases:
        with pytest.raises(ValidationError):
            validate_request(ManualRequest(paragraphs=paras, footnotes=fns))


def test_limits():
    import pytest

    paras = [[{"type": "text", "text": "x"}] for _ in range(101)]
    with pytest.raises(ValidationError):
        validate_request(ManualRequest(paragraphs=paras, footnotes={}))


def test_footnote_numbering_by_first_use_and_only_once():
    paras = [
        [{"type": "text", "text": "first "}, {"type": "ref", "ref": "b"}],
        [{"type": "text", "text": "second "}, {"type": "ref", "ref": "a"}],
        [{"type": "text", "text": "repeat "}, {"type": "ref", "ref": "b"}],
    ]
    fns = {"a": "alpha", "b": "beta"}
    _, _, pages, order = _build(paras, fns)
    assert order == {"b": 1, "a": 2}
    rendered = [fid for page in pages for fid in page.footnotes]
    assert rendered.count("b") == 1
    assert rendered.count("a") == 1


def test_unreferenced_footnote_is_not_output():
    paras = [[{"type": "text", "text": "no notes here at all today"}]]
    _, _, pages, _ = _build(paras, {"x": "unused"})
    assert all(not p.footnotes for p in pages)


def test_long_word_split_never_overflows():
    paras = [[{"type": "text", "text": "A" * 400}]]
    paragraphs, _, _, _ = _build(paras, {})
    for para in paragraphs:
        for line in para.lines:
            assert line.width <= CONTENT_WIDTH + 0.01


def test_split_paragraph_keeps_two_lines_per_page():
    words = "gasket housing fastener manifold " * 120
    paras = [[{"type": "text", "text": words}]]
    paragraphs, _, pages, _ = _build(paras, {})
    total = len(paragraphs[0].lines)
    assert total > 2
    counts = [sum(1 for pi, _ in page.body if pi == 0) for page in pages]
    assert all(n >= 2 for n in counts)


def test_impossible_footnote_is_rejected():
    import pytest

    fns = {"big": ("warning word " * 700).strip()}
    paras = [[{"type": "text", "text": "x"}, {"type": "ref", "ref": "big"}]]
    with pytest.raises(LayoutError):
        _build(paras, fns)


def test_http_endpoint_returns_pdf():
    body = {
        "paragraphs": [
            [
                {"type": "text", "text": "Disconnect power before service."},
                {"type": "ref", "ref": "safety"},
            ]
        ],
        "footnotes": {"safety": "Lock out and tag out the main breaker."},
    }
    res = client.post("/manual.pdf", json=body)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"


def test_http_endpoint_rejects_unknown_ref():
    body = {
        "paragraphs": [[{"type": "ref", "ref": "missing"}]],
        "footnotes": {},
    }
    res = client.post("/manual.pdf", json=body)
    assert res.status_code == 422


def test_pdf_embeds_font_and_is_searchable():
    paras = [[{"type": "text", "text": "searchable unique token zyxwv"}]]
    paragraphs, note_lines, pages, order = _build(paras, {})
    pdf = render_pdf(paragraphs, note_lines, pages, order)
    assert b"DejaVuSerif" in pdf
    assert b"/FontFile" in pdf
    assert b"BT" in pdf
