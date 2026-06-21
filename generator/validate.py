"""Validate a generated corpus.

Checks (exit non-zero on any failure):
  * model.json present and self-consistent (every FK resolves);
  * every manifest document file exists and its sha256 matches;
  * every golden question's relevant_doc_ids resolve to manifest documents;
  * roster covers every model entity.

    python -m generator.validate --out corpus/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .provenance import sha256_file


def _load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(out: Path) -> tuple[bool, list[str]]:
    out = Path(out)
    errors: list[str] = []

    model_path = out / "model.json"
    manifest_path = out / "manifest.json"
    roster_path = out / "roster.tsv"
    golden_path = out / "golden.jsonl"

    for required in (model_path, manifest_path, roster_path):
        if not required.exists():
            errors.append(f"missing required file: {required}")
    if errors:
        return False, errors

    model = _load_json(model_path)
    manifest = _load_json(manifest_path)

    # --- referential integrity of the model -------------------------------- #
    holder_ids = {h["id"] for h in model["policyholders"]}
    agent_ids = {a["id"] for a in model["agents"]}
    adjuster_ids = {a["id"] for a in model["adjusters"]}
    policy_ids = {p["id"] for p in model["policies"]}

    for p in model["policies"]:
        if p["holder_id"] not in holder_ids:
            errors.append(f"policy {p['id']}: holder_id {p['holder_id']} not in model")
        if p["agent_id"] not in agent_ids:
            errors.append(f"policy {p['id']}: agent_id {p['agent_id']} not in model")
    for c in model["claims"]:
        if c["policy_id"] not in policy_ids:
            errors.append(f"claim {c['id']}: policy_id {c['policy_id']} not in model")
        if c["adjuster_id"] not in adjuster_ids:
            errors.append(f"claim {c['id']}: adjuster_id {c['adjuster_id']} not in model")

    # --- roster covers every entity ---------------------------------------- #
    roster_ids = set()
    lines = roster_path.read_text(encoding="utf-8").splitlines()
    for line in lines[1:]:  # skip header
        if line.strip():
            roster_ids.add(line.split("\t", 1)[0])
    all_ids = holder_ids | agent_ids | adjuster_ids | policy_ids | {c["id"] for c in model["claims"]}
    missing = all_ids - roster_ids
    if missing:
        errors.append(f"roster missing {len(missing)} entity rows (e.g. {sorted(missing)[:3]})")

    # --- manifest documents exist + sha matches ---------------------------- #
    doc_ids = set()
    for d in manifest["documents"]:
        doc_ids.add(d["doc_id"])
        # Generated images whose pixels aren't rendered in this corpus (only the prompt-spec
        # is committed) have no file to check — they must still carry a prompt_spec, though.
        if d.get("is_generated") and not d.get("rendered", True):
            if not d.get("prompt_spec"):
                errors.append(f"document {d['doc_id']}: unrendered generated image has no prompt_spec")
            continue
        fpath = out / d["path"]
        if not fpath.exists():
            errors.append(f"document {d['doc_id']}: file missing at {d['path']}")
            continue
        if d.get("sha256"):
            actual = sha256_file(fpath)
            if actual != d["sha256"]:
                errors.append(f"document {d['doc_id']}: sha256 mismatch ({actual[:8]} != {d['sha256'][:8]})")

    # --- scanned variants reference a real source document ----------------- #
    for d in manifest["documents"]:
        src = d.get("scanned_of")
        if src and src not in doc_ids:
            errors.append(f"document {d['doc_id']}: scanned_of {src} not in manifest")

    # --- golden questions resolve ------------------------------------------ #
    n_golden = 0
    if golden_path.exists():
        for i, raw in enumerate(golden_path.read_text(encoding="utf-8").splitlines()):
            if not raw.strip():
                continue
            n_golden += 1
            q = json.loads(raw)
            for did in q.get("relevant_doc_ids", []):
                if did not in doc_ids:
                    errors.append(f"golden {q.get('id', i)}: relevant_doc_id {did} not in manifest")

    ok = not errors
    if ok:
        print(
            f"[validate] OK — {out}: "
            f"{len(all_ids)} entities, {len(manifest['documents'])} documents, {n_golden} golden questions"
        )
    return ok, errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="generator.validate")
    ap.add_argument("--out", type=Path, default=Path("corpus"))
    args = ap.parse_args(argv)
    ok, errors = validate(args.out)
    if not ok:
        print(f"[validate] FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
