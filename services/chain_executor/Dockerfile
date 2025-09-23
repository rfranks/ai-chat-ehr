# syntax=docker/dockerfile:1.5

ARG BASE_IMAGE=ai-chat-ehr-base:latest
FROM ${BASE_IMAGE} AS runtime

WORKDIR /app

COPY shared ./shared
COPY services/chain_executor ./services/chain_executor

EXPOSE 8003

CMD ["uvicorn", "services.chain_executor.main:app", "--host", "0.0.0.0", "--port", "8003"]
