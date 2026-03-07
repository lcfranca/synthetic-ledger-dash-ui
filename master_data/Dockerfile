FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY master_data/pyproject.toml ./pyproject.toml
COPY master_data/src ./src
COPY domain_data ./src/master_data/domain_data
RUN pip install --no-cache-dir .

CMD ["uvicorn", "master_data.main:app", "--host", "0.0.0.0", "--port", "8091"]
