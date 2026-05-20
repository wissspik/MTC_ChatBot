FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DEFAULT_TIMEOUT=300
ENV PIP_RETRIES=10
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_PROGRESS_BAR=off
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface

WORKDIR /app

ARG INSTALL_LOCAL_LLM=false

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --prefer-binary --timeout 300 --retries 10 -r /app/requirements.txt

COPY backend/requirements-local.txt /app/requirements-local.txt
RUN if [ "$INSTALL_LOCAL_LLM" = "true" ]; then \
        pip install --prefer-binary --timeout 300 --retries 10 -r /app/requirements-local.txt; \
    fi

COPY backend /app/backend
COPY INSTUC.txt /app/INSTUC.txt

RUN mkdir -p /app/.cache/huggingface

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
