"""Determinism + integrity tests for the generator (the non-negotiable contract).

Same seed -> byte-stable structured output; different seed -> different output;
the model is referentially consistent and the roster covers every entity.
"""

from __future__ import annotations

from generator.model import (
    PROFILES,
    build_model,
    index,
    roster_rows,
    to_json_bytes,
    to_roster_bytes,
)


def test_model_json_byte_stable():
    for profile in PROFILES:
        a = to_json_bytes(build_model(42, profile))
        b = to_json_bytes(build_model(42, profile))
        assert a == b, f"model.json not byte-stable for profile={profile}"


def test_roster_byte_stable():
    a = to_roster_bytes(build_model(7, "sample"))
    b = to_roster_bytes(build_model(7, "sample"))
    assert a == b


def test_seed_sensitive():
    assert to_json_bytes(build_model(42, "full")) != to_json_bytes(build_model(43, "full"))


def test_counts_match_profile():
    for profile, counts in PROFILES.items():
        m = build_model(1, profile)
        assert len(m.policyholders) == counts["holders"]
        assert len(m.policies) == counts["policies"]
        assert len(m.claims) == counts["claims"]


def test_referential_integrity():
    m = build_model(99, "full")
    idx = index(m)
    for p in m.policies:
        assert p.holder_id in idx["policyholders"]
        assert p.agent_id in idx["agents"]
    for c in m.claims:
        assert c.policy_id in idx["policies"]
        assert c.adjuster_id in idx["adjusters"]
        # claim date_of_loss falls inside its policy term
        policy = idx["policies"][c.policy_id]
        assert policy.effective_date <= c.date_of_loss <= policy.expiry_date


def test_roster_covers_every_entity():
    m = build_model(3, "sample")
    roster_ids = {r[0] for r in roster_rows(m)}
    expected = (
        {h.id for h in m.policyholders}
        | {a.id for a in m.agents}
        | {a.id for a in m.adjusters}
        | {p.id for p in m.policies}
        | {c.id for c in m.claims}
    )
    assert expected <= roster_ids


def test_contract_docx_byte_stable(tmp_path):
    """The .docx renderer must be byte-reproducible (normalized zip + pinned dates)."""
    from generator.content import contract_document
    from generator.render.docx import write_contract_docx

    m = build_model(42, "slice")
    policy = m.policies[0]
    holder = index(m)["policyholders"][policy.holder_id]
    ctx = contract_document(m.meta, policy, holder)

    a = tmp_path / "a.docx"
    b = tmp_path / "b.docx"
    write_contract_docx(ctx, a)
    write_contract_docx(ctx, b)
    assert a.read_bytes() == b.read_bytes()
    # and it's a valid OOXML package
    import zipfile

    assert "word/document.xml" in zipfile.ZipFile(a).namelist()


def test_synthetic_markers_present():
    m = build_model(5, "slice")
    assert m.meta["synthetic"] is True
    assert "SYNTHETIC" in m.meta["marker"]
    # synthetic tax id uses the never-issued "9" area prefix
    for h in m.policyholders:
        assert h.synthetic_tax_id.startswith("9")
