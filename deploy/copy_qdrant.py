"""Copy the 3gpp_specs collection from the local Qdrant to a Qdrant Cloud cluster.

Copies points with their stored vectors and payloads (no re-embedding), so it
takes seconds and works across Qdrant versions, unlike a snapshot. Re-running
it recreates the target collection: it is also the restore path if the free
cluster is ever deleted.

    python deploy/copy_qdrant.py

QDRANT_CLOUD_URL and QDRANT_CLOUD_API_KEY are read from the environment, then
from .env. (Separate names, so the local QDRANT_URL stays on the local Qdrant.)
"""

import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import dotenv_values  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import PayloadSchemaType, PointStruct  # noqa: E402

from src.config import get_settings  # noqa: E402

BATCH = 256
FILTERED_FIELDS = ["spec_id", "clause_id"]


def copy_collection(source: QdrantClient, target: QdrantClient, collection: str) -> int:
    info = source.get_collection(collection)
    vectors = info.config.params.vectors
    if target.collection_exists(collection):
        target.delete_collection(collection)
    target.create_collection(collection_name=collection, vectors_config=vectors)
    # Qdrant Cloud refuses filtered searches on fields without an index; these
    # are the fields the retriever filters on (spec targeting, clause prefixes).
    for field in FILTERED_FIELDS:
        target.create_payload_index(collection, field_name=field, field_schema=PayloadSchemaType.KEYWORD, wait=True)

    copied = 0
    offset = None
    while True:
        points, offset = source.scroll(
            collection_name=collection, limit=BATCH, offset=offset, with_payload=True, with_vectors=True
        )
        if points:
            target.upsert(
                collection_name=collection,
                points=[PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in points],
                wait=True,
            )
            copied += len(points)
            print(f"  copied {copied}")
        if offset is None:
            return copied


def main() -> int:
    cfg = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-url", default=cfg.qdrant_url)
    env_file = dotenv_values(os.path.join(cfg.project_root, ".env"))
    parser.add_argument("--target-url", default=os.environ.get("QDRANT_CLOUD_URL") or env_file.get("QDRANT_CLOUD_URL", ""))
    parser.add_argument("--collection", default=cfg.qdrant_collection)
    args = parser.parse_args()
    api_key = os.environ.get("QDRANT_CLOUD_API_KEY") or env_file.get("QDRANT_CLOUD_API_KEY", "")
    if not args.target_url or not api_key:
        print("Set QDRANT_CLOUD_URL and QDRANT_CLOUD_API_KEY (or pass --target-url).")
        return 2

    source = QdrantClient(url=args.source_url, check_compatibility=False)
    target = QdrantClient(url=args.target_url, api_key=api_key, check_compatibility=False, timeout=60)

    expected = source.count(args.collection, exact=True).count
    print(f"Copying {expected} points: {args.source_url} -> {args.target_url}")
    copied = copy_collection(source, target, args.collection)
    actual = target.count(args.collection, exact=True).count
    print(f"Source {expected}, copied {copied}, target now has {actual}.")
    return 0 if actual == expected else 1


if __name__ == "__main__":
    sys.exit(main())
