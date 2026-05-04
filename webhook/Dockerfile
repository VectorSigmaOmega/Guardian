FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY app.py /app/app.py
COPY config /app/config
COPY runbooks /app/runbooks

RUN pip install --no-cache-dir .

EXPOSE 5000

CMD ["python", "app.py"]

