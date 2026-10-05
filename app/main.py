"""FastAPI application exposing the PDF rendering endpoint."""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.responses import Response

from .layout import LayoutError, build_layout
from .measure import Atom
from .models import ManualRequest, RefItem, TextItem, ValidationError, validate_request
from .renderer import render_pdf

app = FastAPI(title="Repair Manual PDF", version="1.0.0")


@app.exception_handler(ValidationError)
async def validation_handler(_request, exc: ValidationError):
    return Response(
        content=json.dumps({"detail": exc.args[0]}),
        status_code=422,
        media_type="application/json",
    )


@app.exception_handler(LayoutError)
async def layout_handler(_request, exc: LayoutError):
    return Response(
        content=json.dumps({"detail": exc.args[0]}),
        status_code=422,
        media_type="application/json",
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/manual.pdf")
async def render_manual(req: ManualRequest):
    validate_request(req)
    atoms: list[list[Atom]] = []
    for paragraph in req.paragraphs:
        para_atoms: list[Atom] = []
        for item in paragraph:
            if isinstance(item, TextItem):
                para_atoms.append(Atom("text", item.text))
            else:
                para_atoms.append(Atom("ref", item.ref))
        atoms.append(para_atoms)

    paragraphs, note_lines, pages, order = build_layout(atoms, req.footnotes)
    pdf = render_pdf(paragraphs, note_lines, pages, order)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=manual.pdf"},
    )
