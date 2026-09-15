# Product requirements document

## Discovery brief

### User and problem

The primary user is a product manager, growth lead, founder, or product-operations partner making a
near-term decision: diagnose a funnel, frame a strategy, align a team, or turn research into reusable
writing. They value the practical expertise in Lenny's Podcast but cannot repeatedly search hundreds of
long transcripts, reconcile several guests' advice, track provenance, and then reformat the result.

The assistant removes that research-to-output gap. The user asks in normal language, receives a concise
answer tied to inspectable transcript passages, can follow up without restating context, and can turn the
same evidence into an essay or rendered briefing without learning prompts or moving to another tool.

### Success metrics

For an evaluator study of 20 representative product/growth questions:

- **Grounded task success:** at least 85% of answers are rated useful and fully supported by the displayed
  source passages; unsupported-answer rate is below 5%.
- **Time to evidence:** median time from opening the app to inspecting the first relevant source is under
  90 seconds on a warm configured model.
- **Operational success:** a fresh evaluator reaches a ready application with one documented command and
  no code changes; at least 95% of first-run failures identify the failed dependency in `/health/ready`.
- **Artifact safety:** 100% of the active-content payloads in the automated security suite are blocked.

### Assumptions

- This is an internal assistant for a small team; single sign-on, role administration, and usage billing
  are production follow-ons, not take-home essentials.
- Users prefer trustworthy evidence over broad world knowledge. “I don't know from these transcripts” is
  a correct product outcome.
- The public ChatPRD archive is an acceptable transcript source and its folder/frontmatter contract is
  stable enough to isolate behind one ingestion script.
- Local deployment means Docker Compose on one workstation. A managed PostgreSQL target is documented by
  the same `DATABASE_URL` contract but is not required for the demo.
- HTML artifacts are static communication surfaces, not mini applications. JavaScript and forms are not
  required and should be blocked.
- A browser-generated opaque user ID is sufficient for separating take-home sessions; it is not claimed as
  authentication.

### Scope choices

Included:

- multi-session chat with persisted context, timestamps, citations, artifacts, and user metadata;
- FastAPI contracts, validation, structured domain errors, liveness, and dependency readiness;
- PostgreSQL full-text RAG with source diversification;
- native Ollama for the required local demo, with switchable OpenAI Responses API and Claude Agent SDK adapters;
- deterministic routing across grounded answer, Ship 30 essay, Markdown, and HTML skills;
- source excerpts and timestamped episode links;
- sanitized, sandboxed side-by-side artifact rendering;
- responsive, keyboard-accessible UI, structured logs, migrations, automated tests, and one-command startup.

Intentionally excluded:

- **Authentication/RBAC:** an identity provider would be client-specific and fake auth would overstate
  security. The boundary is explicit so verified claims can replace the header later.
- **Live collaborative editing/version history:** useful after artifact demand is proven, but not necessary
  to validate grounded generation.
- **Arbitrary JavaScript artifacts:** conflicts with the threat model and is unnecessary for briefs,
  memos, frameworks, and static explainers.
- **Automatic cloud fallback:** silently creates cost and data-boundary surprises.
- **Transcript administration UI:** refresh is an operator workflow with logs, not a frequent end-user job.
- **Voice, sharing, analytics dashboards, and prompt editing:** speculative surface area outside the core job.

### Risks and trade-offs

| Risk | Product/technical choice | Residual risk |
|---|---|---|
| Hallucinated claims or sources | Evidence-only prompt, empty-result refusal, fixed markers, source drawers | A model may overgeneralize a real passage; users must inspect high-impact claims |
| Weak retrieval | PostgreSQL FTS, diversified episodes, configurable top-k | Vocabulary mismatch remains with lexical retrieval |
| Model quality | Narrow grounded context, explicit skill contracts, switchable provider | Long-form output quality varies by configured model |
| Cloud cost/data leakage | Server-side keys, explicit provider, no silent fallback, `store=false` for OpenAI | Operators remain responsible for provider terms and usage |
| Unsafe artifact rendering | Allowlist sanitizer, CSS filtering, CSP, empty iframe sandbox | Browser/sanitizer vulnerabilities require dependency updates |
| Session data leakage | Ownership check on every session route, minimal opaque user ID | Header identity is spoofable until real authentication exists |
| Source drift | Content hashes, idempotent refresh, metadata/path traceability, ingestion runs | Upstream format or availability can break refresh |
| Database failure | Health separation and structured errors; durable volumes | Chat is intentionally unavailable rather than pretending to persist |

