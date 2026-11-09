"""Serve the backend API on Modal (free Starter plan: $30 of usage a month).

Builds the repo's Dockerfile (models baked in) and serves src/api/main.py.
At most one container runs; it sleeps after `scaledown_window` seconds
without requests, so idle time costs nothing.

    python deploy/modal_app.py            # deploy; prints the public URL

Secrets are read from .env at deploy time (Modal token, OpenRouter key,
Qdrant Cloud URL + key), stored in a named Modal secret, and reach the
container as environment variables.
"""

import os
import subprocess
import sys
from pathlib import Path

import modal
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ENV = dotenv_values(ROOT / ".env")

# Container environment. The Qdrant Cloud values are stored locally under
# QDRANT_CLOUD_* so that the local QDRANT_URL keeps pointing at local Qdrant.
CONTAINER_ENV = {
    "USE_REMOTE_LLM": "true",
    "OPEN_ROUTER_API_KEY": ENV.get("OPEN_ROUTER_API_KEY") or "",
    "QDRANT_URL": ENV.get("QDRANT_CLOUD_URL") or "",
    "QDRANT_API_KEY": ENV.get("QDRANT_CLOUD_API_KEY") or "",
}
if ENV.get("API_CORS_ORIGINS"):
    CONTAINER_ENV["API_CORS_ORIGINS"] = ENV["API_CORS_ORIGINS"]

SECRET_NAME = "3gpp-echo-api-env"  # created/updated by __main__ before each deploy

image = modal.Image.from_dockerfile(ROOT / "Dockerfile", context_dir=ROOT)
app = modal.App("3gpp-echo-api")
secret = modal.Secret.from_name(SECRET_NAME)


@app.function(image=image, secrets=[secret], timeout=120)
def check():
    """Smoke test from inside the container, no LLM tokens:
    `python -m modal run deploy/modal_app.py::check`."""
    sys.path.insert(0, "/app")
    from qdrant_client import QdrantClient

    from src.api.main import openrouter_balance
    from src.config import get_settings

    cfg = get_settings()
    q = QdrantClient(url=cfg.qdrant_url, api_key=cfg.qdrant_api_key or None, check_compatibility=False)
    print("qdrant host:", cfg.qdrant_url.split("//")[-1].split(".")[1:3])
    print("qdrant points:", q.count(cfg.qdrant_collection, exact=True).count)
    print("openrouter balance:", openrouter_balance())
    print("remote llm:", cfg.use_remote_llm)


@app.function(
    image=image,
    secrets=[secret],
    cpu=2,
    memory=2048,
    max_containers=1,  # one copy of the models; caps cost
    scaledown_window=300,  # sleep after 5 idle minutes
    timeout=120,
)
@modal.concurrent(max_inputs=8)  # extra requests queue inside the one container
@modal.asgi_app()
def api():
    sys.path.insert(0, "/app")
    os.chdir("/app")
    from src.api.main import app as fastapi_app

    return fastapi_app


if __name__ == "__main__":
    missing = [k for k in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "OPEN_ROUTER_API_KEY",
                           "QDRANT_CLOUD_URL", "QDRANT_CLOUD_API_KEY") if not ENV.get(k)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")
    env = {**os.environ, "MODAL_TOKEN_ID": ENV["MODAL_TOKEN_ID"], "MODAL_TOKEN_SECRET": ENV["MODAL_TOKEN_SECRET"],
           "PYTHONIOENCODING": "utf-8"}
    modal_cli = [sys.executable, "-m", "modal"]
    pairs = [f"{k}={v}" for k, v in CONTAINER_ENV.items()]
    if subprocess.call(modal_cli + ["secret", "create", "--force", SECRET_NAME, *pairs],
                       env=env, cwd=ROOT, stdout=subprocess.DEVNULL):
        sys.exit("Could not create the Modal secret.")
    sys.exit(subprocess.call(modal_cli + ["deploy", __file__], env=env, cwd=ROOT))
