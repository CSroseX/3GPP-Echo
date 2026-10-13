import glob
import json
import re
import sys

try:
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
    from sentence_transformers import CrossEncoder
except ImportError:
    print("Missing dependencies. Please run: pip install qdrant-client fastembed sentence-transformers")
    sys.exit(1)

from src.config import get_settings
from src.ingestion.chunk_ids import assign_chunk_ids
from src.obs.logging import get_logger
from src.retrieval.hybrid import BM25Index, rrf_fuse
from src.retrieval.lineage import lineage_match

log = get_logger(__name__)

class Retriever:
    def __init__(self, collection_name=None, qdrant_url=None):
        cfg = get_settings()
        self.collection_name = collection_name or cfg.qdrant_collection
        self.q_client = QdrantClient(url=qdrant_url or cfg.qdrant_url, check_compatibility=False)
        self.model = TextEmbedding(model_name=cfg.embedding_model)
        log.info("retriever.loading_cross_encoder")
        self.cross_encoder = CrossEncoder(cfg.reranker_model)
        log.info("retriever.cross_encoder_loaded")

        # Regex patterns for query routing
        self.spec_pattern = re.compile(r"(?i)(?:TS\s*)?\b(\d{2}\.\d{3})\b")
        self.clause_pattern = re.compile(r"(?i)(?:clause|sec|section|subclause)\s+([1-9A-Z][\d\.a-zA-Z]*)\b")

        # Load every chunk: clause IDs for prefix matching, and the BM25
        # index. Sorted file order matches the indexer, so assign_chunk_ids
        # reproduces the chunk_id stored in each Qdrant payload.
        chunk_dir = cfg.project_root / "data" / "chunks"
        chunk_files = sorted(glob.glob(str(chunk_dir / "*_chunks.json")))
        if not chunk_files:
            raise FileNotFoundError(
                f"No chunk files found in {chunk_dir}. "
                "Run the ingestion pipeline first (see CLAUDE.md)."
            )
        self.chunks = []
        for f in chunk_files:
            with open(f, "r", encoding="utf-8") as file:
                self.chunks.extend(json.load(file))
        self.valid_clause_ids = {c["clause_id"] for c in self.chunks}
        if not self.valid_clause_ids:
            raise ValueError(
                f"Chunk files in {chunk_dir} contained no clause IDs. "
                "The files may be empty or malformed."
            )
        assign_chunk_ids(self.chunks)

        self.bm25 = None
        if cfg.hybrid_bm25:
            self.bm25 = BM25Index(self.chunks)
            log.info("retriever.bm25_index_built", num_chunks=len(self.chunks))

    def _parse_query(self, query: str):
        """
        Parses the query to extract explicit spec_id or clause_id targeting.
        Returns a tuple of (spec_id, clause_id).
        """
        spec_match = self.spec_pattern.search(query)
        clause_match = self.clause_pattern.search(query)

        spec_id = spec_match.group(1) if spec_match else None
        clause_id = clause_match.group(1).rstrip('.') if clause_match else None

        return spec_id, clause_id

    def search(self, query: str, top_k: int = None, candidate_k: int = None):
        """
        Executes a dual-path retrieval based on query parsing.

        candidate_k is how many candidates the cross-encoder reranks before
        truncating to top_k; it defaults to rerank_multiplier * top_k.
        """
        cfg = get_settings()
        if top_k is None:
            top_k = cfg.default_top_k
        if candidate_k is None:
            candidate_k = cfg.rerank_multiplier * top_k
        candidate_k = max(candidate_k, top_k)

        spec_id, clause_id = self._parse_query(query)

        # Determine Path A (Default) vs Path B (Targeted)
        is_targeted = bool(spec_id or clause_id)
        path_name = "TARGETED PATH" if is_targeted else "DEFAULT PATH"

        log.debug("retriever.search.path", path=path_name, query=query)

        # Build Filter if Targeted
        query_filter = None
        matched_clauses = None
        if is_targeted:
            conditions = []
            if spec_id:
                log.debug("retriever.search.spec_targeting", spec_id=spec_id)
                conditions.append(
                    FieldCondition(key="spec_id", match=MatchValue(value=spec_id))
                )
            if clause_id:
                # Find all clauses that are this clause or children of this clause
                prefix = clause_id + "."
                matched_clauses = [c for c in self.valid_clause_ids if c == clause_id or c.startswith(prefix)]

                if not matched_clauses:
                    # Fallback to just the raw string if not found
                    matched_clauses = [clause_id]

                log.debug(
                    "retriever.search.clause_targeting",
                    clause_id=clause_id,
                    expanded_count=len(matched_clauses),
                )
                conditions.append(
                    FieldCondition(key="clause_id", match=MatchAny(any=matched_clauses))
                )
            query_filter = Filter(must=conditions)
        else:
            log.debug("retriever.search.no_targeting")

        # Generate embedding
        vector = list(self.model.embed([query]))[0].tolist()

        # Search Qdrant
        results = self.q_client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=candidate_k
        ).points

        # Format results and prepare for reranking
        candidates = [_candidate(res.payload, qdrant_score=round(res.score, 4)) for res in results]

        if self.bm25 is not None:
            bm25_hits = self.bm25.search(query, candidate_k, spec_id=spec_id, clause_ids=matched_clauses)
            candidates = _fuse(candidates, bm25_hits, candidate_k, cfg.rrf_k)

        if not candidates:
            return []

        log.debug(
            "retriever.search.candidates_before_rerank",
            count=len(candidates),
            candidates=[
                {"spec_id": c["spec_id"], "clause_id": c["clause_id"], "qdrant_score": c["qdrant_score"],
                 "bm25_score": c.get("bm25_score")}
                for c in candidates
            ],
        )

        # Rerank with Cross-Encoder
        log.debug("retriever.search.reranking", count=len(candidates))
        pairs = [(str(query), str(c["content"])) for c in candidates]
        cross_scores = self.cross_encoder.predict(pairs)

        # score = cross-encoder logit + lineage boost; cross_score keeps the
        # raw logit for anything that needs an uncalibrated-by-us signal.
        for i, c in enumerate(candidates):
            c["cross_score"] = round(float(cross_scores[i]), 4)
            c["lineage_match"] = round(lineage_match(query, c["clause_title"], c["lineage"]), 4)
            c["score"] = round(c["cross_score"] + cfg.lineage_boost * c["lineage_match"], 4)

        # Sort by final score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # Take top_k
        formatted_results = candidates[:top_k]

        log.debug(
            "retriever.search.final_results",
            top_k=top_k,
            results=[
                {"spec_id": c["spec_id"], "clause_id": c["clause_id"], "score": c["score"]}
                for c in formatted_results
            ],
        )

        return formatted_results


