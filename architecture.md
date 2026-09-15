# Architecture

## System context and boundaries

The browser is an untrusted client. FastAPI owns validation, session authorization, task routing, retrieval,
provider calls, citation normalization, artifact sanitation, and persistence. PostgreSQL is the system of
record. Native Ollama is the default demo inference boundary. OpenAI Responses API and Claude Agent SDK are
explicitly selected cloud alternatives.
The transcript GitHub repository is an operator-time ingestion dependency, not a request-time dependency.

```text
                    ┌─────────────────────────────────────┐
                    │ Browser                             │
                    │ chat • sources • artifact sandbox   │
                    └────────────────┬────────────────────┘
                                     │ same-origin JSON
                    ┌────────────────▼────────────────────┐
                    │ FastAPI                             │
                    │ contracts • ownership • trace IDs   │
                    ├────────────┬─────────────┬───────────┤
                    │ Chat       │ Retrieval   │ Artifact  │
                    │ router     │ diversify   │ sanitizer │
                    │ skills     │ rerank      │ renderer  │
                    └─────┬──────┴──────┬──────┴─────┬─────┘
                          │             │            │
               ┌──────────▼───┐  ┌──────▼─────┐  ┌──▼────────────┐
               │ PostgreSQL   │  │ Ollama     │  │ Cloud models │
               │ state + FTS  │  │ local chat │  │ OpenAI/Claude│
               └──────▲───────┘  └────────────┘  └───────────────┘
                      │
              transcript ingestion
                      │
        ChatPRD/lennys-podcast-transcripts
```

## Component responsibilities

| Component | Owns | Does not own |
|---|---|---|
| API routes | Typed HTTP contracts, dependency construction, safe user header | Prompts or SQL details |
| `ChatService` | Request transaction, context, evidence gating, skill/provider invocation | Provider transport details |
| Router | Deterministic explicit/heuristic mode selection | Generative classification |
| Skills/prompts | Grounding, answer, Ship 30, and static artifact contracts | Source retrieval |
| Retriever | FTS candidates, source diversity, citations | Answer generation |
| Providers | Ollama chat, OpenAI Responses API, Claude Agent SDK, provider-specific errors | Session persistence |
| Artifact service | Fence extraction, Markdown rendering, allowlist sanitation, CSP shell | Browser layout |
| Repositories | Session ownership, ordered messages, artifacts, transcript search | Product decisions |
| Ingestion | Fetch, safe extract, parse, chunk, hash, upsert, run log | Request-time generation |

## Database schema

```text
chat_sessions 1 ──────── * messages
      │                       │ optional
      └──────── 1 ─────── * artifacts

transcript_sources 1 ──── * transcript_chunks

ingestion_runs (operational audit)
```

### `chat_sessions`

`id UUID-like string` primary key, `title`, indexed `user_id`, JSON `user_metadata`, timezone-aware
`created_at` and `updated_at`.

### `messages`

`id`, `session_id`, `role`, `content`, routed `mode`, `provider`, `model`, JSON citation snapshot,
optional `artifact_id`, timestamps. Citation snapshots make historic answers explainable even if the index is
later refreshed.

### `artifacts`

`id`, `session_id`, `kind`, `title`, original generated `source`, server-produced `sanitized_html`, timestamps.
Original source is available for copy/download but is never injected into the app DOM.

### `transcript_sources`

Stable folder slug `id` (deterministically hash-shortened only if it exceeds the schema limit), guest/title,
YouTube URL, publish date, source path, SHA-256 content hash, preserved safe frontmatter, and index timestamp.

### `transcript_chunks`

Stable derived `id`, source foreign key, ordinal, content, first timestamp seconds, and a stored generated
English `tsvector` with a GIN index. `(source_id, ordinal)` is unique.

### `ingestion_runs`

Run ID/status/source ref, sources seen, chunks written, error, start/completion timestamps.

Cascade deletion is limited to parent-owned session/source records. Artifacts set their message pointer to null
when removed so message history stays valid.

## API

All mutation payloads are Pydantic models with length/enum constraints. Domain errors share a stable envelope.

| Endpoint | Request | Response | Failure highlights |
|---|---|---|---|
| `GET /health/live` | — | process status | only process/framework failure |
| `GET /health/ready` | — | DB/provider/index checks | returns degraded state with reasons |
| `GET /api/config` | — | safe models, availability, retrieval/index summary | DB unavailable |
| `POST /api/sessions` | metadata JSON | session summary | validation/DB unavailable |
| `GET /api/sessions` | user header | newest 30 summaries | DB unavailable |
| `GET /api/sessions/{id}` | user header | messages/citations/artifacts | 404 for missing or wrong owner |
| `POST /api/sessions/{id}/messages` | content, mode, optional provider | persisted assistant message + trace | no session, provider config/down/timeout, DB failure |

The service intentionally maps “missing” and “not owned” to the same 404, avoiding a cross-user existence
oracle. `X-Request-Id` is accepted/returned for correlation, capped to 100 characters, and generated when absent.

## Ingestion and retrieval flow

1. Validate that automatic downloads target `github.com/{owner}/{repo}` and build a branch archive URL.
2. Stream into a temporary directory; validate every archive member resolves under that directory.
3. Find `episodes/*/transcript.md`; parse YAML frontmatter and content.
4. Split on paragraph boundaries around 1,600 characters. Carry one short paragraph as overlap and record the
   first `HH:MM:SS`/`MM:SS` timestamp.
