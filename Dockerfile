# Backend API image (FastAPI + the LangGraph pipeline). Deployed on Modal by
# deploy/modal_app.py (which ignores USER/EXPOSE/CMD); runnable anywhere:
#
#   docker build -t 3gpp-echo-api .
#   docker run -p 7860:7860 -e QDRANT_URL=... -e QDRANT_API_KEY=... \
#       -e USE_REMOTE_LLM=true -e OPEN_ROUTER_API_KEY=... 3gpp-echo-api
#
# Models are downloaded at build time, so a restart never fetches them.
# Configuration and secrets come only from environment variables.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/models/hf \
    FASTEMBED_CACHE_PATH=/app/models/fastembed

RUN useradd -m -u 1000 user
WORKDIR /app

# CPU-only torch first; the default wheel pulls in several GB of CUDA.
RUN pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml .
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

COPY src/ src/
COPY data/chunks/*_chunks.json data/chunks/
COPY data/domain_centroids.npz data/

RUN python -c "from src.config import get_settings as s; from fastembed import TextEmbedding; from sentence_transformers import CrossEncoder; TextEmbedding(s().embedding_model); CrossEncoder(s().reranker_model)" \
    && chown -R user:user /app

# Models are in the image now: never contact huggingface.co at runtime.
ENV HF_HUB_OFFLINE=1

USER user
EXPOSE 7860
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
