"""Eval harness (#15): metric math is correct and the oracle run scores perfectly."""

from __future__ import annotations

import math

from generator.eval import (
    evaluate,
    exact_match,
    ndcg_at_k,
    normalize,
    oracle_predictions,
    recall_at_k,
    token_f1,
)


def test_normalize_and_exact_match():
    assert normalize("  Burglary\tLOSS ") == "burglary loss"
    assert exact_match("Burglary ", "burglary") == 1.0
    assert exact_match("€3,525.00", "€3,525.00") == 1.0
    assert exact_match("theft", "burglary") == 0.0


def test_recall_at_k():
    rel = {"a", "b"}
    assert recall_at_k(rel, ["a", "c", "b"], 1) == 0.5  # only a in top-1, of 2 relevant
    assert recall_at_k(rel, ["a", "c", "b"], 2) == 0.5
    assert recall_at_k(rel, ["a", "c", "b"], 3) == 1.0
    assert recall_at_k(rel, [], 5) == 0.0
    assert recall_at_k({"a"}, ["a"], 1) == 1.0


def test_ndcg_at_k():
    # relevant {a,b}; retrieved [a,c,b]: DCG = 1/log2(2) + 1/log2(4); IDCG = 1/log2(2) + 1/log2(3)
    dcg = 1 / math.log2(2) + 1 / math.log2(4)
    idcg = 1 / math.log2(2) + 1 / math.log2(3)
    assert abs(ndcg_at_k({"a", "b"}, ["a", "c", "b"], 3) - dcg / idcg) < 1e-9
    assert ndcg_at_k({"a"}, ["a"], 5) == 1.0  # perfect rank
    assert ndcg_at_k({"a"}, ["x", "y"], 5) == 0.0  # not retrieved
    # a repeated doc is one ranked result — metrics must never exceed 1.0 (textbook dedup)
    assert ndcg_at_k({"a"}, ["a", "a", "a"], 5) == 1.0
    assert recall_at_k({"a", "b"}, ["a", "a", "b"], 2) == 1.0  # distinct ranking [a,b] fits top-2


def test_token_f1():
    assert token_f1("burglary", "burglary") == 1.0
    assert token_f1("the quick brown", "quick brown fox") == 2 / 3  # 2 overlap, p=g=3 tokens
    assert token_f1("", "burglary") == 0.0
    assert token_f1("totally wrong", "burglary loss") == 0.0


def test_evaluate_missing_prediction_scores_zero_and_breaks_down_by_class():
    golden = [
        {"id": "Q1", "answer": "burglary", "relevant_doc_ids": ["D1"], "query_class": "semantic"},
        {"id": "Q2", "answer": "€10.00", "relevant_doc_ids": ["D2", "D3"], "query_class": "aggregation"},
    ]
    predictions = {
        "Q1": {"retrieved_doc_ids": ["D1", "Dx"], "answer": "burglary"},
        # Q2 has NO prediction -> all zeros
    }
    m = evaluate(golden, predictions, ks=(1, 5))
    assert m["n_questions"] == 2 and m["n_with_prediction"] == 1
    assert m["by_class"]["semantic"]["recall@1"] == 1.0
    assert m["by_class"]["semantic"]["exact_match"] == 1.0
    assert m["by_class"]["aggregation"]["recall@5"] == 0.0  # unanswered
    assert m["by_class"]["aggregation"]["exact_match"] == 0.0
    # overall recall@1 = mean(1.0, 0.0) = 0.5
    assert m["overall"]["recall@1"] == 0.5
    # rows without a modality group under "text"; the breakdown is a partition of the same questions
    assert set(m["by_modality"]) == {"text"}
    assert m["by_modality"]["text"]["recall@1"] == m["overall"]["recall@1"]


def test_oracle_scores_perfectly_on_sample_golden():
    import json
    import pathlib

    golden = [json.loads(l) for l in pathlib.Path("sample/golden.jsonl").read_text().splitlines() if l.strip()]
    m = evaluate(golden, oracle_predictions(golden), ks=(1, 5, 10))
    assert m["n_with_prediction"] == m["n_questions"]
    # a perfect run: answers exact, retrieval ideal -> EM/F1/nDCG and recall at K>=max(|relevant|) are 1.0
    assert m["overall"]["exact_match"] == 1.0
    assert m["overall"]["token_f1"] == 1.0
    assert m["overall"]["ndcg@10"] == 1.0
    assert m["overall"]["recall@10"] == 1.0
    # recall@1 < 1.0 because many questions have 2 relevant docs (only one fits in the top-1)
    assert m["overall"]["recall@1"] < 1.0
