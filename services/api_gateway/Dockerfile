# syntax=docker/dockerfile:1.5

ARG BASE_IMAGE=ai-chat-ehr-base:latest
FROM ${BASE_IMAGE} AS runtime

WORKDIR /app

COPY shared ./shared
COPY services/api_gateway ./services/api_gateway

EXPOSE 8000

CMD ["uvicorn", "services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
