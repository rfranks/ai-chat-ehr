# syntax=docker/dockerfile:1.5

ARG BASE_IMAGE=ai-chat-ehr-base:latest
FROM ${BASE_IMAGE} AS runtime

WORKDIR /app

COPY shared ./shared
COPY services/generator ./services/generator

EXPOSE 8005

CMD ["uvicorn", "services.generator.main:app", "--host", "0.0.0.0", "--port", "8005"]
