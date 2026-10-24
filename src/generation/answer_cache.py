"""Answer cache for the input guardrail: a repeated question costs no LLM call.

Only answers labelled "answered" are stored. A question hits the cache when either
1. its normalized text (lowercase, punctuation and spacing removed) equals a
   stored question's, or
2. its embedding is at least `answer_cache_similarity` cosine-similar to a
   stored question's AND both mention exactly the same 3GPP terms.

The term rule is what makes a fuzzy cache safe in this corpus: "What timer
does the AMF use for TAU?" and "What timer does the MME use for TAU?" embed
almost identically but have different answers (5G vs 4G). Terms come from the
corpus lexicon (acronyms and spec numbers), so no hand-written list is needed.

Stored in SQLite so it survives restarts; the table is small (one row per
distinct answered question), so lookups scan it in memory.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from src.config import get_settings
from src.generation.lexicon import DomainLexicon, get_lexicon

EmbedFn = Callable[[Sequence[str]], np.ndarray]

_SPEC_RE = re.compile(r"\b\d{2}\.\d{3}\b")


def normalize(question: str) -> str:
    """"What is the AMF?" and "what is the  AMF" map to the same key."""
    return re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()


def domain_terms(question: str, lex: DomainLexicon) -> List[str]:
    """The 3GPP terms a question mentions: corpus acronyms (long forms map to
    their acronym) and spec numbers. Two questions must share exactly these
    to count as the same question."""
    terms = set(lex.find_acronyms(question))
    terms.update(acronym for _, acronym in lex.find_long_forms(question))
    terms.update(_SPEC_RE.findall(question))
    return sorted(terms)


class AnswerCache:
    def __init__(
        self,
        path: Path,
        embed: EmbedFn,
        lexicon: Optional[DomainLexicon] = None,
        similarity: Optional[float] = None,
    ):
        self.path = Path(path)
        self.embed = embed
        self.lexicon = lexicon
        self.similarity = similarity if similarity is not None else get_settings().answer_cache_similarity
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS answers ("
                " key TEXT PRIMARY KEY, question TEXT, terms TEXT, embedding BLOB,"
                " answer TEXT, sources TEXT, created_at REAL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _lex(self) -> DomainLexicon:
        return self.lexicon or get_lexicon()

    def _vector(self, question: str) -> np.ndarray:
        v = np.asarray(self.embed([question])[0], dtype=np.float32)
        return v / (np.linalg.norm(v) or 1.0)

    def lookup(self, question: str) -> Optional[Dict[str, Any]]:
        """The cached entry for this question, or None. The returned dict
        carries `match` ("exact" | "semantic") and `similarity`."""
        key = normalize(question)
        with self._connect() as db:
            row = db.execute("SELECT question, answer, sources FROM answers WHERE key = ?", (key,)).fetchone()
            if row:
                return {"question": row[0], "answer": row[1], "sources": json.loads(row[2]),
                        "match": "exact", "similarity": 1.0}
            rows = db.execute("SELECT question, terms, embedding, answer, sources FROM answers").fetchall()
        if not rows:
            return None

        terms = json.dumps(domain_terms(question, self._lex()))
        candidates = [r for r in rows if r[1] == terms]
        if not candidates:
            return None
        query = self._vector(question)
        best, best_sim = None, -1.0
        for r in candidates:
            sim = float(np.dot(query, np.frombuffer(r[2], dtype=np.float32)))
            if sim > best_sim:
                best, best_sim = r, sim
        if best_sim < self.similarity:
            return None
        return {"question": best[0], "answer": best[3], "sources": json.loads(best[4]),
                "match": "semantic", "similarity": round(best_sim, 4)}

    def store(self, question: str, answer: str, sources: List[Dict[str, Any]]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO answers VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    normalize(question),
                    question,
                    json.dumps(domain_terms(question, self._lex())),
                    self._vector(question).tobytes(),
                    answer,
                    json.dumps(sources),
                    time.time(),
                ),
            )
