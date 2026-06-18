import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { AnimatePresence, motion } from "framer-motion";
import {
  BarChart3,
  BookOpenText,
  Check,
  FilePenLine,
  Gauge,
  Inbox,
  Play,
  RefreshCw,
  Save,
  Settings,
  ShieldAlert,
  Trash2,
  X,
} from "lucide-react";

import { api } from "./api";
import type { DraftItem, FunnelCounts, InsightsResponse, KnowledgeFile, PersonaResponse, TabKey } from "./types";
import "./styles.css";

const tabs: { key: TabKey; label: string; icon: React.ComponentType<{ size?: number }> }[] = [
  { key: "drafts", label: "Drafts", icon: Inbox },
  { key: "insights", label: "Signal", icon: BarChart3 },
  { key: "knowledge", label: "Knowledge", icon: BookOpenText },
  { key: "settings", label: "Settings", icon: Settings },
  { key: "run", label: "Run", icon: Play },
];

function useLoad<T>(loader: () => Promise<T>, deps: React.DependencyList = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await loader());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, deps);

  return { data, error, loading, reload: load };
}

function App() {
  const [active, setActive] = useState<TabKey>("drafts");

  return (
    <main className="shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />
      <aside className="nav" aria-label="Dashboard navigation">
        <div>
          <p className="eyebrow">Local Instrument</p>
          <h1>X Engagement Agent</h1>
        </div>
        <nav className="nav-list">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button key={key} className={active === key ? "nav-item active" : "nav-item"} onClick={() => setActive(key)}>
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <Header active={active} />
        <AnimatePresence mode="wait">
          <motion.div
            key={active}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18 }}
          >
            {active === "drafts" && <Drafts />}
            {active === "insights" && <Insights />}
            {active === "knowledge" && <Knowledge />}
            {active === "settings" && <SettingsPanel />}
            {active === "run" && <RunPanel />}
          </motion.div>
        </AnimatePresence>
      </section>
    </main>
  );
}

function Header({ active }: { active: TabKey }) {
  const copy = {
    drafts: ["Review queue", "Approve, edit, or discard draft work before a send session touches X."],
    insights: ["Signal review", "See funnel health, edit rate, profile intelligence, and performance slices."],
    knowledge: ["Knowledge workbench", "Read and edit personas, style docs, playbooks, learnings, and writing guides."],
    settings: ["Operating controls", "Tune limits, metric goals, active persona, and tagging defaults."],
    run: ["Mode launcher", "Start a local agent mode in a focused terminal window."],
  }[active];
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">{copy[0]}</p>
        <h2>{copy[1]}</h2>
      </div>
      <div className="status-pill">
        <span className="pulse" />
        <span>Private data root</span>
      </div>
    </header>
  );
}

function Drafts() {
  const { data: drafts, loading, error, reload } = useLoad(api.drafts);
  const { data: incidents, reload: reloadIncidents } = useLoad(api.incidents);

  async function clearLockout() {
    await api.clearLockout();
    await reloadIncidents();
  }

  return (
    <div className="stack">
      {incidents?.locked_out && (
        <section className="callout danger">
          <ShieldAlert size={20} aria-hidden="true" />
          <div>
            <strong>Auto-lockout is active.</strong>
            <p>Review incidents, then clear the lockout when you have checked the browser state.</p>
          </div>
          <button className="button secondary" onClick={clearLockout}>Clear lockout</button>
        </section>
      )}
      <SectionToolbar title="Draft queue" count={drafts?.drafts.length} onRefresh={reload} />
      <State loading={loading} error={error} />
      {!loading && drafts?.drafts.length === 0 && <EmptyState title="No active drafts" detail="Run scroll or compose mode to generate a review queue." />}
      <div className="draft-grid">
        {drafts?.drafts.map((draft) => <DraftCard key={draft.id} draft={draft} onChange={reload} />)}
      </div>
    </div>
  );
}

