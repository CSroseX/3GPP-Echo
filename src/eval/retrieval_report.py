"""Retrieval-only report: recall@5/@20, MRR, nDCG@10, strict and
prefix-credit, over every golden-set question with retrieval_scored=true.

Zero LLM tokens — this only exercises Retriever.search() against Qdrant,
never the generate/verify graph. Safe to re-run anytime Qdrant is live.

    python -m src.eval.retrieval_report
    python -m src.eval.retrieval_report --output eval/baselines/ablation_x.json

With --grades (a pooling grades.json; its grading_sheet.jsonl must sit next
to it), each question is also scored at chunk level: is a graded answer
chunk in the top 5 / 10? Results are broken down by 5G / 4G / trap.

    python -m src.eval.retrieval_report --golden eval/golden/golden_set.v2.json \\
        --grades eval/pooling/v2/grades.json --output eval/baselines/v2_x.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import get_settings
from src.eval.metrics import score_chunk_grades, score_question
from src.retrieval.retriever import Retriever

GOLDEN_SET_PATH = "eval/golden/golden_set.v1.json"
OUTPUT_PATH = "eval/baselines/retrieval_baseline.json"


def load_chunk_grades(grades_path: str) -> dict[int, dict[str, int]]:
    """{question_id: {chunk_id: grade}} for every pooled pair. grades.json is
    keyed by the sheet's grade_id and lists only non-zero grades, so every
    other sheet row is a judged 0. Any supplement*.jsonl next to it (chunks
    graded later, after a change surfaced them) is merged in."""
    with open(grades_path, "r", encoding="utf-8") as f:
        graded = json.load(f)
    sheet_path = os.path.join(os.path.dirname(grades_path), "grading_sheet.jsonl")
    out: dict[int, dict[str, int]] = {}
    with open(sheet_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            grade = graded["grades"].get(str(row["grade_id"]), {}).get("grade", graded["default_grade"])
            out.setdefault(row["question_id"], {})[row["chunk_id"]] = grade
    for path in sorted(glob.glob(os.path.join(os.path.dirname(grades_path), "supplement*.jsonl"))):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                out.setdefault(row["question_id"], {})[row["chunk_id"]] = row["grade"]
    return out


def question_group(q: dict) -> str:
    return "trap" if q.get("category") == "trap" else q.get("generation") or q.get("type", "?")


def main():
    parser = argparse.ArgumentParser(description="Zero-LLM-token retrieval report over the golden set.")
    parser.add_argument("--output", default=OUTPUT_PATH,
                        help="Where to write the report (default: the committed baseline).")
    parser.add_argument("--golden", default=GOLDEN_SET_PATH, help="Golden set to score against.")
    parser.add_argument("--grades", default=None,
                        help="Pooling grades.json for chunk-level scoring (optional).")
    args = parser.parse_args()
    output_path, golden_path = args.output, args.golden

    cfg = get_settings()

    with open(golden_path, "r", encoding="utf-8") as f:
        golden_set = json.load(f)
    chunk_grades = load_chunk_grades(args.grades) if args.grades else None

    scored_questions = [q for q in golden_set if q.get("retrieval_scored")]

    retriever = Retriever()
    candidate_k = cfg.rerank_multiplier * cfg.default_top_k

    per_question = []
    latencies_ms = []

    for q in scored_questions:
        start = time.perf_counter()
        # Rerank the same candidate pool the app uses at default_top_k, so
        # this list's top-5 is exactly what the app would return.
        results = retriever.search(q["question"], top_k=cfg.eval_top_k, candidate_k=candidate_k)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed_ms)

        metrics = score_question(results, q["gold_clauses"])
        if chunk_grades is not None:
            metrics["chunk"] = score_chunk_grades(results, chunk_grades.get(q["id"], {}))
        per_question.append({
            "id": q["id"],
            "group": question_group(q),
            "question": q["question"],
            "gold_clauses": q["gold_clauses"],
            "latency_ms": round(elapsed_ms, 1),
            "top_5": [f'{r["spec_id"]}/{r["clause_id"]}' for r in results[:5]],
            "top_5_chunk_ids": [r.get("chunk_id") for r in results[:5]],
            **metrics,
        })

    def mean(key_path):
        total, count = 0.0, 0
        for pq in per_question:
            node = pq
            for key in key_path:
                node = node[key]
            total += node
            count += 1
        return total / count if count else 0.0

    latencies_ms.sort()

    def percentile(data, pct):
        if not data:
            return 0.0
        idx = min(len(data) - 1, int(len(data) * pct))
        return round(data[idx], 1)

    summary = {
        "n_questions": len(per_question),
        "strict": {
            "mean_recall_at_5": round(mean(["strict", "recall_at_5"]), 4),
            "mean_recall_at_20": round(mean(["strict", "recall_at_20"]), 4),
            "mean_mrr": round(mean(["strict", "mrr"]), 4),
            "mean_ndcg_at_10": round(mean(["strict", "ndcg_at_10"]), 4),
        },
        "prefix_credit": {
            "mean_recall_at_5": round(mean(["prefix_credit", "recall_at_5"]), 4),
            "mean_recall_at_20": round(mean(["prefix_credit", "recall_at_20"]), 4),
            "mean_mrr": round(mean(["prefix_credit", "mrr"]), 4),
            "mean_ndcg_at_10": round(mean(["prefix_credit", "ndcg_at_10"]), 4),
        },
        "latency_ms": {
            "p50": percentile(latencies_ms, 0.50),
            "p95": percentile(latencies_ms, 0.95),
        },
    }

    if chunk_grades is not None:
        def count(rows, key):
            return f'{sum(pq["chunk"][key] for pq in rows)}/{len(rows)}'

        groups = sorted({pq["group"] for pq in per_question})
        summary["chunk_level"] = {
            "answer_at_5": count(per_question, "answer_at_5"),
            "answer_at_10": count(per_question, "answer_at_10"),
            "relevant_at_5": count(per_question, "relevant_at_5"),
            "answer_at_5_by_group": {
                g: count([pq for pq in per_question if pq["group"] == g], "answer_at_5") for g in groups
            },
            "unjudged_in_top_5": sum(pq["chunk"]["unjudged_in_top_5"] for pq in per_question),
        }

    report = {
        "golden_set_path": golden_path,
        "grades_path": args.grades,
        "config": {
            "default_top_k": cfg.default_top_k,
            "rerank_multiplier": cfg.rerank_multiplier,
            "candidate_k": candidate_k,
            "eval_top_k": cfg.eval_top_k,
            "embedding_model": cfg.embedding_model,
            "reranker_model": cfg.reranker_model,
            "hybrid_bm25": cfg.hybrid_bm25,
            "lineage_boost": cfg.lineage_boost,
        },
        "summary": summary,
        "per_question": per_question,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote {output_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
