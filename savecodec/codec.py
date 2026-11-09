"""Decode/encode ``SingleFileSaveDataV2`` and convert it to/from JSON."""

from __future__ import annotations

import json
from typing import Any

from .mp import MemoryPackError, Reader, Writer
from .schema import ROOT


def decode(data: bytes) -> Any:
    """Parse a MemoryPack save file into plain Python objects (dict/list/...)."""
    r = Reader(data)
    value = ROOT.read(r, ROOT.name)
    if r.pos != len(data):
        raise MemoryPackError(
            f"{len(data) - r.pos} trailing byte(s) at 0x{r.pos:X}: "
            "this is not a SingleFileSaveDataV2 file, or it uses a "
            "different version"
        )
    return value


def encode(value: Any) -> bytes:
    """Serialize Python objects produced by :func:`decode` back to bytes."""
    w = Writer()
    ROOT.write(w, value, ROOT.name)
    return w.getvalue()


def dumps(value: Any, indent: int | None = 2) -> str:
    """Serialize a decoded save as JSON text, without a trailing newline."""
    return json.dumps(value, ensure_ascii=False, indent=indent, allow_nan=True)


def to_json(value: Any, indent: int | None = 2) -> str:
    """Convert a decoded save into JSON text."""
    return dumps(value, indent=indent) + "\n"


def from_json(text: str) -> Any:
    """Parse JSON text and validate that it can be encoded as a save."""
    return json.loads(text)


def load_json_file(path: str) -> Any:
    """Read JSON text from *path*."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json_file(path: str, value: Any, indent: int | None = 2) -> None:
    """Write *value* to *path* as JSON text."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(to_json(value, indent=indent))
