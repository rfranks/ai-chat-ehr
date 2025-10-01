# syntax=docker/dockerfile:1.5

ARG BASE_IMAGE=ai-chat-ehr-base:latest
FROM ${BASE_IMAGE} AS runtime

WORKDIR /app

COPY shared ./shared
COPY services/anonymizer ./services/anonymizer

EXPOSE 8004

CMD ["uvicorn", "services.anonymizer.main:app", "--host", "0.0.0.0", "--port", "8004"]
