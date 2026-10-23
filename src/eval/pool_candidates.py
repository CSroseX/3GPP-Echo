"""Pool candidate chunks for golden-set grading from several independent
search methods, so the answer key isn't built only from what our own
retriever finds. Read-only against Qdrant; zero LLM tokens.

    python -m src.eval.pool_candidates --ids 1,23,28,31,35
    python -m src.eval.pool_candidates            # every retrieval_scored question

Writes to --out-dir (default eval/pooling/):
  pool.json            which methods found each chunk, and at what rank
                       (kept away from the grader)
  grading_sheet.jsonl  one line per (question, chunk) in shuffled order,
                       with text and section path but no method names
"""

from __future__ import annotations

import argparse
import io
import json
import os
import random
import re
import subprocess
import sys
from collections import defaultdict
from typing import Any, Dict, List, Sequence

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import snowballstemmer
from qdrant_client.models import FieldCondition, Filter, MatchValue
from rank_bm25 import BM25Okapi

from src.config import get_settings
from src.generation.lexicon import get_lexicon
from src.retrieval.hybrid import _STOPWORDS, chunk_text
from src.retrieval.retriever import Retriever

GOLDEN_SET_PATH = "eval/golden/golden_set.v2.json"
OUT_DIR = "eval/pooling"
SPECS = ("23.501", "24.501", "24.301")
DEPTH = 10            # top-N chunks per method
PER_SPEC_DEPTH = 5    # dense-per-spec takes this many from each spec
RANDOM_PER_QUESTION = 3
SEED = 20261023

_STEMMER = snowballstemmer.stemmer("english")
# Hyphen/dot-joined runs stay whole ("5g-guti", "t3510", "s-nssai") and also
# contribute their parts, so "NSSAI" still matches "S-NSSAI".
_JOINED_RE = re.compile(r"[a-z0-9]+(?:[-.][a-z0-9]+)*")
_PART_RE = re.compile(r"[a-z0-9]+")
# Exact 3GPP terms beyond lexicon acronyms: upper-case message names
# ("REGISTRATION REQUEST"), timers, cause numbers, double-quoted phrases.
_MESSAGE_NAME_RE = re.compile(r"\b[A-Z][A-Z0-9-]{2,}(?: [A-Z][A-Z0-9-]{1,})+\b")
_TIMER_RE = re.compile(r"\bT\d{4}\b")
_CAUSE_RE = re.compile(r"#\d+")
_QUOTED_RE = re.compile(r"\"([^\"]{3,})\"")


def stem_tokens(text: str) -> List[str]:
    out: List[str] = []
    for joined in _JOINED_RE.findall(text.lower()):
        parts = _PART_RE.findall(joined)
        if len(parts) > 1:
            out.append(joined)
        out.extend(_STEMMER.stemWord(p) for p in parts if p not in _STOPWORDS)
    return out


def exact_terms(question: str) -> List[str]:
    terms = list(get_lexicon().find_acronyms(question))
    for pattern in (_MESSAGE_NAME_RE, _TIMER_RE, _CAUSE_RE):
        terms.extend(pattern.findall(question))
    terms.extend(_QUOTED_RE.findall(question))
    seen: List[str] = []
    for t in terms:
        if t not in seen and not any(t != s and t in s for s in terms):
            seen.append(t)
    return seen


def _text(chunk: Dict[str, Any]) -> str:
    content = chunk["content"]
    return content if isinstance(content, str) else " ".join(str(c) for row in content for c in row)


