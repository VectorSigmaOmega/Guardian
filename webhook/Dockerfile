FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
COPY app.py /app/app.py
COPY config /app/config
COPY runbooks /app/runbooks

RUN pip install --no-cache-dir .

EXPOSE 5000

CMD ["python", "app.py"]
