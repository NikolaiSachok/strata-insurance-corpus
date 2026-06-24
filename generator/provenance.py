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
    format: str  # pdf | docx | xlsx | png | jpg | ...
    path: str  # relative to the corpus root
    entity_ids: list  # every entity this doc is "about"
    asserts: list = field(default_factory=list)  # list[Assertion]
    is_scanned: bool = False
    synthetic: bool = True
    sha256: str = ""
    source_doc_id: str = ""  # for scanned variants: the clean doc this was rendered from
    is_generated: bool = False  # AI-generated image (non-deterministic pixels)
    rendered: bool = True  # for generated images: whether the pixel file exists in this corpus
    prompt_spec: dict | None = None  # for generated images: the committed reproducible recipe

    def to_obj(self) -> dict:
        obj = {
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
        if self.source_doc_id:
            obj["scanned_of"] = self.source_doc_id
        if self.is_generated:
            obj["is_generated"] = True
            obj["rendered"] = self.rendered
            if self.prompt_spec is not None:
                obj["prompt_spec"] = self.prompt_spec
        return obj


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def provenance_index(records: list) -> dict:
    """Invert per-document assertions into a queryable ``(entity_id, field) -> [(doc_id, value)]`` map.

    This is the spine the golden set is built on: a question about ``(entity, field)`` resolves to the
    documents that assert it (its supporting/relevant docs) and to the asserted value (its answer), so a
    golden answer is, by construction, exactly what its cited documents state. Entries are sorted by
    ``doc_id`` for determinism.
    """
    idx: dict[tuple, list] = {}
    for r in records:
        for a in r.asserts:
            idx.setdefault((a.entity_id, a.field), []).append((r.doc_id, a.value))
    for key in idx:
        idx[key].sort()
    return idx


def support_for(prov: dict, entity_id: str, field: str) -> tuple | None:
    """Resolve ``(entity_id, field)`` to ``(value, [doc_ids])`` via the provenance index, or ``None``.

    All documents asserting the same ``(entity, field)`` agree by construction; the shared value is the
    golden answer and every asserting document is a relevant/supporting doc.
    """
    entries = prov.get((entity_id, field))
    if not entries:
        return None
    values = {v for _, v in entries}
    if len(values) != 1:  # contradictory provenance would make the answer ambiguous
        raise ValueError(f"provenance for ({entity_id}, {field}) is not single-valued: {sorted(values)}")
    doc_ids = sorted({d for d, _ in entries})
    return next(iter(values)), doc_ids
