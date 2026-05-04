FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY state /app/state

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "-m", "guardian_exporter.app"]