## Product flows

### Grounded conversation

1. User opens directly onto the working surface and sees library/model readiness.
2. User asks a question or chooses a relevant starter.
3. System creates/uses an independent session, retrieves transcript passages, and routes to **Answer**.
4. Assistant answers with inline `[S#]` markers and source drawers.
5. User inspects an excerpt/link or asks a follow-up; recent chat resolves references while transcripts
   remain the only evidence.
6. If no evidence is found, the assistant states that and suggests a narrower query without calling a model.

### Ship 30 essay

1. User chooses **Ship 30 essay** or explicitly asks for one.
2. Router invokes the checked-in content skill with retrieved evidence and recent context.
3. The response targets 1,250 words with a narrow promise, hook, consistent structure, skimmable sections,
   and a concrete final action.
4. Claims retain source markers and drawers.

### Artifact

1. User chooses Markdown/HTML or asks to create a recognizable artifact.
2. Model returns source only under the static-artifact contract.
3. Server strips unsafe content, stores original source plus sanitized render, and returns both.
4. Viewer opens beside chat; user switches Preview/Source, copies, or downloads.
5. Browser renders only the sanitized document in a restricted iframe.

### Model switch

1. User opens the provider control and sees model names and availability.
2. User explicitly chooses OpenAI or Claude.
3. Choice applies to future requests. If unavailable, the request returns a specific recovery action; no paid
   fallback happens implicitly.

## Functional requirements and acceptance criteria

| Area | Acceptance criterion |
|---|---|
| Sessions | New chats have unique IDs; one user's session is not returned to another user ID; reload restores ordered messages and artifacts |
| Persistence | Session, user metadata, timestamps, roles, provider/model, citations, and artifacts reside in PostgreSQL |
| Grounding | Answer claims use only supplied passages; source cards identify episode/guest/excerpt; empty retrieval does not call the model |
| Follow-ups | At least the latest 10 messages are supplied as conversational context without becoming evidence |
| Model config | Evaluator changes provider/model through environment or visible UI without application code changes |
| Model setup | The active UI state identifies the configured cloud provider and model without exposing credentials |
| Essay | Dedicated skill targets 1,100–1,400 words, hook, parallel structure, skimmability, cited claims, and concrete action |
| Artifact | Markdown and complete static HTML/CSS render beside chat; source can be copied/downloaded |
| Security | Scripts, events, forms, unsafe URLs/CSS, storage, navigation, and network calls are blocked by sanitizer/viewer policy |
| API | OpenAPI documents typed payloads; validation/domain failures are structured; request IDs are returned |
| Operations | One command starts reusable volumes; health identifies database/model/index state; failures are logged without content/secrets |
| Responsive/a11y | Core flow works at 360 px and desktop, keyboard focus is visible, labels/landmarks exist, and reduced motion is honored |

## Non-functional requirements

- No secrets or raw prompt/transcript bodies in logs.
- Target p95 API overhead excluding model generation under 500 ms on warm local Docker.
- Retrieval context and history have configurable hard bounds.
- Source refresh is idempotent and changed-source scoped.
- All runtime dependencies are pinned and CI runs lint plus critical tests.

## Implementation plan

1. Establish schema, health contracts, structured errors, and repository boundary.
2. Add transcript fetch/parse/chunk/index with trace metadata and idempotency.
3. Implement lexical retrieval, citation assembly, and source diversity.
4. Add OpenAI Responses API and Claude Agent SDK adapters with explicit failure behavior.
5. Encode router and Ship 30/artifact skill contracts.
6. Connect session transaction and sanitized artifact persistence.
7. Build the responsive chat/artifact surface and provider/status states.
8. Cover critical behavior in tests, package with Compose, and run clean-clone/manual evaluation.

## Validation plan

Automated tests cover routing, security, retrieval, persistence, API shape, and evidence refusal. Manual
checks cover the model indicator, multi-turn context, source navigation, artifact layout, provider
failure, responsive layout, and keyboard use. A 20-question groundedness set should be added before a
production pilot, reviewed blind by two product practitioners, and stratified across PMF, activation,
retention, growth loops, product craft, and leadership.
