"""Provenance: record which entity/field each document asserts.

Every emitted document carries a provenance block — the list of (entity, field,
value) facts the document expresses. This is what makes the golden eval knowable
by construction: a golden question's answer is one of these recorded values, and
its supporting doc is the one whose provenance asserts it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Assertion:
    entity_id: str
    field: str
    value: str


@dataclass
class DocRecord:
    doc_id: str
    doc_type: str  # policy_contract | fnol | ...
    format: str  # pdf | docx | xlsx | png | ...
    path: str  # relative to the corpus root
    entity_ids: list  # every entity this doc is "about"
    asserts: list = field(default_factory=list)  # list[Assertion]
    is_scanned: bool = False
    synthetic: bool = True
    sha256: str = ""

    def to_obj(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "format": self.format,
            "path": self.path,
            "entity_ids": self.entity_ids,
            "is_scanned": self.is_scanned,
            "synthetic": self.synthetic,
            "sha256": self.sha256,
            "provenance": [{"entity_id": a.entity_id, "field": a.field, "value": a.value} for a in self.asserts],
        }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()
