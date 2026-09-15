# Design rationale

## Experience thesis

This is a **research desk, not a chatbot toy**. The interface should feel like a calm editorial workspace:
credible enough for strategy work, fast enough for a question between meetings, and explicit about where
every answer came from. Deep green signals the transcript library; paper and ink make long reading
comfortable; a sharp citrus accent marks live local infrastructure; orange is reserved for emphasis and
risk.

The memorable interaction is the split: conversation remains anchored while a finished briefing opens as a
clean page beside it. Users never have to interpret a code block or leave the product to judge the output.

## Principles

1. **Start with the job.** The first viewport opens on the composer and four concrete product tasks, not a
   marketing hero or feature tour.
2. **Trust is a visible state.** Model, index size, inline markers, source excerpts, guest, episode, and
   timestamp are available without exposing infrastructure jargon in the main flow.
3. **Complexity is progressive.** Ordinary questions require only typing. Response mode, source evidence,
   provider choice, and artifact source stay one interaction away.
4. **Reading gets the space.** Serif display type adds editorial character; 16px body text, short line lengths,
   generous leading, and restrained surfaces support long answers.
5. **Local/cloud boundaries are explicit.** Provider availability and model names are visible. The copy states
   why no silent fallback occurs.
6. **Artifacts remain subordinate to the conversation.** They open when created, can be closed, and do not
   replace the evidence trail.

## Information architecture

```text
Application
├── Conversation history
│   ├── New conversation
│   └── Recent session titles
├── Active conversation
│   ├── Provider / knowledge status
│   ├── Messages
│   │   ├── Answer
│   │   ├── Inline source markers
│   │   └── Expandable source excerpts
│   └── Composer
│       └── Auto / Answer / Essay / Markdown / HTML
├── Artifact viewer
│   ├── Preview
│   ├── Source
│   └── Copy / Download / Security status
└── Model routing dialog
    ├── Ollama availability and local model
    ├── OpenAI availability and model
    └── Claude availability and model
```

## Key interaction states

- **First use:** focused question framing plus four realistic prompts; composer remains the primary action.
- **Loading:** user message appears immediately; the status moves from finding transcript evidence to local
  model synthesis without pretending that non-streamed output is token streaming.
- **Grounded success:** concise formatted response, visible model badge, inline markers, collapsed evidence.
- **Unsupported:** direct “not enough transcript evidence” language and query-reframing suggestion.
- **Dependency error:** short toast with the server's safe recovery message; the user's message remains in the
  persisted chat so retry context is not lost.
- **Artifact success:** desktop becomes a balanced split view; preview is default and source is one tab away.
- **Provider unavailable:** provider card remains visible for diagnosis but is disabled. The app never routes
  a request to it or changes providers silently.
- **Empty history/index:** purposeful copy and zero-count readiness, never fabricated content.

## Responsive behavior

- **Desktop (>1080px):** 268px persistent history rail. Chat uses a centered reading column. Artifact opens in
  a roughly 45/55 split to favor the finished work.
- **Tablet (821–1080px):** narrower adaptive split, one-column prompt starters, retained side-by-side artifact.
- **Mobile (≤820px):** history becomes a dismissible drawer; artifact becomes the full working surface with a
  clear close action; status collapses to an indicator while retaining an accessible label.
- **Small mobile (≤520px):** mode control expands, keyboard hint disappears, and optional fourth starter is
  removed to protect the composer and reading space.

No information is available only on hover. Touch targets are approximately 34px or larger, and primary
actions remain reachable without horizontal scrolling.

## Accessibility

- Semantic `aside`, `nav`, `main`, `header`, `section`, `article`, and `footer` landmarks.
- Explicit labels for composer, mode selection, viewer, controls, and dialogs.
- Keyboard send uses Cmd/Ctrl+Enter while the normal form submit remains available.
- Visible focus rings, native dialog focus management, logical DOM order, and live regions for messages/toasts.
- Text is at least 16px for primary reading; small metadata is nonessential and remains high contrast.
- Color is never the sole availability signal: status includes words such as Ready/Unavailable.
- `prefers-reduced-motion` collapses transitions and loading animation duration.
- Generated HTML is encouraged to be semantic and is isolated under the same accessibility expectations.

## Content design

Labels describe outcomes: “Ship 30 essay,” “Markdown artifact,” “Open transcript passages.” The first screen
states the evidence boundary and exposes three concrete trust signals instead of a generic chatbot greeting. Error messages
name the unavailable component and offer one recovery path. The interface does not explain itself with
taglines or evaluator language. Starter questions represent common jobs and set an appropriate level of
specificity.

## Decisions and trade-offs

- **No streaming in v1:** a single persisted assistant response makes failure/retry behavior simpler across
  the provider adapters. The loading state is honest. Server-sent token streaming is an extension point.
- **Custom lightweight client:** FastAPI serves the frontend directly, eliminating Node from the evaluator's
  runtime and keeping one application origin. Native browser APIs provide all required interactions.
- **Collapsed sources:** showing every excerpt inline would overwhelm answers. Markers maintain proximity;
  drawers preserve auditability.
- **No dark-mode toggle:** the designed paper/ink artifact workspace is deliberate. System-theme support can
  follow after core usability is validated.
