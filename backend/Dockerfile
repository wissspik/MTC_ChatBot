FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface

WORKDIR /app

ARG INSTALL_LOCAL_LLM=false

COPY backend/requirements.txt backend/requirements-local.txt /app/
RUN if [ "$INSTALL_LOCAL_LLM" = "true" ]; then \
        pip install -r /app/requirements-local.txt; \
    else \
        pip install -r /app/requirements.txt; \
    fi

COPY backend /app/backend
COPY INSTUC.txt /app/INSTUC.txt

RUN mkdir -p /app/.cache/huggingface

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