def _candidate(chunk, qdrant_score=None):
    content = chunk.get("content", "")
    return {
        "chunk_id": chunk.get("chunk_id"),
        "spec_id": chunk.get("spec_id"),
        "clause_id": chunk.get("clause_id"),
        "clause_title": chunk.get("clause_title", ""),
        "lineage": chunk.get("lineage", []),
        "qdrant_score": qdrant_score,
        "content": content,
        "content_preview": str(content)[:150].replace("\n", " ") + "...",
    }


def _fuse(dense_candidates, bm25_hits, candidate_k, rrf_k):
    """RRF-merge the dense ranking with BM25's, keyed by chunk_id, and keep
    the top candidate_k for the cross-encoder. A chunk found only by BM25
    has qdrant_score None; one found by both carries both scores."""
    by_key = {}
    dense_keys = []
    for c in dense_candidates:
        key = c["chunk_id"] or f"{c['spec_id']}|{c['clause_id']}|{c['content_preview']}"
        by_key.setdefault(key, c)
        dense_keys.append(key)

    bm25_keys = []
    for chunk, score in bm25_hits:
        key = chunk["chunk_id"]
        if key not in by_key:
            by_key[key] = _candidate(chunk)
        by_key[key]["bm25_score"] = round(score, 4)
        bm25_keys.append(key)

    return [by_key[key] for key in rrf_fuse([dense_keys, bm25_keys], k=rrf_k)[:candidate_k]]


if __name__ == "__main__":
    retriever = Retriever()

    queries = [
        "What is the AMF?",
        "What is the AMF according to TS 23.501?",
        "Details on procedure in clause 5.5.1",
        "clause 5.5"
    ]

    for q in queries:
        results = retriever.search(q, top_k=3)
        print("Results:")
        for i, r in enumerate(results):
            print(f"  {i+1}. [Score: {r['score']}] Spec {r['spec_id']} Clause {r['clause_id']}")
            print(f"     Preview: {r['content_preview']}")
        print("-" * 60)
