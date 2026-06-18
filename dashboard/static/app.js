// Twitter Agent Dashboard frontend — vanilla JS, talks to the stdlib server.py API.
// Files (CSVs/YAML/Markdown) stay the source of truth (01-spec.md §10); this is a
// view/edit layer only.

const VALID_MODES = ["learn", "scroll", "compose", "send", "review"];

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const loaders = {
  drafts: loadDrafts,
  insights: loadInsights,
  config: loadConfig,
  knowledge: loadKnowledge,
  run: loadRun,
};

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    document.getElementById(`tab-${tab}`).classList.add("active");
    loaders[tab]();
  });
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function getJSON(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || `${res.status} ${url}`);
  return data;
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || `${res.status} ${url}`);
  return data;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function chip(text, cls = "") {
  return `<span class="chip ${cls}">${escapeHtml(text)}</span>`;
}

// ---------------------------------------------------------------------------
// Drafts tab
// ---------------------------------------------------------------------------

async function loadDrafts() {
  const list = document.getElementById("drafts-list");
  const banner = document.getElementById("lockout-banner");
  list.textContent = "Loading…";

  try {
    const incidents = await getJSON("/api/incidents");
    if (incidents.locked_out) {
      banner.classList.remove("hidden");
      banner.innerHTML = `Auto-lockout is active (2+ security incidents in 7 days). Review <code>data/data/incidents.csv</code>, then ` +
        `<button class="btn secondary" id="clear-lockout-btn">Clear lockout</button>`;
      banner.querySelector("#clear-lockout-btn").addEventListener("click", async () => {
        await postJSON("/api/incidents/clear-lockout");
        loadDrafts();
      });
    } else {
      banner.classList.add("hidden");
      banner.innerHTML = "";
    }

    const { drafts } = await getJSON("/api/drafts");
    if (drafts.length === 0) {
      list.innerHTML = `<p class="hint">No drafts queued. Run <code>scroll</code> or <code>compose</code> mode to generate some.</p>`;
      return;
    }
    list.innerHTML = "";
    drafts.forEach((d) => list.appendChild(renderDraftCard(d)));
  } catch (e) {
    list.textContent = `Error: ${e.message}`;
  }
}

function renderDraftCard(draft) {
  const row = draft.row;
  const card = document.createElement("div");
  card.className = "card";

  const chips = [];
  chips.push(chip(draft.type, ""));
  chips.push(chip(`status: ${row.status}`, `status-${row.status}`));
  if (draft.stale_age) chips.push(chip("stale (age)", "stale"));
  if ((row.tagged_users || "").trim()) chips.push(chip(`tags: ${row.tagged_users}`, "tag-callout"));
  if (row.reply_archetype) chips.push(chip(row.reply_archetype));
  if (row.tweet_format) chips.push(chip(row.tweet_format));
  if (row.content_type) chips.push(chip(row.content_type));
  if (row.hook_type) chips.push(chip(row.hook_type));
  if (row.thread_position) chips.push(chip(`thread: ${row.thread_position}`));
  if (row.tagging_mode) chips.push(chip(`tagging: ${row.tagging_mode}`));

  const targetLine = row.target_tweet_url
    ? `<p class="meta">Target: <a href="${escapeHtml(row.target_tweet_url)}" target="_blank" rel="noopener">${escapeHtml(row.target_tweet_url)}</a>
       ${row.target_author_handle ? ` — @${escapeHtml(row.target_author_handle)}` : ""}</p>`
    : "";

  card.innerHTML = `
    <h3>${escapeHtml(draft.id)}</h3>
    <p class="meta">drafted ${escapeHtml(row.drafted_at || "")} — ${escapeHtml(row.persona || "")}</p>
    <div class="chips">${chips.join("")}</div>
    ${targetLine}
    <label>Draft text (edit to change before approving)</label>
    <textarea class="draft-text">${escapeHtml(row.draft_text || "")}</textarea>
    <div class="actions">
      <button class="btn approve-btn">Approve</button>
      <button class="btn danger discard-btn">Discard</button>
    </div>
  `;

  card.querySelector(".approve-btn").addEventListener("click", async () => {
    const text = card.querySelector(".draft-text").value;
    try {
      await postJSON(`/api/drafts/${encodeURIComponent(draft.id)}/approve`, { edited_text: text });
      loadDrafts();
    } catch (e) {
      alert(`Approve failed: ${e.message}`);
    }
  });

  card.querySelector(".discard-btn").addEventListener("click", async () => {
    const reason = prompt("Discard reason (optional):", "");
    if (reason === null) return; // cancelled
    try {
      await postJSON(`/api/drafts/${encodeURIComponent(draft.id)}/discard`, { reason: reason || undefined });
      loadDrafts();
    } catch (e) {
      alert(`Discard failed: ${e.message}`);
    }
  });

  return card;
}