5. Hash full source. Skip unchanged sources; replace chunks only for changed sources.
6. PostgreSQL derives `tsvector` values and maintains its GIN index.
7. At request time, `websearch_to_tsquery` returns 30 ranked candidates. Source diversity limits each episode
   to two selected chunks and returns 8.
8. Context is truncated at a configured character boundary without splitting a passage. Each passage receives
   a fixed marker included in both prompt and response citation metadata.

Follow-ups prepend the previous two user turns to the retrieval query and include up to ten recent messages in
the model conversation. Conversation text resolves intent; only retrieved passages are evidence.

## Agent routing and skills

Explicit UI mode always wins. In Auto, bounded regular expressions route recognizable essay/HTML/Markdown
requests; everything else is an Answer. Deterministic routing is cheaper, testable, and avoids using an LLM
before evidence retrieval.

- **Answer:** concise synthesis under the grounding contract.
- **Ship 30:** a checked-in skill encoding reader promise, hook, 4A-informed angle, one parallel organizing
  pattern, narrative progression, skimmability, 1,100–1,400 word range, cited claims, and final action.
- **Markdown/HTML:** static source-only generation with citations and explicit feature prohibitions.

The default Ollama adapter uses the native `/api/chat` endpoint with non-streaming bounded generation and a
model-presence health check. The OpenAI adapter uses the Responses API with response storage disabled. The
Claude adapter uses the official Agent SDK one-shot `query()` path with `max_turns=1`, no tools, and `dontAsk`
permission mode. All implement the same provider protocol and never silently fall back.

## Artifact threat model

Threats include script execution, event attributes, data exfiltration through fetch/CSS/forms/images, cookie or
storage access, parent/top navigation, nested frames, deceptive overlays, plugins, and malformed markup.

Controls:

1. Server allowlists semantic HTML tags, safe attributes, HTTPS/mail protocols, and presentation-only inline
   CSS properties; images and remote assets are removed.
2. Server removes active elements, event handlers, unsafe protocols, CSS imports, CSS `url()`, expressions,
   behaviors, and font-face rules.
3. Render output injects a CSP: no default/network/image/object/frame/form/base sources; only inline style is
   permitted.
4. Browser iframe uses `sandbox=""` (no allowances) and `referrerpolicy="no-referrer"`.
5. Original source appears only through `textContent` inside a `<code>` block and downloads as a Blob.

There is no intentional outbound rendering capability. A future image requirement should use proxied,
scanned assets on an explicit allowlist rather than weakening the viewer globally.

## Security and privacy

- `.env` and transcript downloads are ignored; secrets are neither in files nor logs.
- CORS is explicit and same-origin by default.
- API content is length-limited; modes/providers are enums.
- Session ownership is checked on reads and writes, but the current browser header is not authentication.
- Logs contain trace, provider/model, timing, status, and operational source IDs—never prompts, answers, source
  bodies, or credentials.
- Database credentials in Compose are development-only. Production uses a secret manager, TLS, rotated strong
  credentials, verified identity claims, network policy, encrypted backups, and retention/deletion rules.
- Dependencies are pinned; CI should be paired with dependency and container scanning in a production pipeline.

## Resilience and observability

| Failure | Behavior | Signal |
|---|---|---|
| Ollama stopped/model absent | Provider shown unavailable with the exact pull command | provider card, readiness check |
| Missing Claude key | Provider shown unavailable; explicit request returns 503 | provider card, structured error/log |
| Model provider unavailable | No silent fallback; actionable 503 | readiness check and error details |
| Model timeout | 504 with shorter-request/smaller-model suggestion | request ID and provider log |
| Empty retrieval | Model is not called; supported refusal persisted | empty citations and normal 200 |
| Transcript download failure | Startup continues with existing/empty index | ingestion warning and degraded readiness |
| Database failure | Liveness remains OK; readiness is degraded; stateful API fails | DB health/logs |
| Unsafe artifact | Disallowed content stripped before persistence/render | security tests, safe viewer footer |

## Deployment topology

Docker Compose creates durable PostgreSQL and transcript volumes plus two service roles: PostgreSQL and FastAPI.
The API reaches native Ollama through `host.docker.internal`, waits for database health, migrates, attempts
idempotent ingestion, then serves HTTP on port 8000. Database and transcript volumes survive normal `down`.

For managed deployment, keep FastAPI stateless behind TLS, move PostgreSQL to Supabase/Railway or another
managed service via `DATABASE_URL`, use an approved cloud model provider, run ingestion as a scheduled job,
and replace `X-User-Id` with verified identity. Do not expose PostgreSQL publicly.

## Extension seams

- Add provider adapters behind `LLMProvider` without touching routing or persistence.
- Replace/reweight search behind `KnowledgeRepository`/`Retriever`.
- Add skills as named system contracts plus deterministic routes and tests.
- Add streamed events at the `ChatService` output boundary while retaining final-message persistence.
- Add identity by replacing `current_user`; repository ownership checks already consume a trusted user ID.
- Add artifact versions by introducing `artifact_revisions` without changing the iframe boundary.
