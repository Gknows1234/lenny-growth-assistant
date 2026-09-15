const state = {
  userId: localStorage.getItem("lenny-user-id") || crypto.randomUUID(),
  sessionId: null,
  sessions: [],
  config: null,
  provider: localStorage.getItem("lenny-provider"),
  artifact: null,
  sending: false,
};
localStorage.setItem("lenny-user-id", state.userId);
const activeSessionKey = `lenny-session-id:${state.userId}`;

const $ = (selector) => document.querySelector(selector);
const els = {
  shell: $("#app-shell"),
  sidebar: $("#sidebar"),
  history: $("#history"),
  historyEmpty: $("#history-empty"),
  title: $("#conversation-title"),
  welcome: $("#welcome"),
  messages: $("#messages"),
  scroll: $("#message-scroll"),
  form: $("#composer"),
  input: $("#message-input"),
  mode: $("#mode-select"),
  send: $("#send-button"),
  newChat: $("#new-chat"),
  menuOpen: $("#menu-open"),
  grid: $("#content-grid"),
  artifactPanel: $("#artifact-panel"),
  artifactTitle: $("#artifact-title"),
  artifactFrame: $("#artifact-frame"),
  artifactSource: $("#artifact-source code"),
  artifactSourceWrap: $("#artifact-source"),
  artifactToggle: $("#artifact-toggle"),
  previewTab: $("#preview-tab"),
  sourceTab: $("#source-tab"),
  settings: $("#settings-dialog"),
  providerOptions: $("#provider-options"),
  providerName: $("#sidebar-provider"),
  providerModel: $("#sidebar-model"),
  providerOrb: $("#sidebar-orb"),
  knowledgeCount: $("#knowledge-count"),
  knowledgePill: $("#knowledge-pill"),
  modifierKey: $("#modifier-key"),
  toast: $("#toast"),
  scrim: $("#mobile-scrim"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": state.userId,
      ...(options.headers || {}),
    },
  });
  let payload = {};
  try { payload = await response.json(); } catch (_) { /* empty response */ }
  if (!response.ok) {
    const error = new Error(payload?.error?.message || "Something went wrong.");
    error.code = payload?.error?.code;
    error.details = payload?.error?.details;
    throw error;
  }
  return payload;
}

function escapeHtml(value = "") {
  const node = document.createElement("div");
  node.textContent = value;
  return node.innerHTML;
}

function renderInline(value = "") {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[S(\d+)\]/g, '<button class="citation-marker" type="button" data-citation="S$1" title="Open source S$1">S$1</button>');
}

function renderMarkdown(value = "") {
  const output = [];
  const paragraph = [];
  let listType = null;
  let listItems = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    output.push(`<p>${paragraph.map(renderInline).join("<br>")}</p>`);
    paragraph.length = 0;
  };
  const flushList = () => {
    if (!listType) return;
    output.push(`<${listType}>${listItems.map((item) => `<li>${renderInline(item)}</li>`).join("")}</${listType}>`);
    listType = null;
    listItems = [];
  };

  for (const rawLine of String(value).replace(/\r\n/g, "\n").split("\n")) {
    const line = rawLine.trimEnd();
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    const unordered = line.match(/^[-*]\s+(.+)$/);
    const ordered = line.match(/^\d+\.\s+(.+)$/);
    const quote = line.match(/^>\s?(.+)$/);

    if (!line.trim()) {
      flushParagraph();
      flushList();
    } else if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      output.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
    } else if (unordered || ordered) {
      flushParagraph();
      const nextType = unordered ? "ul" : "ol";
      if (listType && listType !== nextType) flushList();
      listType = nextType;
      listItems.push((unordered || ordered)[1]);
    } else if (quote) {
      flushParagraph();
      flushList();
      output.push(`<blockquote>${renderInline(quote[1])}</blockquote>`);
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();
  return output.join("");
}

function showToast(message, type = "info") {
  els.toast.textContent = message;
  els.toast.className = `toast show ${type}`;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { els.toast.className = "toast"; }, 4000);
}

