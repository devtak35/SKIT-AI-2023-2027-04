import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const views = [{ id: "workspace", label: "Workspace", icon: "▦" }, { id: "memory", label: "Evidence search", icon: "⌕" }, { id: "intake", label: "Transcript intake", icon: "↗" }];

const time = (ms = 0) => {
  const value = Math.floor(ms / 1000);
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
};
const date = (value) => value ? new Date(value).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
const confidence = (value) => value == null ? "Not scored" : value >= .9 ? "High confidence" : value >= .75 ? "Reviewable" : "Needs review";
const Empty = ({ title, text, action }) => <div className="empty"><b>✦</b><strong>{title}</strong><p>{text}</p>{action}</div>;
const PanelTitle = ({ kicker, title, children }) => <div className="panel-title"><div><p className="eyebrow">{kicker}</p><h3>{title}</h3></div>{children}</div>;

export default function App() {
  const [health, setHealth] = useState("checking");
  const [view, setView] = useState("workspace");
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [segments, setSegments] = useState([]);
  const [summary, setSummary] = useState(null);
  const [records, setRecords] = useState([]);
  const [revisions, setRevisions] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [semantic, setSemantic] = useState("");
  const [matches, setMatches] = useState([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [intake, setIntake] = useState({ sessionId: "live-meeting", title: "Live meeting", speaker: "SPEAKER_01", text: "", start: "0", end: "1800", confidence: ".95", final: true, recordingFile: null });
  const [live, setLive] = useState(false);
  const recognition = useRef(null);
  const liveStartedAt = useRef(0);

  const api = useCallback(async (path, options = {}) => {
    const headers = { ...(options.headers || {}) };
    if (!(options.body instanceof FormData)) headers["Content-Type"] ||= "application/json";
    const response = await fetch(`${API}${path}`, { ...options, headers });
    const body = response.status === 204 ? null : await response.json();
    if (!response.ok) throw new Error(body?.error?.message || body?.detail || "The request could not be completed.");
    return body;
  }, []);
  const refresh = useCallback(async () => {
    try {
      const data = await api("/v1/sessions");
      setSessions(data);
      setSessionId((current) => current || data[0]?.session_id || "");
    } catch (e) { setError(e.message); }
  }, [api]);
  const load = useCallback(async () => {
    if (!sessionId) { setSegments([]); setSummary(null); setRecords([]); return; }
    try {
      const [transcript, nextSummary, graph] = await Promise.all([
        api(`/v1/sessions/${encodeURIComponent(sessionId)}/transcript-segments?include_revisions=${revisions}`),
        api(`/v1/sessions/${encodeURIComponent(sessionId)}/summaries/latest`),
        api(`/v1/sessions/${encodeURIComponent(sessionId)}/records`),
      ]);
      setSegments(transcript.segments || []); setSummary(nextSummary); setRecords(graph.records || []);
    } catch (e) { setError(e.message); }
  }, [api, revisions, sessionId]);
  useEffect(() => { api("/health").then(() => setHealth("online")).catch(() => setHealth("offline")); refresh(); }, [api, refresh]);
  useEffect(() => { if (view === "workspace") load(); }, [load, view]);
  useEffect(() => () => recognition.current?.stop(), []);

  const selected = sessions.find((item) => item.session_id === sessionId);
  const entities = useMemo(() => records.filter((record) => record.record_type === "entity").reduce((all, record) => {
    const kind = record.metadata?.entity_type || "topic";
    (all[kind] ||= []).push(record); return all;
  }, {}), [records]);
  const actions = records.filter((record) => record.record_type === "action_item");
  const scoredSegments = segments.filter((item) => item.asr_confidence != null);
  const avgConfidence = scoredSegments.length ? Math.round(scoredSegments.reduce((sum, item) => sum + item.asr_confidence, 0) / scoredSegments.length * 100) : null;

  async function ask(event) {
    event.preventDefault(); if (!question.trim()) return;
    setBusy(true); setError("");
    try { setAnswer(await api("/v1/query", { method: "POST", body: JSON.stringify({ question, session_ids: sessionId ? [sessionId] : [], top_k: 8 }) })); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function search(event) {
    event.preventDefault(); if (!semantic.trim()) return;
    try { const q = new URLSearchParams({ question: semantic, top_k: "8" }); if (sessionId) q.append("session_ids", sessionId); setMatches((await api(`/v1/semantic-search?${q}`)).matches || []); }
    catch (e) { setError(e.message); }
  }
  async function submitSegment(event) {
    event.preventDefault(); if (!intake.text.trim()) return;
    const id = Date.now(), now = new Date().toISOString();
    setBusy(true); setError("");
    try {
      await ensureSession();
      await api("/v1/transcript-segments", { method: "POST", body: JSON.stringify({ schema_version: "1.0", event_id: `manual-event-${id}`, session_id: intake.sessionId, created_at: now, payload: { segment_id: `manual-segment-${id}`, revision: 1, is_final: intake.final, start_ms: Number(intake.start), end_ms: Number(intake.end), speaker_id: intake.speaker, text: intake.text, asr_confidence: Number(intake.confidence) } }) });
      await refresh(); setSessionId(intake.sessionId); setIntake((item) => ({ ...item, text: "", start: item.end, end: String(Number(item.end) + 1800) })); setMessage("Transcript evidence accepted and indexed.");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function uploadRecording(event) {
    event.preventDefault();
    if (!intake.recordingFile) { setError("Choose an audio or video recording before uploading."); return; }
    setBusy(true); setError("");
    try {
      const body = new FormData();
      body.append("file", intake.recordingFile);
      body.append("title", intake.title.trim());
      const result = await api(`/v1/sessions/${encodeURIComponent(intake.sessionId)}/audio`, { method: "POST", body });
      await refresh(); setSessionId(intake.sessionId); setView("workspace");
      setMessage(`Transcribed and indexed ${result.segments_stored} recording segments with ${result.provider}.`);
      setIntake((item) => ({ ...item, recordingFile: null }));
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function renameSession(item, title) {
    try {
      await api(`/v1/sessions/${encodeURIComponent(item.session_id)}`, { method: "PATCH", body: JSON.stringify({ title }) });
      await refresh();
      setMessage("Meeting name updated.");
    } catch (e) { setError(e.message); throw e; }
  }
  async function removeSession(item) {
    if (!window.confirm(`Delete “${item.title || item.session_id}” and all of its transcript evidence? This cannot be undone.`)) return;
    try {
      await api(`/v1/sessions/${encodeURIComponent(item.session_id)}`, { method: "DELETE" });
      const remaining = sessions.filter((session) => session.session_id !== item.session_id);
      if (sessionId === item.session_id) {
        setSessionId(remaining[0]?.session_id || "");
        setSegments([]); setSummary(null); setRecords([]); setAnswer(null); setMatches([]);
      }
      await refresh();
      setMessage("Meeting and its stored evidence were deleted.");
    } catch (e) { setError(e.message); }
  }
  async function generateIntelligence() {
    if (!sessionId) return;
    setBusy(true); setError("");
    try {
      const result = await api(`/v1/sessions/${encodeURIComponent(sessionId)}/intelligence`, { method: "POST" });
      await load();
      setMessage(`AI intelligence updated: ${result.entities_created} records and ${result.action_items_created} action items extracted from your evidence.`);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function ensureSession() {
    const currentSessions = await api("/v1/sessions");
    setSessions(currentSessions);
    if (currentSessions.some((item) => item.session_id === intake.sessionId)) return;
    await api("/v1/sessions", { method: "POST", body: JSON.stringify({ session_id: intake.sessionId, title: intake.title.trim() || intake.sessionId }) });
    await refresh();
    setSessionId(intake.sessionId);
  }
  async function startLiveDictation() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { setError("Live dictation needs Chrome or another browser that supports the Web Speech API. You can still add transcript evidence manually."); return; }
    setBusy(true); setError("");
    try {
      await ensureSession();
      const listener = new SpeechRecognition();
      listener.continuous = true; listener.interimResults = false; listener.lang = "en-IN";
      listener.onresult = async (event) => {
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index];
          if (!result.isFinal) continue;
          const text = result[0].transcript.trim();
          if (!text) continue;
          const end = Date.now() - liveStartedAt.current;
          const start = Math.max(0, end - 4000);
          try {
            const asrConfidence = Number.isFinite(result[0].confidence) ? result[0].confidence : null;
            await api("/v1/transcript-segments", { method: "POST", body: JSON.stringify({ schema_version: "1.0", event_id: `speech-${Date.now()}-${index}`, session_id: intake.sessionId, created_at: new Date().toISOString(), payload: { segment_id: `speech-${Date.now()}-${index}`, revision: 1, is_final: true, start_ms: start, end_ms: end, speaker_id: intake.speaker, text, asr_confidence: asrConfidence } }) });
            await refresh(); setSessionId(intake.sessionId);
          } catch (e) { setError(e.message); }
        }
      };
      listener.onerror = (event) => { setError(`Live dictation stopped: ${event.error}.`); setLive(false); };
      listener.onend = () => setLive(false);
      recognition.current = listener; liveStartedAt.current = Date.now(); listener.start();
      setLive(true); setMessage("Live dictation is listening. Final speech results are being saved as transcript evidence.");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  function stopLiveDictation() { recognition.current?.stop(); setLive(false); setMessage("Live dictation stopped. Your captured transcript remains in the meeting workspace."); }
  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><b>V</b><span>VIDEO INTELLIGENCE<small>system</small></span></div>
      <nav>{views.map((item) => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}><i>{item.icon}</i>{item.label}</button>)}</nav>
      <div className="side-label">MEETING SESSIONS <button onClick={refresh}>↻</button></div>
      <div className="session-list">{sessions.length ? sessions.map((item) => <SessionNavItem key={item.session_id} item={item} selected={sessionId === item.session_id} onSelect={() => { setSessionId(item.session_id); setView("workspace"); }} onRename={renameSession} onDelete={removeSession} />) : <p>No meetings yet.<br />Start one or add transcript evidence.</p>}</div>
      <div className="api"><i className={health}></i> API {health}</div>
    </aside>
    <main>
      <header><div><p className="eyebrow">AI REALTIME VIDEO SUMMARY</p><h1>{view === "workspace" ? "Meeting workspace" : view === "memory" ? "Evidence memory" : "Transcript intake"}</h1></div><div className="head-actions"><span className={`connection ${health}`}>{health === "online" ? "● Connected" : "● Offline"}</span><button className="primary mini" onClick={() => setView("intake")}>+ New meeting</button></div></header>
      {message && <div className="notice">✓ {message}<button onClick={() => setMessage("")}>×</button></div>}
      {error && <div className="error">! {error}<button onClick={() => setError("")}>×</button></div>}
      {view === "workspace" && <Workspace {...{ sessionId, selected, segments, summary, entities, actions, revisions, setRevisions, avgConfidence, scoredSegmentCount: scoredSegments.length, question, setQuestion, ask, answer, busy, setView, generateIntelligence }} />}
      {view === "memory" && <Memory {...{ semantic, setSemantic, search, matches, question, setQuestion, ask, answer, busy, sessionId }} />}
      {view === "intake" && <Intake intake={intake} setIntake={(key, value) => setIntake((state) => ({ ...state, [key]: value }))} submit={submitSegment} uploadRecording={uploadRecording} busy={busy} segmentCount={segments.length} live={live} startLiveDictation={startLiveDictation} stopLiveDictation={stopLiveDictation} />}
    </main>
  </div>;
}

function SessionNavItem({ item, selected, onSelect, onRename, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(item.title || item.session_id);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (!editing) setTitle(item.title || item.session_id); }, [editing, item.title, item.session_id]);
  async function save(event) {
    event.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    try { await onRename(item, title.trim()); setEditing(false); }
    catch { /* the parent displays the API error and keeps the editor open */ }
    finally { setSaving(false); }
  }
  return <div className={`session-entry ${selected ? "selected" : ""}`}>
    {editing ? <form className="session-rename" onSubmit={save}><b>{item.session_id[0]?.toUpperCase()}</b><div><input aria-label="Meeting name" value={title} onChange={(event) => setTitle(event.target.value)} autoFocus maxLength={200} /><span><button type="submit" disabled={saving || !title.trim()}>{saving ? "Saving…" : "Save"}</button><button type="button" onClick={() => setEditing(false)}>Cancel</button></span></div></form> : <><button className="session-select" onClick={onSelect} aria-label={`Open ${item.title || item.session_id}`}><b>{item.session_id[0]?.toUpperCase()}</b><span><strong>{item.title || item.session_id}</strong><small>{item.segment_count} segments · {item.status}</small></span></button><div className="session-actions"><button type="button" aria-label={`Edit ${item.title || item.session_id}`} title="Edit meeting name" onClick={() => setEditing(true)}>✎</button><button type="button" aria-label={`Delete ${item.title || item.session_id}`} title="Delete meeting" onClick={() => onDelete(item)}>×</button></div></>}
  </div>;
}

function Workspace({ sessionId, selected, segments, summary, entities, actions, revisions, setRevisions, avgConfidence, scoredSegmentCount, question, setQuestion, ask, answer, busy, setView, generateIntelligence }) {
  if (!sessionId) return <Empty title="Start a real meeting" text="Create a named session, then capture live microphone speech or add your own verified transcript evidence." action={<p><button className="primary" onClick={() => setView("intake")}>Start a meeting</button></p>} />;
  const speakerCount = new Set(segments.map((item) => item.speaker_id)).size;
  return <><section className="hero"><div><small>MEETING / {sessionId}</small><h2>{selected?.title || "Untitled meeting"}</h2><p>Updated {date(selected?.updated_at)} · {selected?.status || "processing"}</p></div><div><label className="toggle"><input type="checkbox" checked={revisions} onChange={(event) => setRevisions(event.target.checked)} /><i></i>Revision history</label><span className="linked">● Evidence linked</span></div></section>
    <section className="metrics"><Metric label="Transcript segments" value={segments.length} detail={revisions ? "including revisions" : "latest revisions"} /><Metric label="Speakers" value={speakerCount || "—"} detail="diarization labels" /><Metric label="ASR confidence" value={avgConfidence == null ? "—" : `${avgConfidence}%`} detail={avgConfidence == null ? "not supplied by speech source" : `average of ${scoredSegmentCount} scored segments`} /><Metric label="Open actions" value={actions.filter((item) => item.status !== "completed").length} detail="extracted from meeting" /></section>
    <section className="workspace"><article className="panel transcript"><PanelTitle kicker="LIVE EVIDENCE" title="Transcript"><span className="pill">{segments.length}</span></PanelTitle>{segments.length ? <div className="timeline">{segments.map((item) => <div className="segment" key={`${item.segment_id}-${item.revision}`}><div className="stamp"><b>{time(item.start_ms)}</b><span>{time(item.end_ms)}</span></div><div className="rail"><i></i></div><div><div className="segment-tags"><b>{item.speaker_id}</b><em className={item.is_final ? "final" : "draft"}>{item.is_final ? "Final" : "Draft"}</em><small>r{item.revision}</small></div><p>{item.text}</p><div className="confidence"><span>ASR confidence</span><i><b style={{ width: `${Math.round((item.asr_confidence || 0) * 100)}%` }}></b></i><strong>{item.asr_confidence == null ? "—" : `${Math.round(item.asr_confidence * 100)}%`}</strong><small>{confidence(item.asr_confidence)}</small></div></div></div>)}</div> : <Empty title="No transcript evidence" text="Use Transcript intake to submit speaker-labelled segments." action={<button className="text" onClick={() => setView("intake")}>Open transcript intake →</button>} />}</article>
      <aside className="right-rail"><article className="panel summary"><PanelTitle kicker="ROLLING SUMMARY" title="Meeting pulse"><button className="text" onClick={generateIntelligence} disabled={busy}>{busy ? "Generating…" : "Generate with AI"}</button></PanelTitle>{summary ? <><p>{summary.text}</p><footer>◈ Evidence {summary.source_segment_ids.map((id) => <b key={id}>{id}</b>)}</footer></> : <Empty title="No summary yet" text="After adding final evidence, generate a cited summary and action items with Groq." action={<button className="primary" onClick={generateIntelligence} disabled={busy}>Generate intelligence</button>} />}</article><article className="panel quick-answer"><PanelTitle kicker="ASK THIS MEETING" title="Grounded answer" /><form onSubmit={ask}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about decisions, owners, or risks…" /><button className="primary" disabled={busy}>Ask</button></form>{answer ? <Answer answer={answer} /> : <p>Answers are grounded in stored transcript and graph evidence, with exact citations.</p>}</article></aside></section>
    <section className="intelligence"><div className="section-title"><div><p className="eyebrow">KNOWLEDGE GRAPH</p><h2>Meeting intelligence</h2></div><span>{recordsCount(entities, actions)} evidence-backed records</span></div><div className="cards"><RecordCard title="People" icon="◉" items={entities.person || []} /><RecordCard title="Topics" icon="◇" items={entities.topic || []} /><RecordCard title="Decisions" icon="✓" items={entities.decision || []} /><ActionCard items={actions} /></div></section></>;
}
const recordsCount = (entities, actions) => Object.values(entities).reduce((total, list) => total + list.length, 0) + actions.length;
function Metric({ label, value, detail }) { return <article><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>; }
function RecordCard({ title, icon, items }) { return <article className="record-card"><header><b>{icon}</b><h3>{title}</h3><span>{items.length}</span></header>{items.length ? items.map((item) => <div className="record" key={item.record_id}><strong>{item.text}</strong><small className={item.status}>{item.status.replace("_", " ")} · {Math.round(item.confidence * 100)}% confidence</small></div>) : <p>No {title.toLowerCase()} extracted yet.</p>}</article>; }
function ActionCard({ items }) { return <article className="record-card"><header><b>→</b><h3>Action items</h3><span>{items.length}</span></header>{items.length ? items.map((item) => <div className="record action" key={item.record_id}><strong><i></i>{item.text}</strong><small>{item.metadata?.owner_text || item.metadata?.owner_entity_id || "Owner unassigned"}{item.metadata?.due_date_text ? ` · Due ${item.metadata.due_date_text}` : ""}</small></div>) : <p>No action items extracted yet.</p>}</article>; }
function Answer({ answer, full = false }) { return <div className={`answer ${full ? "full" : ""}`}><small>{answer.insufficient_evidence ? "INSUFFICIENT EVIDENCE" : "EVIDENCE-GROUNDED ANSWER"}</small><p>{answer.answer}</p>{answer.citations?.map((item) => <div className="citation" key={`${item.session_id}-${item.segment_id}`}><b>◈</b><span><strong>{item.segment_id} · r{item.revision}</strong><small>{time(item.start_ms)}–{time(item.end_ms)} · {item.session_id}</small>{full && <em>“{item.quote}”</em>}</span></div>)}<footer>{answer.retrieval_metadata?.evidence_count || 0} cited evidence items · {answer.retrieval_metadata?.query_scope?.replace("_", " ")}</footer></div>; }

function Memory({ semantic, setSemantic, search, matches, question, setQuestion, ask, answer, busy, sessionId }) { return <section className="memory"><article className="panel search"><p className="eyebrow">SEMANTIC RETRIEVAL</p><h2>Find evidence, not just keywords</h2><p>Search the indexed transcript revisions for {sessionId || "all stored meetings"}.</p><form onSubmit={search}><input value={semantic} onChange={(event) => setSemantic(event.target.value)} placeholder="e.g. release checklist, migration risk…" /><button className="primary">Search evidence</button></form>{matches.length ? <div className="matches">{matches.map((item) => <div key={`${item.session_id}-${item.segment_id}`}><span>{Math.round(item.score * 100)}% match</span><strong>{item.segment_id}</strong><small>{item.session_id} · revision {item.revision}</small></div>)}</div> : <Empty title="Retrieval results appear here" text="The derived index preserves the session, segment, and revision of every match." />}</article><article className="panel question"><p className="eyebrow">CITED Q&A</p><h2>Ask across your evidence</h2><form onSubmit={ask}><textarea rows="4" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What did we decide about the release?" /><button className="primary" disabled={busy}>{busy ? "Retrieving…" : "Get cited answer"}</button></form>{answer ? <Answer answer={answer} full /> : <div className="hints"><span>Try asking</span><button onClick={() => setQuestion("What are the open action items?")}>What are the open action items?</button><button onClick={() => setQuestion("What did we decide about the timeline?")}>What did we decide about the timeline?</button><button onClick={() => setQuestion("Who owns the release checklist?")}>Who owns the release checklist?</button></div>}</article></section>; }
function Intake({ intake, setIntake, submit, uploadRecording, busy, segmentCount, live, startLiveDictation, stopLiveDictation }) {
  return <section className="intake"><article className="panel form-panel"><p className="eyebrow">ASR + DIARIZATION HANDOFF</p><h2>Capture meeting evidence</h2><p>Start a named meeting and dictate in Chrome, add a transcript segment, or upload an audio or video recording with Deepgram.</p><div className="live-capture"><label>Meeting title<input value={intake.title} onChange={(e) => setIntake("title", e.target.value)} required /></label><label>Session ID<input value={intake.sessionId} onChange={(e) => setIntake("sessionId", e.target.value)} required /></label><button type="button" className={live ? "stop-live" : "primary"} disabled={busy} onClick={live ? stopLiveDictation : startLiveDictation}>{live ? "■ Stop live dictation" : "● Start live dictation"}</button><small>Uses your browser microphone. Final speech results are saved immediately.</small></div><form className="audio-upload" onSubmit={uploadRecording}><label>Meeting recording (audio or video)<input type="file" accept="audio/*,video/mp4,video/webm,video/quicktime,.mp4,.mov,.webm" onChange={(e) => setIntake("recordingFile", e.target.files?.[0] || null)} /></label><small>Deepgram transcribes speech from the recording. Video frames are not analyzed. The temporary upload is removed after processing.</small><button className="primary" disabled={busy || !intake.recordingFile}>{busy ? "Transcribing recording…" : "Transcribe recording"}</button></form><form onSubmit={submit}><div><label>Speaker label<input value={intake.speaker} onChange={(e) => setIntake("speaker", e.target.value)} required /></label><label>ASR confidence<input type="number" min="0" max="1" step=".01" value={intake.confidence} onChange={(e) => setIntake("confidence", e.target.value)} required /></label></div><div><label>Start (ms)<input type="number" min="0" value={intake.start} onChange={(e) => setIntake("start", e.target.value)} required /></label><label>End (ms)<input type="number" min="0" value={intake.end} onChange={(e) => setIntake("end", e.target.value)} required /></label></div><label>Transcript text<textarea rows="5" value={intake.text} onChange={(e) => setIntake("text", e.target.value)} placeholder="What was said in the meeting?" required /></label><label className="check"><input type="checkbox" checked={intake.final} onChange={(e) => setIntake("final", e.target.checked)} /> This is a final ASR revision</label><button className="primary wide" disabled={busy}>{busy ? "Accepting evidence…" : "Submit transcript evidence"}</button></form></article><aside className="pipeline"><p className="eyebrow">PIPELINE STATUS</p><h2>Evidence journey</h2><ol>{[["Capture", "Browser microphone or audio/video recording"], ["ASR + diarization", "Provider transcript, timing, speaker, confidence"], ["Storage + embeddings", "Revision-aware, searchable evidence"], ["Summary + graph", "Evidence-linked claims and actions"], ["Grounded RAG", "Cited answers across meetings"]].map(([title, text], index) => <li className={index === 2 ? "current" : ""} key={title}><b>0{index + 1}</b><span><strong>{title}</strong><small>{text}</small></span></li>)}</ol><footer><strong>{segmentCount}</strong> segments currently loaded</footer></aside></section>;
}
