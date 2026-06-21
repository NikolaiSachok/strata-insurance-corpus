"""Top-level corpus manifest.

``manifest.json`` lists every emitted document with its provenance, so a consumer
(or ``validate.py``) can resolve any ``doc_id`` to a file + the facts it asserts.
Written with sorted keys for a stable diff.
"""

from __future__ import annotations

import json
from pathlib import Path


def write_manifest(outdir: Path, model_meta: dict, records: list) -> Path:
    outdir = Path(outdir)
    docs = [r.to_obj() for r in records]
    docs.sort(key=lambda d: d["doc_id"])
    manifest = {
        "company": model_meta.get("company"),
        "marker": model_meta.get("marker"),
        "synthetic": True,
        "seed": model_meta.get("seed"),
        "profile": model_meta.get("profile"),
        "generator_version": model_meta.get("generator_version"),
        "counts": {
            **model_meta.get("counts", {}),
            "documents": len(docs),
        },
        "documents": docs,
    }
    path = outdir / "manifest.json"
    path.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return path
