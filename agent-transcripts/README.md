# Sanitized coding-agent transcript

This folder records the AI-assisted implementation process, including failures and corrections. It contains no
credentials, private user data, hidden reasoning, or raw transcript bodies. Entries summarize observable inputs,
actions, tool output, and verification decisions.

## Session 2026-09-14

### Brief intake

- **Input:** Build a deployable FastAPI/PostgreSQL assistant over Lenny's Podcast transcripts,
  with switchable cloud model, sessions, grounding, Ship 30 skill, artifacts, documentation, and tests.
- **Decision:** Treat reliability and evaluator handoff as product requirements. Use the OpenAI Responses API by
  default, a Claude Agent SDK adapter as an alternative, and PostgreSQL FTS as the reliable retrieval baseline.
- **External contracts checked:** ChatPRD transcript structure/frontmatter; Ship 30 reader promise, 4A angles,
  consistent organizing pattern and hook guidance; OpenAI Responses API; Claude Agent SDK Python one-shot query
  types.

### Failed attempt: site scaffold

- **Attempt:** Run the pinned site scaffold with its required component add-on.
- **Observed result:** The environment returned “npm is not recognized.” A capability check also found no Python,
  Node, Docker, or a model runtime; only Git was present.
- **Correction:** Avoided pretending the generated starter or dependencies existed. Built a no-build-step browser
  client served by FastAPI and made Docker Compose the reproducible evaluator runtime. Kept all Python/runtime
  dependencies pinned. Execution-based validation is deferred to CI or an evaluator host with Docker.

### Architecture decisions

- Persisted sessions, messages, citation snapshots, artifacts, source metadata/chunks, and ingestion runs.
- Used deterministic task routing so explicit UI modes are testable and retrieval happens before generation.
- Made empty retrieval a model-free supported refusal.
- Limited each source to two final chunks to reduce single-episode dominance.
- Chose no silent local-to-cloud fallback because it changes cost and data boundaries.
- Stored original artifact source but rendered only a sanitized derivative in an empty-sandbox iframe.

### Implementation slices

1. Runtime/configuration, Compose, data model, and migration.
2. Transcript fetch/chunk/hash/index and optional embedding batches.
3. Retrieval, provider protocol/adapters, route classifier, prompts, and checked-in Ship 30 skill.
4. Chat transaction, citation normalization, artifact generation/sanitation/persistence.
5. Responsive chat/history/settings/artifact interface with accessible states.
6. Critical tests and evaluator documentation.

### Verification written

- Deterministic/explicit routing tests.
- Retrieval diversity, cosine, citation marker, and timestamp deep-link tests.
- Empty retrieval confirms the provider is never called.
- SQLite-backed repository round trip for session/message/artifact persistence.
- HTTP session contract and structured validation tests.
- Artifact payload tests for scripts, events, forms, inputs, unsafe URL protocols, and CSS imports.
- Clean-clone, end-to-end, failure, responsive, and keyboard manual test plan.

### Failures found during execution

- The first lint command traversed the ignored temporary Python distribution and dependency cache, creating
  irrelevant third-party findings. The lint configuration was corrected to exclude environment/cache paths and
  scan the repository.
- The first test run reported 3 failures and 13 passes. All failures traced to the artifact viewer document
  template using `str.format()` with literal CSS braces. Replacing only the named placeholders avoided CSS being
  interpreted as format fields. The sanitizer tests then passed.
- A preview-database one-liner failed because Python does not permit an `async def` after a semicolon. A small
  ignored temporary script replaced it; this did not affect product source.
- A verifier reinstall auto-selected host Python 3.14, for which pinned `asyncpg` had no wheel and local C++
  build tools were absent. Pinning the verifier to the Docker target, Python 3.12, restored the supported path.
- The first package-build retry targeted a locked user-profile cache. Pointing the temporary build cache inside
  the workspace contained the tool and produced both distribution formats successfully.

### Executed verification results

- Bootstrapped the official `uv` binary and Python 3.12 into an ignored workspace directory solely for checks.
- `ruff check .`: passed.
- `pytest --cov=app --cov-report=term-missing`: 21 passed, 77% application coverage.
- Alembic offline PostgreSQL generation: completed through revision `0001`, including generated `tsvector` and
  GIN index SQL.
- Python compilation: ingestion, migration environment/revision, and application entry point passed.
- Compose YAML: parsed with the expected `db` and `api` services.
- Local SQLite-backed HTTP smoke: `/` returned 200 with the product title, liveness returned `ok`, configuration
  returned both providers, and session creation returned a 36-character ID.
- Static frontend validation: 37 unique HTML IDs, all 35 JavaScript-queried controls present, and no CSS parser
  errors.
- Python packaging: source archive and wheel built successfully with the static client and Ship 30 skill included.

### Remaining verification constraint

Docker is not installed on the authoring host, so the clean-clone Compose path could not run here. Full
transcript ingestion and a SQLite-backed HTTP runtime were verified. OpenAI inference awaits a user-supplied
server-side API key. GitHub Actions and the documented Docker/manual gate remain required before submission.
