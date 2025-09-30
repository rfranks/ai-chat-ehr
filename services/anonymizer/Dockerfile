# syntax=docker/dockerfile:1.5

ARG BASE_IMAGE=ai-chat-ehr-base:latest
FROM ${BASE_IMAGE} AS runtime

WORKDIR /app

# Copy project metadata and source required for installation
COPY pyproject.toml README.md ./
COPY shared ./shared
COPY repositories ./repositories
COPY services/__init__.py ./services/__init__.py
COPY services/anonymizer ./services/anonymizer

# Install the application package to ensure dependencies are available
RUN pip install --no-cache-dir .

EXPOSE 8004

CMD ["uvicorn", "services.anonymizer.main:app", "--host", "0.0.0.0", "--port", "8004"]
