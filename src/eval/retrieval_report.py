"""Retrieval-only report: recall@5/@20, MRR, nDCG@10, strict and
prefix-credit, over every golden-set question with retrieval_scored=true.

Zero LLM tokens — this only exercises Retriever.search() against Qdrant,
never the generate/verify graph. Safe to re-run anytime Qdrant is live.

    python -m src.eval.retrieval_report
    python -m src.eval.retrieval_report --output eval/baselines/ablation_x.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import get_settings
from src.eval.metrics import score_question
from src.retrieval.retriever import Retriever

GOLDEN_SET_PATH = "eval/golden/golden_set.v1.json"
OUTPUT_PATH = "eval/baselines/retrieval_baseline.json"


def main():
    parser = argparse.ArgumentParser(description="Zero-LLM-token retrieval report over the golden set.")
    parser.add_argument("--output", default=OUTPUT_PATH,
                        help="Where to write the report (default: the committed baseline).")
    output_path = parser.parse_args().output

    cfg = get_settings()

    with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

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
        per_question.append({
            "id": q["id"],
            "question": q["question"],
            "gold_clauses": q["gold_clauses"],
            "latency_ms": round(elapsed_ms, 1),
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

    report = {
        "golden_set_path": GOLDEN_SET_PATH,
        "config": {
            "default_top_k": cfg.default_top_k,
            "rerank_multiplier": cfg.rerank_multiplier,
            "candidate_k": candidate_k,
            "eval_top_k": cfg.eval_top_k,
            "embedding_model": cfg.embedding_model,
            "reranker_model": cfg.reranker_model,
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
