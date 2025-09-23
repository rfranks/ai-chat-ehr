# syntax=docker/dockerfile:1.5

ARG BASE_IMAGE=ai-chat-ehr-base:latest
FROM ${BASE_IMAGE} AS runtime

WORKDIR /app

COPY shared ./shared
COPY repositories ./repositories
COPY services/patient_context ./services/patient_context

EXPOSE 8002

CMD ["uvicorn", "services.patient_context.main:app", "--host", "0.0.0.0", "--port", "8002"]