class Pooler:
    def __init__(self, retriever: Retriever):
        self.retriever = retriever
        self.chunks = retriever.chunks  # chunk_id already assigned, same as Qdrant
        self.by_id = {c["chunk_id"]: c for c in self.chunks}
        self.bm25 = BM25Okapi([stem_tokens(chunk_text(c)) for c in self.chunks])
        self.texts = [_text(c) for c in self.chunks]
        # Clause-title index: one entry per (spec, clause) with its chunks.
        self.clauses: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for c in self.chunks:
            self.clauses[(c["spec_id"], c["clause_id"])].append(c)

    # ── methods: each returns chunk_ids, best first ──────────────────
    def dense_per_spec(self, question: str) -> List[str]:
        vector = list(self.retriever.model.embed([question]))[0].tolist()
        ids: List[str] = []
        for spec in SPECS:
            points = self.retriever.q_client.query_points(
                collection_name=self.retriever.collection_name, query=vector, limit=PER_SPEC_DEPTH,
                query_filter=Filter(must=[FieldCondition(key="spec_id", match=MatchValue(value=spec))]),
            ).points
            ids.extend(p.payload["chunk_id"] for p in points)
        return ids

    def dense_no_rerank(self, question: str) -> List[str]:
        vector = list(self.retriever.model.embed([question]))[0].tolist()
        points = self.retriever.q_client.query_points(
            collection_name=self.retriever.collection_name, query=vector, limit=DEPTH,
        ).points
        return [p.payload["chunk_id"] for p in points]

    def bm25_stemmed(self, question: str) -> List[str]:
        scores = self.bm25.get_scores(stem_tokens(question))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.chunks[i]["chunk_id"] for i in order[:DEPTH] if scores[i] > 0]

    def exact_term(self, question: str) -> List[str]:
        terms = exact_terms(question)
        if not terms:
            return []
        scored = []
        for i, text in enumerate(self.texts):
            hits = [t for t in terms if t in text]
            if hits:
                # Distinct terms first, then total occurrences.
                scored.append((len(hits), sum(text.count(t) for t in hits), i))
        scored.sort(reverse=True)
        return [self.chunks[i]["chunk_id"] for _, _, i in scored[:DEPTH]]

    def clause_title(self, question: str) -> List[str]:
        q = set(stem_tokens(question))
        scored = []
        for key, chunks in self.clauses.items():
            title = set(stem_tokens(chunks[0].get("clause_title") or ""))
            overlap = len(q & title)
            if overlap:
                # More shared words first; among ties, the more specific title.
                scored.append((overlap, -len(title), key))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        ids = []
        for _, _, key in scored[:DEPTH]:
            # Within a matched clause, take the chunk sharing most words with the question.
            best = max(self.clauses[key], key=lambda c: len(q & set(stem_tokens(_text(c)))))
            ids.append(best["chunk_id"])
        return ids

    def system(self, question: str) -> List[str]:
        cfg = get_settings()
        results = self.retriever.search(question, top_k=DEPTH,
                                        candidate_k=cfg.rerank_multiplier * cfg.default_top_k)
        return [r["chunk_id"] for r in results]

    def random_sample(self, question_id: int) -> List[str]:
        rng = random.Random(SEED + question_id)
        return [c["chunk_id"] for c in rng.sample(self.chunks, RANDOM_PER_QUESTION)]

    METHODS = ("dense_per_spec", "dense_no_rerank", "bm25_stemmed", "exact_term", "clause_title", "system")

    def pool(self, q: Dict[str, Any]) -> Dict[str, Any]:
        found: Dict[str, Dict[str, int]] = defaultdict(dict)
        for method in self.METHODS:
            for rank, cid in enumerate(getattr(self, method)(q["question"]), 1):
                found[cid].setdefault(method, rank)
        for rank, cid in enumerate(self.random_sample(q["id"]), 1):
            found[cid].setdefault("random", rank)
        candidates = []
        for cid, methods in found.items():
            c = self.by_id[cid]
            candidates.append({"chunk_id": cid, "spec_id": c["spec_id"], "clause_id": c["clause_id"],
                               "found_by": methods})
        return {"id": q["id"], "question": q["question"], "gold_clauses": q["gold_clauses"],
                "exact_terms": exact_terms(q["question"]), "candidates": candidates}


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def grading_rows(pools: Sequence[Dict[str, Any]], by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for p in pools:
        for cand in p["candidates"]:
            c = by_id[cand["chunk_id"]]
            rows.append({"question_id": p["id"], "question": p["question"], "chunk_id": c["chunk_id"],
                         "spec_id": c["spec_id"], "clause_id": c["clause_id"],
                         "clause_title": c.get("clause_title"), "lineage": c.get("lineage"),
                         "text": _text(c)})
    random.Random(SEED).shuffle(rows)
    for i, row in enumerate(rows, 1):
        row["grade_id"] = i
    return rows


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    parser = argparse.ArgumentParser(description="Pool candidate chunks for blind grading.")
    parser.add_argument("--ids", help="Comma-separated golden-set ids (default: all retrieval_scored).")
    parser.add_argument("--out-dir", default=OUT_DIR)
    args = parser.parse_args()

    with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
        golden = [q for q in json.load(f) if q["retrieval_scored"]]
    if args.ids:
        wanted = {int(i) for i in args.ids.split(",")}
        golden = [q for q in golden if q["id"] in wanted]

    pooler = Pooler(Retriever())
    pools = [pooler.pool(q) for q in golden]

    os.makedirs(args.out_dir, exist_ok=True)
    cfg = get_settings()
    with open(os.path.join(args.out_dir, "pool.json"), "w", encoding="utf-8") as f:
        json.dump({"golden_set_path": GOLDEN_SET_PATH, "git_commit": _git_commit(),
                   "depth": DEPTH, "per_spec_depth": PER_SPEC_DEPTH, "random_per_question": RANDOM_PER_QUESTION,
                   "seed": SEED, "system_settings": {"rerank_multiplier": cfg.rerank_multiplier,
                                                     "default_top_k": cfg.default_top_k,
                                                     "hybrid_bm25": cfg.hybrid_bm25,
                                                     "lineage_boost": cfg.lineage_boost},
                   "questions": pools}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(args.out_dir, "grading_sheet.jsonl"), "w", encoding="utf-8") as f:
        for row in grading_rows(pools, pooler.by_id):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Per-question summary: pool size, and chunks only one method found.
    print(f"{'Q':>3} {'pool':>4}  " + "  ".join(f"{m[:12]:>12}" for m in Pooler.METHODS))
    for p in pools:
        only = defaultdict(int)
        for cand in p["candidates"]:
            real = [m for m in cand["found_by"] if m != "random"]
            if len(real) == 1:
                only[real[0]] += 1
        print(f"{p['id']:>3} {len(p['candidates']):>4}  "
              + "  ".join(f"{only[m]:>12}" for m in Pooler.METHODS) + f"   terms={p['exact_terms']}")
    print("(columns: chunks found ONLY by that method)")


if __name__ == "__main__":
    main()
