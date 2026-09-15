# 2–3 minute demo video outline

Camera stays enabled. Before recording, start Ollama, pull `qwen3:4b-instruct`, and complete the transcript index.
Keep `/health/ready` and the app open in separate tabs.

## 0:00–0:25 — Problem and product judgment

“Product teams have access to hundreds of excellent Lenny transcripts, but turning them into a decision takes
search, synthesis, provenance checking, and reformatting. This app makes that a single grounded workflow. My
success bar is useful, source-supported answers and a fresh-clone startup another engineer can operate.”

Show the main screen, nonzero library count, and the lower-left `Ollama · qwen3:4b-instruct` state.

## 0:25–1:15 — Grounded local conversation

Ask: “How should an early-stage team find and validate product-market fit?”

While it runs: “This request runs locally through Ollama. PostgreSQL full-text search selects transcript
passages before the model runs; conversation history helps resolve follow-ups but never becomes evidence.”

Open one `[S#]` marker/source drawer and point to guest, episode, exact excerpt, and timestamp link. Ask the
prepared follow-up: “What should a five-person team do next week?”

## 1:15–2:05 — Content skill and artifact

Select **HTML artifact** and use a prepared prompt: “Create an HTML executive briefing card from this advice,
with three actions and risks.”

Show the side-by-side viewer, Preview/Source, then download. Briefly show **Ship 30 essay** in the mode control:
“That route uses a checked-in skill—narrow reader promise, hook, consistent structure, skimmability, concrete
takeaway, and 1,250-word target—rather than a one-off hidden prompt.”

## 2:05–2:40 — Important trade-off and security

“My key trade-off was static artifacts instead of arbitrary mini-apps. Generated HTML is hostile. The server
allowlists markup and CSS, adds a restrictive CSP, and the browser uses an iframe with no sandbox allowances.
Scripts, forms, storage, navigation, nested frames, and network calls are blocked. That covers the internal
briefing use case without giving generated code app privileges.”

Show the security footer, then the provider dialog and no-silent-fallback note.

## 2:40–3:00 — Handoff

Show `/health/ready` briefly. “One Docker Compose command migrates PostgreSQL, refreshes
the transcripts, and starts the app. The repo includes the PRD, architecture, design rationale, structured
logs, automated tests, failure guidance, and this clean-clone manual plan.”

End on the working product. Upload as unlisted/public YouTube, verify sound and camera, then add the URL to the
README submission checklist before submitting.