function formatTime(seconds) {
  if (seconds == null) return "";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`
    : `${minutes}:${String(rest).padStart(2, "0")}`;
}

function safeExternalUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch (_) {
    return null;
  }
}

function sourceMarkup(citations = []) {
  if (!citations.length) return "";
  return `
    <div class="sources">
      <button class="sources-toggle" type="button" aria-expanded="false">
        ${citations.length} transcript passage${citations.length === 1 ? "" : "s"}
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 10 4 4 4-4" /></svg>
      </button>
      <div class="source-list">
        ${citations.map((source) => {
          const url = safeExternalUrl(source.url);
          const tag = url ? "a" : "div";
          const attributes = url
            ? `href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer"`
            : 'tabindex="-1"';
          return `
          <${tag} class="source-card" ${attributes} data-source="${escapeHtml(source.id)}">
            <strong>${source.id} · ${escapeHtml(source.guest)}</strong>
            <small>${escapeHtml(source.title)}${source.timestamp_seconds != null ? ` · ${formatTime(source.timestamp_seconds)}` : ""}</small>
            <p>${escapeHtml(source.excerpt)}…</p>
          </${tag}>`;
        }).join("")}
      </div>
    </div>`;
}

function messageMarkup(message, loading = false) {
  if (message.role === "user") {
    return `<article class="message user"><div class="message-body">${escapeHtml(message.content)}</div></article>`;
  }
  const model = message.model ? `<span class="model-badge">${escapeHtml(message.model)}</span>` : "";
  const content = loading
    ? '<div class="loading-dots" aria-label="Thinking"><span></span><span></span><span></span></div>'
    : renderMarkdown(message.content);
  const artifact = message.artifact
    ? `<button class="artifact-chip" type="button" data-artifact-id="${message.artifact.id}">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM13 5v14" /></svg>
        Open ${message.artifact.kind.toUpperCase()} artifact
      </button>`
    : "";
  return `<article class="message assistant" data-message-id="${message.id || "loading"}">
    <div class="avatar" aria-hidden="true">L</div>
    <div class="message-body">
      <div class="message-meta"><strong>Lenny Assistant</strong>${model}</div>
      <div class="message-content">${content}</div>
      ${artifact}
      ${sourceMarkup(message.citations)}
    </div>
  </article>`;
}

function bindMessageInteractions() {
  document.querySelectorAll(".sources-toggle").forEach((button) => {
    button.onclick = () => {
      const group = button.closest(".sources");
      const open = group.classList.toggle("open");
      button.setAttribute("aria-expanded", String(open));
    };
  });
  document.querySelectorAll(".citation-marker").forEach((button) => {
    button.onclick = () => {
      const message = button.closest(".message");
      const group = message.querySelector(".sources");
      if (!group) return;
      group.classList.add("open");
      group.querySelector(".sources-toggle").setAttribute("aria-expanded", "true");
      group.querySelector(`[data-source="${button.dataset.citation}"]`)?.focus();
    };
  });
  document.querySelectorAll(".artifact-chip").forEach((button) => {
    button.onclick = () => {
      const artifact = currentMessages.find((item) => item.artifact?.id === button.dataset.artifactId)?.artifact;
      if (artifact) openArtifact(artifact);
    };
  });
}

let currentMessages = [];
function renderMessages(messages) {
  currentMessages = messages;
  els.welcome.hidden = messages.length > 0;
  els.messages.innerHTML = messages.map((message) => messageMarkup(message)).join("");
  els.messages.setAttribute("aria-busy", "false");
  bindMessageInteractions();
  requestAnimationFrame(() => { els.scroll.scrollTop = els.scroll.scrollHeight; });
}

function renderHistory() {
  els.historyEmpty.hidden = state.sessions.length > 0;
  els.history.innerHTML = state.sessions.map((session) => `
    <button class="history-item ${session.id === state.sessionId ? "active" : ""}" data-session-id="${session.id}">
      ${escapeHtml(session.title || "New conversation")}
    </button>`).join("");
  els.history.querySelectorAll(".history-item").forEach((button) => {
    button.onclick = () => loadSession(button.dataset.sessionId);
  });
}

async function refreshSessions() {
  state.sessions = await api("/api/sessions");
  renderHistory();
}

async function createSession() {
  const session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ user_metadata: { client: "web", locale: navigator.language } }),
  });
  state.sessionId = session.id;
  localStorage.setItem(activeSessionKey, session.id);
  currentMessages = [];
  renderMessages([]);
  closeArtifact(true);
  els.title.textContent = "New conversation";
  try { await refreshSessions(); } catch (_) { /* the session itself is still usable */ }
  return session;
}

async function loadSession(id) {
  try {
    const session = await api(`/api/sessions/${id}`);
    state.sessionId = id;
    localStorage.setItem(activeSessionKey, id);
    els.title.textContent = session.title || "New conversation";
    renderMessages(session.messages);
    renderHistory();
    closeArtifact(true);
    closeSidebar();
    const latestArtifact = [...session.messages].reverse().find((item) => item.artifact)?.artifact;
    if (latestArtifact && window.innerWidth > 820) openArtifact(latestArtifact);
  } catch (error) {
    showToast(error.message, "error");
  }
}

function loadingMessage() {
  els.welcome.hidden = true;
  els.messages.setAttribute("aria-busy", "true");
  els.messages.insertAdjacentHTML("beforeend", messageMarkup({ role: "assistant" }, true));
  els.scroll.scrollTop = els.scroll.scrollHeight;
}

function updateComposerState() {
  els.send.disabled = state.sending || !els.input.value.trim();
  els.newChat.disabled = state.sending;
  els.mode.disabled = state.sending;
  els.form.setAttribute("aria-busy", String(state.sending));
}

async function sendMessage(content) {
  if (!content.trim() || state.sending) return;
  state.sending = true;
  const clean = content.trim();
  els.input.value = "";
  resizeComposer();
  updateComposerState();
  try {
    if (!state.sessionId) await createSession();
    const targetSessionId = state.sessionId;
    currentMessages.push({ role: "user", content: clean, citations: [] });
    renderMessages(currentMessages);
    loadingMessage();
    const payload = await api(`/api/sessions/${targetSessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({
        content: clean,
        mode: els.mode.value,
        provider: state.provider || null,
      }),
    });
    await loadSession(targetSessionId);
    if (payload.message.artifact) openArtifact(payload.message.artifact);
    await refreshSessions();
  } catch (error) {
    document.querySelector('[data-message-id="loading"]')?.remove();
    els.messages.setAttribute("aria-busy", "false");
    if (!state.sessionId) els.input.value = clean;
    showToast(error.message, "error");
  } finally {
    state.sending = false;
    updateComposerState();
    resizeComposer();
    els.input.focus();
  }
}

