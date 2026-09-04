# Pinned to 3.12 rather than latest: the agent extras (langgraph, google-cloud-aiplatform)
# do not reliably have wheels on the newest interpreter yet.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PROVIDER=stub

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e '.[ui]'

COPY data ./data
COPY ui ./ui
COPY docs ./docs

# Bake the index so the container is useful with no first-run step.
RUN python -m psa.rag.index

RUN useradd --create-home --uid 10001 psa && chown -R psa:psa /app
USER psa

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
