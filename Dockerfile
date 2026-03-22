ARG PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.12-slim
ARG NODE_BASE_IMAGE=public.ecr.aws/docker/library/node:22-bookworm-slim

FROM ${NODE_BASE_IMAGE} AS node-runtime

FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_REQUIRE_HASHES=0

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node-runtime /usr/local/ /usr/local/

RUN node --version \
    && npm --version

COPY pyproject.toml /workspace/pyproject.toml
COPY app /workspace/app
COPY tests /workspace/tests

RUN pip install -e ".[dev]"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
