FROM python:3.12-slim@sha256:dd29372629eeba2dd003fd9e9d35a5b8236c44727875a0364254b5127af88e65 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY pyproject.toml README.md requirements-runtime.lock.sha256 ./
COPY src ./src

# Build tooling is explicitly versioned and kept out of the final runtime image.
RUN python -m pip install \
      'pip==26.1.2' \
      'setuptools==83.0.0' \
      'wheel==0.47.0' \
      'pip-tools==7.6.0' \
    && pip-compile pyproject.toml --generate-hashes --strip-extras --output-file /tmp/requirements-runtime.lock \
    && expected="$(awk '{print $1}' requirements-runtime.lock.sha256)" \
    && actual="$(sha256sum /tmp/requirements-runtime.lock | awk '{print $1}')" \
    && test -n "$expected" \
    && test "$actual" = "$expected" \
    && mkdir -p /wheels \
    && python -m pip wheel --require-hashes --wheel-dir /wheels -r /tmp/requirements-runtime.lock \
    && python -m pip wheel --no-deps --no-build-isolation --wheel-dir /wheels .

FROM python:3.12-slim@sha256:dd29372629eeba2dd003fd9e9d35a5b8236c44727875a0364254b5127af88e65 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels 'aisearcharab-api==0.2.0' \
    && python -m pip check \
    && rm -rf /wheels

COPY alembic.ini ./
COPY alembic ./alembic

USER app
EXPOSE 8000
CMD ["uvicorn", "aisearcharab_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
