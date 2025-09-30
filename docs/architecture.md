# Architecture overview

## Chain execution lifecycle

The chain executor service exposes buffered and streaming endpoints at
`POST /chains/execute` and `POST /chains/execute/stream`. Each request is
validated against `ChainExecutionRequest`, which accepts a list of prompt
selectors, optional patient identifier, initial variables, and model overrides
such as `modelProvider`, `model`, and `temperature`.
Resolved requests are wrapped in a `_ChainExecutionContext` that captures the
chosen language model, provider metadata, fetched patient context, resolved
variables, and the ordered prompt steps that will be executed. Prompt selectors
are normalised via the prompt catalog client: raw strings become temporary
prompts, `ChatPromptKey` enums fetch catalog entries, and missing prompts raise a
`PromptNotFoundError`.

Before executing the chain, the service enriches the variable map with patient
context JSON, derived context helpers, and any IDs supplied in the request.
Each prompt step is compiled into a `PromptTemplate`, assigned a unique output
key, and appended to the execution context. The buffered endpoint runs each
`LLMChain` sequentially, updating the variable map and aggregating outputs for
inclusion in the final `ChainExecutionResponse`. The streaming endpoint executes
non-final steps the same way but streams incremental chunks from the final LLM
step as server-sent events, emitting metadata, intermediate step payloads, and a
final response envelope when completion succeeds or an error occurs.

## Provider resolution

`ChainExecutionRequest` defaults to `LLMProvider.OPENAI_GPT_35_TURBO`, but
callers can override `modelProvider` or supply an explicit `model` name.
`LLMProvider` enumerates the supported provider/model combinations and exposes a
`create_client` helper that constructs the appropriate LangChain client using the
shared settings for OpenAI, Azure, Anthropic, or Vertex. When a model override
is supplied, the helper resolves the concrete `ModelSpec` and delegates client
creation to the resolved provider, ensuring temperature overrides and backend
capabilities are respected.

## Prompt category inference

Prompt metadata optionally includes `categories`, but when a prompt lacks labels
the chain executor invokes `_ensure_prompt_categories` to infer them. The helper
first inspects the prompt metadata and cached results; if no categories are
available it instantiates a lazily-created `CategoryClassifier`. The classifier
serialises the prompt payload to JSON, invokes its `LLMChain`, and parses the
response into category slugs using a deterministic parser. Successful
classifications are cached by a digest of the prompt metadata, and the inferred
slugs are injected back into the prompt metadata for downstream consumers.

Cache characteristics can be tuned via environment variables without code changes.
`CHAIN_EXECUTOR_CATEGORY_CACHE_MAX_ENTRIES` and
`CHAIN_EXECUTOR_CATEGORY_CACHE_TTL_SECONDS` configure the baseline cache size and
expiration. The service also exposes `CHAIN_EXECUTOR_CLASSIFICATION_CACHE_MAX_ENTRIES`
and `CHAIN_EXECUTOR_CLASSIFICATION_CACHE_TTL_SECONDS` for overriding the
classification cache independently when tighter limits or shorter lifetimes are required.
