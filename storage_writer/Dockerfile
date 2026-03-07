FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY storage_writer/pyproject.toml ./pyproject.toml
COPY storage_writer/src ./src
COPY domain_data ./src/storage_writer/domain_data
RUN pip install --no-cache-dir .

CMD ["uvicorn", "storage_writer.main:app", "--host", "0.0.0.0", "--port", "8090"]