function openArtifact(artifact) {
  state.artifact = artifact;
  els.artifactTitle.textContent = artifact.title;
  els.artifactFrame.srcdoc = artifact.rendered_html;
  els.artifactSource.textContent = artifact.source;
  els.artifactPanel.hidden = false;
  els.artifactToggle.hidden = false;
  els.grid.classList.add("has-artifact");
  showArtifactTab("preview");
}

function closeArtifact(clear = false) {
  if (clear) state.artifact = null;
  els.artifactPanel.hidden = true;
  els.grid.classList.remove("has-artifact");
  els.artifactToggle.hidden = !state.artifact;
}

function showArtifactTab(name) {
  const preview = name === "preview";
  els.artifactFrame.hidden = !preview;
  els.artifactSourceWrap.hidden = preview;
  els.previewTab.classList.toggle("active", preview);
  els.sourceTab.classList.toggle("active", !preview);
  els.previewTab.setAttribute("aria-selected", String(preview));
  els.sourceTab.setAttribute("aria-selected", String(!preview));
}

function renderConfig(config) {
  state.config = config;
  const persisted = config.providers.find((item) => item.name === state.provider);
  if (!persisted || (!persisted.available && config.providers.some((item) => item.name === config.active_provider && item.available))) {
    state.provider = config.active_provider;
    localStorage.setItem("lenny-provider", state.provider);
  }
  const selected = config.providers.find((item) => item.name === state.provider) || config.providers[0];
  els.providerName.textContent = selected?.name || "Unknown";
  els.providerModel.textContent = selected?.model || "Not configured";
  els.providerOrb.className = `status-orb ${selected?.available ? "online" : "error"}`;
  els.knowledgeCount.textContent = `${config.knowledge_base.sources.toLocaleString()} episodes · ${config.knowledge_base.chunks.toLocaleString()} passages`;
  els.providerOptions.innerHTML = config.providers.map((provider) => `
    <label class="provider-card">
      <input type="radio" name="provider" value="${provider.name}" ${provider.name === state.provider ? "checked" : ""}>
      <span class="provider-card-head">
        <strong>${escapeHtml(provider.name)}</strong>
        <span class="availability ${provider.available ? "" : "offline"}">${provider.available ? "Ready" : "Unavailable"}</span>
      </span>
      <small>${escapeHtml(provider.model)}${provider.reason ? ` · ${escapeHtml(provider.reason)}` : ""}</small>
    </label>`).join("");
  els.providerOptions.querySelectorAll("input").forEach((input) => {
    input.onchange = () => {
      state.provider = input.value;
      localStorage.setItem("lenny-provider", input.value);
      renderConfig(state.config);
    };
  });
}

