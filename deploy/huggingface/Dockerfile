# Olympics Analysis API - Hugging Face Space (Docker SDK, free CPU tier).
# The 2.7 GB SQLite warehouse is not baked into the image: start.sh downloads it once from the Hugging Face dataset
# repo named by WAREHOUSE_REPO into /app/data, then serves FastAPI on port 7860 (the port Spaces expose).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:///./data/olympics_warehouse.db \
    HF_HOME=/tmp/hf

RUN useradd -m -u 1000 app
WORKDIR /app

COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

COPY --chown=app:app backend ./backend
COPY --chown=app:app reports ./reports
COPY --chown=app:app models ./models
COPY --chown=app:app frontend/public/assets/editions.json ./frontend/public/assets/editions.json
COPY --chown=app:app start.sh ./start.sh
RUN mkdir -p /app/data && chown -R app:app /app && chmod +x start.sh

USER app
EXPOSE 7860
CMD ["./start.sh"]