// ---------------------------------------------------------------------------
// Insights tab
// ---------------------------------------------------------------------------

async function loadInsights() {
  const el = document.getElementById("insights-content");
  el.textContent = "Loading…";
  try {
    const data = await getJSON("/api/insights");
    el.innerHTML = "";
    el.appendChild(renderFunnel("Replies / thread-replies / quotes", data.funnel.replies));
    el.appendChild(renderFunnel("Original tweets", data.funnel.tweets));
    el.appendChild(renderEditRate(data.edit_rate));
    el.appendChild(renderPerformance("By reply archetype", data.performance.by_reply_archetype));
    el.appendChild(renderPerformance("By content type", data.performance.by_content_type));
    el.appendChild(renderProfiles(data.profiles));
  } catch (e) {
    el.textContent = `Error: ${e.message}`;
  }
}

function renderFunnel(title, counts) {
  const wrap = document.createElement("div");
  const rows = Object.entries(counts).map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${v}</td></tr>`).join("");
  wrap.innerHTML = `<h3>${escapeHtml(title)}</h3><table><tr><th>Status</th><th>Count</th></tr>${rows}</table>`;
  return wrap;
}

function renderEditRate(editRate) {
  const wrap = document.createElement("div");
  const rate = editRate.rate === null ? "n/a" : `${(editRate.rate * 100).toFixed(1)}%`;
  wrap.innerHTML = `<h3>Edit rate (sent items)</h3>
    <table><tr><th>Sent</th><th>Edited</th><th>Rate</th></tr>
    <tr><td>${editRate.sent}</td><td>${editRate.edited}</td><td>${rate}</td></tr></table>`;
  return wrap;
}

function renderPerformance(title, breakdown) {
  const wrap = document.createElement("div");
  const entries = Object.entries(breakdown);
  if (entries.length === 0) {
    wrap.innerHTML = `<h3>${escapeHtml(title)}</h3><p class="hint">No reviewed items with engagement_rate yet.</p>`;
    return wrap;
  }
  const rows = entries.map(([k, v]) =>
    `<tr><td>${escapeHtml(k)}</td><td>${v.n}</td><td>${(v.avg_engagement_rate * 100).toFixed(2)}%</td></tr>`
  ).join("");
  wrap.innerHTML = `<h3>${escapeHtml(title)}</h3>
    <table><tr><th>Group</th><th>N</th><th>Avg engagement rate</th></tr>${rows}</table>`;
  return wrap;
}

function renderProfiles(profiles) {
  const wrap = document.createElement("div");
  if (profiles.length === 0) {
    wrap.innerHTML = `<h3>Profiles</h3><p class="hint">No profiles recorded yet.</p>`;
    return wrap;
  }
  const rows = profiles.map((p) => `<tr>
    <td>@${escapeHtml(p.handle)}</td>
    <td>${escapeHtml(p.category)}</td>
    <td>${escapeHtml(p.follower_tier)}</td>
    <td>${escapeHtml(p.relevance)}</td>
    <td>${escapeHtml(p.credibility)}</td>
    <td>${escapeHtml(p.relationship)}</td>
    <td>${escapeHtml(p.times_engaged)}</td>
  </tr>`).join("");
  wrap.innerHTML = `<h3>Profiles</h3>
    <table><tr><th>Handle</th><th>Category</th><th>Follower tier</th><th>Relevance</th><th>Credibility</th><th>Relationship</th><th>Times engaged</th></tr>${rows}</table>`;
  return wrap;
}

// ---------------------------------------------------------------------------
// Config tab
// ---------------------------------------------------------------------------

async function loadConfig() {
  const el = document.getElementById("config-content");
  el.textContent = "Loading…";
  try {
    const [limits, metrics, persona, files] = await Promise.all([
      getJSON("/api/config/limits"),
      getJSON("/api/config/metrics"),
      getJSON("/api/config/persona"),
      getJSON("/api/files"),
    ]);
    el.innerHTML = "";
    el.appendChild(renderLimitsForm(limits));
    el.appendChild(renderMetricsForm(metrics));
    el.appendChild(renderPersonaForm(persona));
    el.appendChild(renderMdEditor(files.files));
  } catch (e) {
    el.textContent = `Error: ${e.message}`;
  }
}

function renderLimitsForm(limits) {
  const wrap = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = "data/config/limits.yaml";
  wrap.appendChild(legend);

  const inputs = {};
  for (const [key, value] of Object.entries(limits)) {
    const label = document.createElement("label");
    label.textContent = key;
    const input = document.createElement("input");
    input.type = "number";
    input.value = value;
    input.dataset.key = key;
    inputs[key] = input;
    wrap.appendChild(label);
    wrap.appendChild(input);
  }

  const status = document.createElement("p");
  status.className = "hint";
  const saveBtn = document.createElement("button");
  saveBtn.className = "btn";
  saveBtn.textContent = "Save limits";
  saveBtn.addEventListener("click", async () => {
    const updates = {};
    for (const [key, input] of Object.entries(inputs)) {
      updates[key] = parseInt(input.value, 10);
    }
    try {
      await postJSON("/api/config/limits", updates);
      status.textContent = "Saved.";
    } catch (e) {
      status.textContent = `Error: ${e.message}`;
    }
  });
  wrap.appendChild(document.createElement("br"));
  wrap.appendChild(saveBtn);
  wrap.appendChild(status);
  return wrap;
}

function renderMetricsForm(metrics) {
  const wrap = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = "data/config/metrics.yaml (comma-separated lists)";
  wrap.appendChild(legend);

  const inputs = {};
  for (const [key, items] of Object.entries(metrics)) {
    const label = document.createElement("label");
    label.textContent = key;
    const input = document.createElement("input");
    input.type = "text";
    input.style.width = "100%";
    input.value = items.join(", ");
    inputs[key] = input;
    wrap.appendChild(label);
    wrap.appendChild(input);
  }

  const status = document.createElement("p");
  status.className = "hint";
  const saveBtn = document.createElement("button");
  saveBtn.className = "btn";
  saveBtn.textContent = "Save metrics config";
  saveBtn.addEventListener("click", async () => {
    const updates = {};
    for (const [key, input] of Object.entries(inputs)) {
      updates[key] = input.value.split(",").map((s) => s.trim()).filter(Boolean);
    }
    try {
      await postJSON("/api/config/metrics", updates);
      status.textContent = "Saved.";
    } catch (e) {
      status.textContent = `Error: ${e.message}`;
    }
  });
  wrap.appendChild(document.createElement("br"));
  wrap.appendChild(saveBtn);
  wrap.appendChild(status);
  return wrap;
}

function renderPersonaForm(persona) {
  const wrap = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = "Active persona & tagging (AGENTS.md §0)";
  wrap.appendChild(legend);

  const personaLabel = document.createElement("label");
  personaLabel.textContent = "persona";
  const personaSelect = document.createElement("select");
  persona.available.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    if (p === persona.active.persona) opt.selected = true;
    personaSelect.appendChild(opt);
  });

  const taggingLabel = document.createElement("label");
  taggingLabel.textContent = "tagging";
  const taggingSelect = document.createElement("select");
  ["on", "off"].forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    if (t === persona.active.tagging) opt.selected = true;
    taggingSelect.appendChild(opt);
  });

  const status = document.createElement("p");
  status.className = "hint";
  const saveBtn = document.createElement("button");
  saveBtn.className = "btn";
  saveBtn.textContent = "Save";
  saveBtn.addEventListener("click", async () => {
    try {
      await postJSON("/api/config/persona", { persona: personaSelect.value, tagging: taggingSelect.value });
      status.textContent = "Saved.";
    } catch (e) {
      status.textContent = `Error: ${e.message}`;
    }
  });

  wrap.appendChild(personaLabel);
  wrap.appendChild(personaSelect);
  wrap.appendChild(taggingLabel);
  wrap.appendChild(taggingSelect);
  wrap.appendChild(document.createElement("br"));
  wrap.appendChild(saveBtn);
  wrap.appendChild(status);
  return wrap;
}

function renderMdEditor(files) {
  const wrap = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = "Edit guidelines / private data style / persona / writing / learnings files";
  wrap.appendChild(legend);

  const label = document.createElement("label");
  label.textContent = "file";
  const select = document.createElement("select");
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "— choose a file —";
  select.appendChild(placeholder);
  files.forEach((f) => {
    const opt = document.createElement("option");
    opt.value = f;
    opt.textContent = f;
    select.appendChild(opt);
  });

  const textarea = document.createElement("textarea");
  textarea.style.minHeight = "16rem";
  textarea.disabled = true;

  const status = document.createElement("p");
  status.className = "hint";
  const saveBtn = document.createElement("button");
  saveBtn.className = "btn";
  saveBtn.textContent = "Save file";
  saveBtn.disabled = true;

  select.addEventListener("change", async () => {
    if (!select.value) {
      textarea.value = "";
      textarea.disabled = true;
      saveBtn.disabled = true;
      return;
    }
    try {
      const data = await getJSON(`/api/file?path=${encodeURIComponent(select.value)}`);
      textarea.value = data.content;
      textarea.disabled = false;
      saveBtn.disabled = false;
      status.textContent = "";
    } catch (e) {
      status.textContent = `Error: ${e.message}`;
    }
  });

  saveBtn.addEventListener("click", async () => {
    try {
      const result = await postJSON("/api/file", { path: select.value, content: textarea.value });
      status.textContent = `Saved (last_updated: ${result.last_updated}).`;
    } catch (e) {
      status.textContent = `Error: ${e.message}`;
    }
  });

  wrap.appendChild(label);
  wrap.appendChild(select);
  wrap.appendChild(textarea);
  wrap.appendChild(document.createElement("br"));
  wrap.appendChild(saveBtn);
  wrap.appendChild(status);
  return wrap;
}

// ---------------------------------------------------------------------------
// Run tab
// ---------------------------------------------------------------------------

async function loadRun() {
  const el = document.getElementById("run-content");
  el.textContent = "Loading…";
  try {
    const [state, persona] = await Promise.all([
      getJSON("/api/run/state"),
      getJSON("/api/config/persona"),
    ]);
    el.innerHTML = "";

    const modeLabel = document.createElement("label");
    modeLabel.textContent = "mode";
    const modeSelect = document.createElement("select");
    VALID_MODES.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      modeSelect.appendChild(opt);
    });

    const personaLabel = document.createElement("label");
    personaLabel.textContent = "persona (optional override)";
    const personaSelect = document.createElement("select");
    const defaultOpt = document.createElement("option");
    defaultOpt.value = "";
    defaultOpt.textContent = `— active (${persona.active.persona || "default"}) —`;
    personaSelect.appendChild(defaultOpt);
    persona.available.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      personaSelect.appendChild(opt);
    });

    const taggingLabel = document.createElement("label");
    const taggingCheckbox = document.createElement("input");
    taggingCheckbox.type = "checkbox";
    taggingCheckbox.id = "tagging-checkbox";
    taggingCheckbox.disabled = modeSelect.value !== "scroll";
    taggingLabel.appendChild(taggingCheckbox);
    taggingLabel.appendChild(document.createTextNode(" --tagging (scroll mode only)"));

    modeSelect.addEventListener("change", () => {
      taggingCheckbox.disabled = modeSelect.value !== "scroll";
      if (taggingCheckbox.disabled) taggingCheckbox.checked = false;
    });

    const launchBtn = document.createElement("button");
    launchBtn.className = "btn";
    launchBtn.textContent = "Launch";

    const status = document.createElement("p");
    status.className = "hint";

    const stateBox = document.createElement("pre");
    stateBox.textContent = JSON.stringify(state.last_launch || { last_launch: null }, null, 2);

    launchBtn.addEventListener("click", async () => {
      try {
        const result = await postJSON("/api/run/launch", {
          mode: modeSelect.value,
          persona: personaSelect.value || undefined,
          tagging: taggingCheckbox.checked,
        });
        status.textContent = `Launched ${result.last_launch.mode} in a new terminal.`;
        stateBox.textContent = JSON.stringify(result.last_launch, null, 2);
      } catch (e) {
        status.textContent = `Error: ${e.message}`;
      }
    });

    el.appendChild(modeLabel);
    el.appendChild(modeSelect);
    el.appendChild(personaLabel);
    el.appendChild(personaSelect);
    el.appendChild(taggingLabel);
    el.appendChild(document.createElement("br"));
    el.appendChild(launchBtn);
    el.appendChild(status);
    el.appendChild(document.createElement("h3")).textContent = "Last launch";
    el.appendChild(stateBox);
    el.appendChild((() => {
      const p = document.createElement("p");
      p.className = "hint";
      p.innerHTML = "Opens a new terminal in <code>twitter-agent/</code> with the mode prompt pre-filled — this dashboard does not stream agent output (see <code>dashboard/README.md</code>, Known limitations).";
      return p;
    })());
  } catch (e) {
    el.textContent = `Error: ${e.message}`;
  }
}

// ---------------------------------------------------------------------------
// Knowledge tab
// ---------------------------------------------------------------------------

const KB_SECTION_LABELS = {
  persona: "Persona",
  style: "Style",
  learnings: "Learnings",
  guidelines: "Guidelines",
};

async function loadKnowledge() {
  const el = document.getElementById("knowledge-content");
  el.textContent = "Loading…";
  try {
    const data = await getJSON("/api/knowledge");
    el.innerHTML = "";
    for (const [key, label] of Object.entries(KB_SECTION_LABELS)) {
      el.appendChild(renderKbSection(label, data[key] || []));
    }
  } catch (e) {
    el.textContent = `Error: ${e.message}`;
  }
}

function renderKbSection(title, files) {
  const section = document.createElement("div");
  section.className = "kb-section";
  const h3 = document.createElement("h3");
  h3.textContent = title;
  section.appendChild(h3);
  files.forEach((file) => section.appendChild(renderKbPanel(file)));
  return section;
}

function renderKbPanel(file) {
  const details = document.createElement("details");
  details.className = "kb-panel";

  const summary = document.createElement("summary");
  summary.textContent = file.path;
  details.appendChild(summary);

  const body = document.createElement("div");
  body.className = "md-body";
  body.innerHTML = renderMarkdown(file.content);
  details.appendChild(body);

  return details;
}

function renderMarkdown(md) {
  // Strip HTML comments
  md = md.replace(/<!--[\s\S]*?-->/g, "");

  const lines = md.split("\n");
  const out = [];
  let inUl = false;

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    // Horizontal rule / frontmatter divider
    if (/^-{3,}$/.test(line.trim())) {
      if (inUl) { out.push("</ul>"); inUl = false; }
      out.push("<hr>");
      continue;
    }

    // Headings — shift +2 so # → h3, ## → h4, ### → h5 (avoids clashing with tab h2)
    const hMatch = line.match(/^(#{1,4})\s+(.*)/);
    if (hMatch) {
      if (inUl) { out.push("</ul>"); inUl = false; }
      const level = Math.min(hMatch[1].length + 2, 6);
      out.push(`<h${level}>${inlineMd(hMatch[2])}</h${level}>`);
      continue;
    }

    // Unordered list items
    const liMatch = line.match(/^[-*]\s+(.*)/);
    if (liMatch) {
      if (!inUl) { out.push("<ul>"); inUl = true; }
      out.push(`<li>${inlineMd(liMatch[1])}</li>`);
      continue;
    }

    // Blank line
    if (line.trim() === "") {
      if (inUl) { out.push("</ul>"); inUl = false; }
      continue;
    }

    // Paragraph
    if (inUl) { out.push("</ul>"); inUl = false; }
    out.push(`<p>${inlineMd(line)}</p>`);
  }

  if (inUl) out.push("</ul>");
  return out.join("\n");
}

function inlineMd(text) {
  // Escape HTML first so content inside patterns is safe
  text = text.replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  // Bold **text**
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic *text* (single asterisk only)
  text = text.replace(/\*([^*\n]+?)\*/g, "<em>$1</em>");
  // Inline code `text`
  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Markdown links [label](url)
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return text;
}

// ---------------------------------------------------------------------------
// Initial load
// ---------------------------------------------------------------------------

loadDrafts();