function resizeComposer() {
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 160)}px`;
}

function closeSidebar() {
  els.sidebar.classList.remove("open");
  els.scrim.classList.remove("show");
  els.menuOpen.setAttribute("aria-expanded", "false");
}

els.form.onsubmit = (event) => { event.preventDefault(); sendMessage(els.input.value); };
els.input.oninput = () => {
  resizeComposer();
  updateComposerState();
};
els.input.onkeydown = (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    els.form.requestSubmit();
  }
};
els.newChat.onclick = async () => {
  try {
    await createSession();
    closeSidebar();
    els.input.focus();
  } catch (error) {
    showToast(error.message, "error");
  }
};
document.querySelectorAll(".prompt-card").forEach((button) => {
  button.onclick = () => sendMessage(button.dataset.prompt);
});
$("#artifact-close").onclick = () => closeArtifact(false);
els.artifactToggle.onclick = () => state.artifact && openArtifact(state.artifact);
els.previewTab.onclick = () => showArtifactTab("preview");
els.sourceTab.onclick = () => showArtifactTab("source");
const openSettings = () => {
  if (!els.settings.open) els.settings.showModal();
};
$("#settings-open").onclick = openSettings;
els.knowledgePill.onclick = openSettings;
$("#copy-artifact").onclick = async () => {
  if (!state.artifact) return;
  try {
    await navigator.clipboard.writeText(state.artifact.source);
    showToast("Artifact source copied.");
  } catch (_) {
    showToast("Copy was blocked by the browser. Use the Source tab and copy manually.", "error");
  }
};
$("#download-artifact").onclick = () => {
  if (!state.artifact) return;
  const extension = state.artifact.kind === "html" ? "html" : "md";
  const blob = new Blob([state.artifact.source], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${state.artifact.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "artifact"}.${extension}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
};
els.menuOpen.onclick = () => {
  els.sidebar.classList.add("open");
  els.scrim.classList.add("show");
  els.menuOpen.setAttribute("aria-expanded", "true");
};
$("#sidebar-close").onclick = closeSidebar;
els.scrim.onclick = closeSidebar;
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && els.sidebar.classList.contains("open")) closeSidebar();
});

async function init() {
  els.modifierKey.textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";
  updateComposerState();
  try {
    const [config, sessions] = await Promise.all([api("/api/config"), api("/api/sessions")]);
    renderConfig(config);
    state.sessions = sessions;
    renderHistory();
    const remembered = localStorage.getItem(activeSessionKey);
    const initialSession = sessions.find((session) => session.id === remembered) || sessions[0];
    if (initialSession) await loadSession(initialSession.id);
  } catch (error) {
    els.providerModel.textContent = "Service unavailable";
    els.providerOrb.className = "status-orb error";
    els.knowledgeCount.textContent = "Library unavailable";
    showToast(error.message || "The service is not ready yet. Refresh and try again.", "error");
  }
}

init();
