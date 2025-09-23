# ai-chat-ehr
Proving Grounds for ChatEHR

## Streaming chain execution

The chain executor service exposes a streaming endpoint at
`POST /chains/execute/stream`. The endpoint emits server-sent events (SSE) so
clients can render language model output as it is generated. Each event is a JSON
payload delivered in the `data:` field and includes a `type` attribute. The most
common event types are:

* `metadata` – initial service metadata including provider, model, and whether
  streaming is expected for the selected model.
* `step` – emitted after non-streaming steps in the chain complete to expose the
  intermediate output keyed by `outputKey`.
* `chunk` – incremental text from the final LLM step. When a provider cannot
  stream tokens the event includes `"buffered": true` and carries the complete
  response.
* `response` – a serialized `ChainExecutionResponse` matching the buffered
  endpoint plus a `streaming` flag indicating whether streaming succeeded.
* `error` – final event describing why execution failed when an exception
  occurs.

When the chosen provider or model does not support streaming, the service logs a
warning, emits an informational event, and falls back to a buffered response. In
this mode the `chunk` event contains the entire response payload, and the final
`response` event reports `"streaming": false` so clients can adjust their user
experience accordingly.
