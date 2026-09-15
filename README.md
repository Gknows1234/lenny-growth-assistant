# The Lenny Growth Assistant

A full-stack assistant that answers product and growth questions from Lenny's Podcast
transcripts, writes Ship 30 for 30–style essays, and renders Markdown or HTML/CSS artifacts beside the
conversation.

The evaluator-facing defaults are intentional: PostgreSQL persists every session, Ollama provides the
required local inference path, OpenAI and Claude remain optional cloud choices, retrieved transcript passages
appear as inspectable citations, and generated HTML is treated as untrusted.

## Quick start

Prerequisites: Docker Desktop with Compose v2 and [Ollama](https://ollama.com/download/windows).

Install the demo model once and keep Ollama running:

```bash
ollama pull qwen3:4b-instruct
```

```bash
git clone https://github.com/Gknows1234/lenny-growth-assistant.git
cd lenny-growth-assistant
cp .env.example .env             # Windows PowerShell: Copy-Item .env.example .env
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). API documentation is at
[http://localhost:8000/docs](http://localhost:8000/docs).

The first run downloads the public transcript archive, runs the database migration, and creates the search
index. It can take several minutes. Later starts reuse the Docker volumes. Follow progress with:

```bash
docker compose logs -f api
```

The copied `.env` defaults to Ollama at `host.docker.internal:11434`; no API key is required for the submitted
demo. Optional cloud API keys stay server-side and are never returned by `/api/config` or sent to the browser.

## What to try

- Ask: “How should an early-stage team find and validate product-market fit?”
- Follow up: “Where do the guests disagree?”
- Choose **Ship 30 essay** and ask for a practical essay on improving activation.
- Choose **HTML artifact** and ask for an executive briefing card on product reviews.
- Open a source drawer and follow a timestamped link back to the episode.
- Open **Model routing** in the lower-left corner to inspect or change the active provider.

## Architecture at a glance

```text
Browser (chat + sandboxed artifact iframe)
        │ JSON / explicit provider + mode
        ▼
FastAPI ── session/router/skills ── Ollama / qwen3:4b-instruct (default)
   │                 ├───────────── OpenAI Responses API (optional)
   │                 └───────────── Claude Agent SDK (optional)
   │
   ├── PostgreSQL: sessions, messages, artifacts
   └── Retrieval: PostgreSQL FTS → source diversity
                                             │
                                             └── Lenny transcript chunks + trace metadata
```

The application is intentionally one Python service plus PostgreSQL and a configurable model provider.
FastAPI serves the static
client as well as the API, avoiding a separate JavaScript build tool while preserving a full browser/API
boundary. See [architecture.md](architecture.md) for component, schema, API, security, and deployment
details.

## Model configuration

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | Server default: `ollama`, `openai`, or `claude` |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` in Compose | Native Ollama API reachable from the API container |
| `OLLAMA_MODEL` | `qwen3:4b-instruct` | Local demo model; about 2.5 GB |
| `OLLAMA_TIMEOUT_SECONDS` | `180` | Local generation timeout |
| `OPENAI_API_KEY` | empty | Optional server-side OpenAI credential |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI Responses API model |
| `OPENAI_TIMEOUT_SECONDS` | `180` | OpenAI request timeout |
| `ANTHROPIC_API_KEY` | empty | Optional Claude Agent SDK credential |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Cloud model name |
| `MAX_HISTORY_CHARS` | `12000` | Hard bound on prior conversation context |

The Ollama adapter uses `POST /api/chat` with streaming disabled, a bounded output budget, and the same grounded
system contract as the cloud adapters. The OpenAI adapter uses `POST /v1/responses` and sets `store=false`.
The UI shows the provider and model. A browser may choose a provider per request; the selection does not change
server settings. There is no silent fallback: the API returns a structured `provider_unavailable` error, and
users can explicitly choose another configured provider.

### Run the required local Ollama demo

```bash
ollama pull qwen3:4b-instruct
ollama list
docker compose up --build
```

Open the model-status dialog and confirm `ollama · qwen3:4b-instruct · Ready`. If you run FastAPI directly
instead of in Docker, set `OLLAMA_BASE_URL=http://127.0.0.1:11434`.

### Enable OpenAI

Set `OPENAI_API_KEY`, change `LLM_PROVIDER=openai`, and restart the API. You can also leave Ollama as the server
default and choose OpenAI explicitly in the UI.

### Enable Claude Agent SDK

Create `.env` (never commit it):

```dotenv
ANTHROPIC_API_KEY=your-key
LLM_PROVIDER=claude
CLAUDE_MODEL=claude-sonnet-4-6
```

Then restart the API:

```bash
docker compose up --build api
```

The cloud adapter uses `claude-agent-sdk`, limits each request to one turn, disables tools, and supplies
retrieved evidence in the system context. Application sessions remain controlled and persisted by this
service rather than delegated to a provider.

## Knowledge ingestion and grounding

The source is the public
[ChatPRD Lenny's Podcast transcript archive](https://github.com/ChatPRD/lennys-podcast-transcripts).
At startup, `scripts/ingest.py`:

1. downloads the configured GitHub branch archive using an allowlisted GitHub repository URL;
2. reads each `episodes/{guest}/transcript.md` and its YAML frontmatter;
3. chunks at paragraph/speaker boundaries to about 1,600 characters with a small boundary overlap;
4. extracts the first timestamp in each chunk and retains episode title, guest, URL, path, and content hash;
5. skips unchanged sources and atomically replaces changed source chunks;
6. indexes chunk text with a generated PostgreSQL `tsvector` and GIN index;
7. records an ingestion run for operational traceability.

Refresh manually with `make ingest` or:

```bash
docker compose exec api python -m scripts.ingest --refresh
```

Answers receive only retrieved passages labeled `[S1]`, `[S2]`, and so on. The prompt contract forbids
outside knowledge and invented sources. Unknown citation markers are removed, source cards return the
exact excerpt, and timestamped YouTube links make claims auditable. When retrieval is empty, the model is
not called; the assistant acknowledges that the library does not support an answer.

## API contracts

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health/live` | Process liveness |
| `GET` | `/health/ready` | Database, model, and knowledge readiness |
| `GET` | `/api/config` | Safe provider/model and index visibility |
| `POST` | `/api/sessions` | Start an independent persisted chat |
| `GET` | `/api/sessions` | List the current user's chats |
| `GET` | `/api/sessions/{id}` | Restore messages, citations, and artifacts |
| `POST` | `/api/sessions/{id}/messages` | Retrieve evidence, route the skill, and answer |

The browser supplies an opaque `X-User-Id` stored in local storage. This is tenant separation for the
take-home, not authentication. Production deployment must replace it with verified identity at the edge.
Validation and operational errors use:

```json
{
  "error": {
    "code": "provider_unavailable",
    "message": "OpenAI could not complete the request.",
    "details": {"provider": "openai", "model": "gpt-4o-mini", "trace_id": "…"}
  }
}
```

Every response also carries `X-Request-Id` and `Server-Timing`; model, retrieval/generation timing, path,
status, and duration appear in structured JSON
logs without transcript contents, prompts, API keys, or generated content.

## Artifact security

Generated HTML is hostile by default. The server strips scripts, forms, inputs, iframes, objects, event
handlers, unsafe URL protocols, remote CSS imports, `url(...)`, and other active CSS. It allows a bounded
set of semantic tags and presentation properties. The viewer then adds a restrictive Content Security
Policy and renders the result in an iframe with an empty `sandbox` attribute and `no-referrer` policy.

This permits static text, layout, tables, inline presentation CSS, and accessible structure. It blocks script
execution, images and remote assets, app cookies/storage, form submission, top navigation, popups, network
connections, nested frames, plugins, and font loads. The defense is covered by automated tests.

## Development and tests

With Docker:

```bash
make test
make lint
```

Or with Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest --cov=app --cov-report=term-missing
ruff check .
```

The suite covers deterministic routing, empty-retrieval refusal, citation/deep-link construction,
retrieval diversity, persistence round trips, HTTP contracts, and artifact XSS/CSS isolation. The manual
browser plan is in [docs/manual-test-plan.md](docs/manual-test-plan.md).

Validation completed in the authoring workspace: lint and automated tests pass; migrations apply through
revision `0002`; and a clean Docker/PostgreSQL run indexed 303 episodes into 21,456 chunks. The native Ollama
journey passes grounded answers, contextual follow-ups, a 1,100–1,400 word essay, sanitized Markdown/HTML
artifacts, cited source links, current-information refusal, and restart persistence. Responsive browser checks
cover 360 px mobile and desktop layouts.

## Operational commands

```bash
make up       # build and run all services
make logs     # follow API and database logs
make ingest   # refresh transcripts
make test     # run tests in the API image
make down     # stop services, preserve model/database volumes
```

Back up the database with `pg_dump` before migrations or destructive maintenance. To inspect service
status, use `docker compose ps` and `/health/ready`.

## Troubleshooting

**OpenAI is not configured.** Set `OPENAI_API_KEY` in the gitignored `.env` file and restart the API. Do not
put the key in browser code or commit it.

**The library shows zero episodes.** Network access may have blocked the archive download. Run
`docker compose exec api python -m scripts.ingest --refresh`. To use an existing checkout, mount it into
the container and pass `--source /path/to/checkout`.

**Database is unavailable.** Check `docker compose logs db`, verify port 5432 is free, and confirm the
`DATABASE_URL` host is `db` inside Compose (not `localhost`). The liveness endpoint remains available;
readiness reports the failed dependency.

**Ollama is unavailable.** Start the Ollama application, run `ollama pull qwen3:4b-instruct`, and verify
`http://localhost:11434/api/tags` responds. In Docker, keep `OLLAMA_BASE_URL=http://host.docker.internal:11434`.

**Local answers are slow or low quality.** Shorten the question, reduce `RETRIEVAL_LIMIT`, or choose a
model that fits available RAM. The model layer is configuration-driven; application code does not change.

**Claude is unavailable.** Confirm the key exists only in `.env`, restart the API, and check the provider
card. The application will not silently switch providers.

## Handoff map

- [PRD.md](PRD.md): customer framing, success metrics, scope, acceptance criteria, and delivery plan
- [design.md](design.md): UX principles, states, responsive behavior, and accessibility
- [architecture.md](architecture.md): boundaries, schema, retrieval, security, and deployment
- [docs/manual-test-plan.md](docs/manual-test-plan.md): evaluator browser checks
- [docs/demo-script.md](docs/demo-script.md): a timed 2–3 minute recording outline
- [agent-transcripts/README.md](agent-transcripts/README.md): sanitized build transcript and corrections

## Source references

- [Lenny transcript archive](https://github.com/ChatPRD/lennys-podcast-transcripts)
- [Ship 30 for 30 Ultimate Guide](https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide)
- [The 5 Pillars of Digital Writing](https://www.ship30for30.com/post/the-5-pillars-of-digital-writing)
- [Claude Agent SDK for Python](https://github.com/anthropics/claude-agent-sdk-python)
- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)

## Submission checklist

- [x] Publish the source at <https://github.com/Gknows1234/lenny-growth-assistant>.
- [x] Run the clean-clone test in `docs/manual-test-plan.md`.
- [ ] Record the demo with the outline in `docs/demo-script.md` and add its YouTube URL here: **TODO — add YouTube URL before submitting**.
- [x] Confirm `.env` and secrets are absent from `git status` and history.
- [ ] Submit the repository and video URLs using the assignment form.

License: application code is provided under the [MIT License](LICENSE). The transcript archive is fetched
at runtime and remains subject to its source repository's terms.
