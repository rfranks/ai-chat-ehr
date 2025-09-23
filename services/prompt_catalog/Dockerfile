# syntax=docker/dockerfile:1.5

ARG BASE_IMAGE=ai-chat-ehr-base:latest
FROM ${BASE_IMAGE} AS runtime

WORKDIR /app

COPY shared ./shared
COPY repositories ./repositories
COPY services/prompt_catalog ./services/prompt_catalog

EXPOSE 8001

CMD ["uvicorn", "services.prompt_catalog.main:app", "--host", "0.0.0.0", "--port", "8001"]
