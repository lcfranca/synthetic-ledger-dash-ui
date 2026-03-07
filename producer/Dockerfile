FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY producer/pyproject.toml ./pyproject.toml
COPY producer/src ./src
COPY domain_data ./src/producer/domain_data
RUN pip install --no-cache-dir .

CMD ["python", "-m", "producer.main"]