function DraftCard({ draft, onChange }: { draft: DraftItem; onChange: () => Promise<void> }) {
  const [text, setText] = useState(draft.row.draft_text || "");
  const [busy, setBusy] = useState(false);
  const tags = [
    draft.type,
    draft.row.status && `status: ${draft.row.status}`,
    draft.stale_age ? "stale" : null,
    draft.row.reply_archetype,
    draft.row.content_type,
    draft.row.tagged_users ? `tags: ${draft.row.tagged_users}` : null,
  ].filter(Boolean);

  async function approve() {
    setBusy(true);
    await api.approveDraft(draft.id, text);
    await onChange();
    setBusy(false);
  }

  async function discard() {
    const reason = window.prompt("Discard reason");
    if (reason === null) return;
    setBusy(true);
    await api.discardDraft(draft.id, reason);
    await onChange();
    setBusy(false);
  }

  return (
    <article className="panel draft-card">
      <div className="card-head">
        <div>
          <p className="eyebrow">{draft.row.persona || "persona"}</p>
          <h3>{draft.id}</h3>
        </div>
        <span className="mono">{draft.row.drafted_at || "undated"}</span>
      </div>
      <div className="chip-row">
        {tags.map((tag) => <span className="chip" key={String(tag)}>{tag}</span>)}
      </div>
      {draft.row.target_tweet_url && (
        <a className="target-link" href={draft.row.target_tweet_url} target="_blank" rel="noreferrer">
          {draft.row.target_author_handle || "Open target"}
        </a>
      )}
      <label className="field-label" htmlFor={`draft-${draft.id}`}>Draft Text</label>
      <textarea id={`draft-${draft.id}`} value={text} onChange={(event) => setText(event.target.value)} />
      <div className="actions">
        <button className="button primary" onClick={approve} disabled={busy}>
          <Check size={16} aria-hidden="true" /> Approve
        </button>
        <button className="button ghost danger-text" onClick={discard} disabled={busy}>
          <Trash2 size={16} aria-hidden="true" /> Discard
        </button>
      </div>
    </article>
  );
}

function Insights() {
  const { data, loading, error, reload } = useLoad(api.insights);
  return (
    <div className="stack">
      <SectionToolbar title="Signal dashboard" count={data?.profiles.length} onRefresh={reload} />
      <State loading={loading} error={error} />
      {data && <InsightsBody data={data} />}
    </div>
  );
}

function InsightsBody({ data }: { data: InsightsResponse }) {
  return (
    <>
      <div className="metric-grid">
        <Metric label="Reply Drafts" value={data.funnel.replies.drafted} detail={`${data.funnel.replies.sent} sent`} />
        <Metric label="Original Drafts" value={data.funnel.tweets.drafted} detail={`${data.funnel.tweets.sent} sent`} />
        <Metric label="Edit Rate" value={data.edit_rate.rate === null ? "n/a" : `${(data.edit_rate.rate * 100).toFixed(1)}%`} detail={`${data.edit_rate.edited}/${data.edit_rate.sent} sent edited`} />
        <Metric label="Profiles" value={data.profiles.length} detail="studied accounts" />
      </div>
      <div className="two-col">
        <Funnel title="Replies" counts={data.funnel.replies} />
        <Funnel title="Original Posts" counts={data.funnel.tweets} />
      </div>
      <ProfileTable profiles={data.profiles} />
    </>
  );
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <div className="panel metric">
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </div>
  );
}

