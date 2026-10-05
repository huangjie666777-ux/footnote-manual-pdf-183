"""Request models and strict input validation.

Only ASCII printable text is accepted (space through tilde plus the
normal whitespace characters space, tab and CR/LF inside the value).
"""
from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field, model_validator

MAX_TEXT_CHARS = 20_000
MAX_PARAGRAPHS = 100


class ValidationError(Exception):
    """Raised for content that must be rejected with HTTP 422."""


class TextItem(BaseModel):
    type: Literal["text"]
    text: str = Field(default="")


class RefItem(BaseModel):
    type: Literal["ref"]
    ref: str


Item = Union[TextItem, RefItem]


class ManualRequest(BaseModel):
    paragraphs: list[list[Item]]
    footnotes: dict[str, str]


def _is_printable_ascii(value: str) -> bool:
    for ch in value:
        if ch in "\t\r\n":
            continue
        if not (32 <= ord(ch) <= 126):
            return False
    return True


def validate_request(req: ManualRequest) -> None:
    if len(req.paragraphs) > MAX_PARAGRAPHS:
        raise ValidationError(
            f"too many paragraphs: {len(req.paragraphs)} > {MAX_PARAGRAPHS}"
        )
    if not req.paragraphs:
        raise ValidationError("at least one paragraph is required")
    for fn_id, fn_text in req.footnotes.items():
        if not _is_printable_ascii(fn_id):
            raise ValidationError(f"footnote id {fn_id!r} is not printable ASCII")
        if not fn_text or not fn_text.strip():
            raise ValidationError(f"footnote {fn_id!r} is empty")
        if not _is_printable_ascii(fn_text):
            raise ValidationError(f"footnote {fn_id!r} contains non-ASCII text")

    total = 0
    for pi, paragraph in enumerate(req.paragraphs):
        if not paragraph:
            raise ValidationError(f"paragraph {pi} is empty")
        para_text = ""
        for item in paragraph:
            if isinstance(item, TextItem):
                if not _is_printable_ascii(item.text):
                    raise ValidationError(
                        f"paragraph {pi} contains non-ASCII printable text"
                    )
                para_text += item.text
            else:
                if item.ref not in req.footnotes:
                    raise ValidationError(
                        f"paragraph {pi} references unknown footnote {item.ref!r}"
                    )
        if not para_text.strip():
            raise ValidationError(f"paragraph {pi} is empty")
        total += len(para_text)

    total += sum(len(text) for text in req.footnotes.values())
    if total > MAX_TEXT_CHARS:
        raise ValidationError(
            f"total text too long: {total} > {MAX_TEXT_CHARS} characters"
        )
