FROM python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.txt

COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 8080

CMD ["python", "app.py"]