function Funnel({ title, counts }: { title: string; counts: FunnelCounts }) {
  const entries = Object.entries(counts);
  const max = Math.max(...entries.map(([, value]) => value), 1);
  return (
    <section className="panel">
      <h3>{title}</h3>
      <div className="bar-list">
        {entries.map(([key, value]) => (
          <div className="bar-row" key={key}>
            <span>{key}</span>
            <div><i style={{ width: `${(value / max) * 100}%` }} /></div>
            <b>{value}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function ProfileTable({ profiles }: { profiles: Record<string, string>[] }) {
  const rows = profiles.slice(0, 80);
  return (
    <section className="panel">
      <div className="card-head">
        <h3>Profile Intelligence</h3>
        <span className="mono">{profiles.length} rows</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Handle</th>
              <th>Category</th>
              <th>Tier</th>
              <th>Relevance</th>
              <th>Credibility</th>
              <th>Relationship</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((profile) => (
              <tr key={`${profile.handle}-${profile.last_updated}`}>
                <td>{profile.handle}</td>
                <td>{profile.category}</td>
                <td>{profile.follower_tier}</td>
                <td>{profile.relevance}</td>
                <td>{profile.credibility}</td>
                <td>{profile.relationship}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Knowledge() {
  const { data: files, loading, error, reload } = useLoad(api.files);
  const [selected, setSelected] = useState<string>("");
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const grouped = useMemo(() => {
    const groups: Record<string, string[]> = {};
    for (const file of files?.files ?? []) {
      const group = file.split("/").slice(0, 2).join("/");
      groups[group] = [...(groups[group] ?? []), file];
    }
    return groups;
  }, [files]);

  useEffect(() => {
    const first = files?.files[0];
    if (!selected && first) void openFile(first);
  }, [files]);

  async function openFile(path: string) {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    const file = await api.file(path);
    setSelected(path);
    setContent(file.content);
    setDirty(false);
  }

  async function save() {
    setSaving(true);
    await api.saveFile(selected, content);
    setDirty(false);
    setSaving(false);
    await reload();
  }

  return (
    <div className="knowledge-layout">
      <section className="panel file-list">
        <SectionToolbar title="Editable Files" count={files?.files.length} onRefresh={reload} />
        <State loading={loading} error={error} />
        {Object.entries(grouped).map(([group, paths]) => (
          <div key={group} className="file-group">
            <p className="eyebrow">{group}</p>
            {paths.map((path) => (
              <button key={path} className={selected === path ? "file-row active" : "file-row"} onClick={() => void openFile(path)}>
                <FilePenLine size={16} aria-hidden="true" />
                <span>{path.split("/").slice(-2).join("/")}</span>
              </button>
            ))}
          </div>
        ))}
      </section>
      <section className="panel editor-panel">
        <div className="card-head">
          <div>
            <p className="eyebrow">Markdown Editor</p>
            <h3>{selected || "Select a file"}</h3>
          </div>
          <button className="button primary" disabled={!selected || !dirty || saving} onClick={save}>
            <Save size={16} aria-hidden="true" /> {saving ? "Saving" : "Save Changes"}
          </button>
        </div>
        <textarea
          className="markdown-editor"
          value={content}
          onChange={(event) => {
            setContent(event.target.value);
            setDirty(true);
          }}
          spellCheck={false}
        />
      </section>
    </div>
  );
}

function SettingsPanel() {
  const { data: limits, reload: reloadLimits } = useLoad(api.limits);
  const { data: metrics, reload: reloadMetrics } = useLoad(api.metrics);
  const { data: persona, reload: reloadPersona } = useLoad(api.persona);
  return (
    <div className="settings-grid">
      {limits && <LimitsForm limits={limits} onSaved={reloadLimits} />}
      {metrics && <MetricsForm metrics={metrics} onSaved={reloadMetrics} />}
      {persona && <PersonaForm persona={persona} onSaved={reloadPersona} />}
    </div>
  );
}

function LimitsForm({ limits, onSaved }: { limits: Record<string, number>; onSaved: () => Promise<void> }) {
  const [values, setValues] = useState(limits);
  async function save() {
    await api.saveLimits(values);
    await onSaved();
  }
  return (
    <section className="panel">
      <h3>Limits</h3>
      <div className="form-grid">
        {Object.entries(values).map(([key, value]) => (
          <label key={key}>
            <span>{key}</span>
            <input type="number" name={key} value={value} onChange={(event) => setValues({ ...values, [key]: Number(event.target.value) })} />
          </label>
        ))}
      </div>
      <button className="button primary" onClick={save}><Save size={16} aria-hidden="true" /> Save Limits</button>
    </section>
  );
}

function MetricsForm({ metrics, onSaved }: { metrics: Record<string, string[]>; onSaved: () => Promise<void> }) {
  const [values, setValues] = useState(Object.fromEntries(Object.entries(metrics).map(([key, value]) => [key, value.join(", ")])));
  async function save() {
    const parsed = Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value.split(",").map((item) => item.trim()).filter(Boolean)]));
    await api.saveMetrics(parsed);
    await onSaved();
  }
  return (
    <section className="panel">
      <h3>Metrics</h3>
      <div className="form-grid single">
        {Object.entries(values).map(([key, value]) => (
          <label key={key}>
            <span>{key}</span>
            <input name={key} value={value} onChange={(event) => setValues({ ...values, [key]: event.target.value })} />
          </label>
        ))}
      </div>
      <button className="button primary" onClick={save}><Save size={16} aria-hidden="true" /> Save Metrics</button>
    </section>
  );
}

function PersonaForm({ persona, onSaved }: { persona: PersonaResponse; onSaved: () => Promise<void> }) {
  const [active, setActive] = useState(persona.active.persona || persona.available[0] || "");
  const [tagging, setTagging] = useState<"on" | "off">(persona.active.tagging || "off");
  async function save() {
    await api.savePersona(active, tagging);
    await onSaved();
  }
  return (
    <section className="panel">
      <h3>Active Persona</h3>
      <div className="form-grid single">
        <label>
          <span>Persona</span>
          <select value={active} onChange={(event) => setActive(event.target.value)}>
            {persona.available.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <label>
          <span>Tagging</span>
          <select value={tagging} onChange={(event) => setTagging(event.target.value as "on" | "off")}>
            <option value="off">off</option>
            <option value="on">on</option>
          </select>
        </label>
      </div>
      <button className="button primary" onClick={save}><Save size={16} aria-hidden="true" /> Save Persona</button>
    </section>
  );
}

function RunPanel() {
  const { data: persona } = useLoad(api.persona);
  const { data: runState, reload } = useLoad(api.runState);
  const [mode, setMode] = useState("learn");
  const [selectedPersona, setSelectedPersona] = useState("");
  const [tagging, setTagging] = useState(false);

  useEffect(() => {
    if (!selectedPersona && persona?.active.persona) setSelectedPersona(persona.active.persona);
  }, [persona]);

  async function launch() {
    await api.launch(mode, selectedPersona || undefined, tagging);
    await reload();
  }

  return (
    <section className="panel run-panel">
      <Gauge size={28} aria-hidden="true" />
      <h3>Launch a Mode</h3>
      <p>Starts a local agent session in a new PowerShell window. Keep one browser tab and one agent session active.</p>
      <div className="run-grid">
        <label>
          <span>Mode</span>
          <select value={mode} onChange={(event) => setMode(event.target.value)}>
            {["learn", "scroll", "compose", "send", "review"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          <span>Persona</span>
          <select value={selectedPersona} onChange={(event) => setSelectedPersona(event.target.value)}>
            {persona?.available.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <label className="switch">
          <input type="checkbox" checked={tagging} disabled={mode !== "scroll"} onChange={(event) => setTagging(event.target.checked)} />
          <span>Enable tagging for scroll mode</span>
        </label>
      </div>
      <button className="button primary big" onClick={launch}><Play size={18} aria-hidden="true" /> Launch Mode</button>
      <pre className="run-state">{JSON.stringify(runState?.last_launch ?? "No launch yet", null, 2)}</pre>
    </section>
  );
}

function SectionToolbar({ title, count, onRefresh }: { title: string; count?: number; onRefresh: () => void | Promise<void> }) {
  return (
    <div className="section-toolbar">
      <div>
        <h3>{title}</h3>
        {typeof count === "number" && <span className="mono">{count} records</span>}
      </div>
      <button className="icon-button" onClick={() => void onRefresh()} aria-label={`Refresh ${title}`}>
        <RefreshCw size={17} aria-hidden="true" />
      </button>
    </div>
  );
}

function State({ loading, error }: { loading: boolean; error: string | null }) {
  if (loading) return <p className="muted">Loading...</p>;
  if (error) return <p className="error"><X size={16} aria-hidden="true" /> {error}</p>;
  return null;
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <section className="panel empty">
      <h3>{title}</h3>
      <p>{detail}</p>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

