# Manual evaluator test plan

Run these checks after `docker compose up --build` reports the API started.

## Clean-clone gate

1. Clone into a new directory with no `.env`.
2. Run only `docker compose up --build`.
3. Verify `http://localhost:8000/health/live` returns `ok`.
4. Verify `/health/ready` identifies PostgreSQL, Ollama/model, source count, and chunk count; wait until the
   UI library pill shows nonzero episodes.
5. Confirm no secret-looking values or raw prompt/transcript content appear in logs.

## Core journey

1. Ask “How should an early-stage team find and validate product-market fit?”
2. Confirm the answer names `qwen3:4b-instruct` (or configured model), contains valid `[S#]` markers, and has source cards.
3. Open two source cards. Confirm guest/title/excerpt are relevant and a timestamped link opens the episode.
4. Ask “Where do these guests disagree?” Confirm the answer resolves “these guests” from session context and
   still cites retrieved evidence.
5. Open a new conversation; confirm the previous context does not affect the new answer.
6. Reload the page and reopen both chats from history; messages, timestamps/order, citations, and titles persist.

## Skills and artifacts

1. Select **Ship 30 essay**; request an essay about activation.
2. Confirm roughly 1,100–1,400 words, a specific hook, parallel headings, skimmable formatting, source markers,
   and one concrete final action.
3. Select **Markdown artifact**; request a one-page growth experiment brief. Confirm the side viewer opens,
   Preview/Source work, and copy/download returns `.md` source.
4. Select **HTML artifact**; request a responsive executive briefing card. Resize the browser and confirm the
   artifact remains legible. Download returns `.html`.
5. Submit an HTML request explicitly asking for a script, form, iframe, and remote tracking CSS. Confirm they
   do not execute/appear in the rendered preview; inspect Source versus sanitized Preview if useful.

## Failure behavior

1. Stop Ollama and confirm the UI shows the local provider as unavailable; restart it and confirm readiness.
2. Temporarily rename the configured model and confirm the status provides the correct `ollama pull` command.
3. Ask a clearly out-of-domain question such as local weather. Confirm a supported refusal with no citations.
4. Choose Claude without `ANTHROPIC_API_KEY`. Confirm it is marked Unavailable and sending returns a clear error.
5. Stop PostgreSQL. Confirm `/health/live` stays `ok`, `/health/ready` becomes degraded, and the UI does not
   pretend that new state was saved.
6. Restart services and confirm prior conversations remain.

## Responsive and accessibility

1. Test at 1440×900, 820×1180, and 360×800.
2. At mobile width, confirm history is a dismissible drawer and an artifact occupies the usable screen with a
   clear close control.
3. Navigate new chat, history, prompt starters, composer, modes, source drawers, provider dialog, and artifact
   tabs using only keyboard.
4. Confirm focus is visible, dialog focus is contained by the browser, and Cmd/Ctrl+Enter sends.
5. Zoom text to 200%; confirm main actions and content remain usable without clipped horizontal controls.
6. Enable reduced-motion preference; transitions should become effectively immediate.

Record failures with request ID, action, expected/actual result, browser size, provider/model, and the relevant
structured log entry.
