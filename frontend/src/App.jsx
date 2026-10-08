import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function App() {
  const [health, setHealth] = useState("checking");
  const [sessionId, setSessionId] = useState("");
  const [segments, setSegments] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/health`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Backend unavailable")))
      .then(() => setHealth("online"))
      .catch(() => setHealth("offline"));
  }, []);

  async function loadTranscript(event) {
    event.preventDefault();
    if (!sessionId.trim()) return;
    setError("");
    try {
      const response = await fetch(`${API}/v1/sessions/${encodeURIComponent(sessionId)}/transcript-segments`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error?.message || "Could not load transcript");
      setSegments(payload.segments);
    } catch (loadError) {
      setError(loadError.message);
      setSegments([]);
    }
  }

  return <main className="shell">
    <header><div><p className="eyebrow">AI REALTIME VIDEO SUMMARY</p><h1>Meeting workspace</h1></div><span className={`status ${health}`}>{health}</span></header>
    <section className="card"><h2>Load a transcript session</h2><form onSubmit={loadTranscript}><input value={sessionId} onChange={(event) => setSessionId(event.target.value)} placeholder="session ID" /><button>Load transcript</button></form>{error && <p className="error">{error}</p>}</section>
    <section className="card"><div className="section-heading"><h2>Transcript</h2><span>{segments.length} segments</span></div>{segments.length === 0 ? <p className="muted">No transcript loaded yet.</p> : <div className="segments">{segments.map((segment) => <article key={`${segment.segment_id}-${segment.revision}`}><span className="speaker">{segment.speaker_id}</span><p>{segment.text}</p><small>{segment.start_ms}–{segment.end_ms} ms · revision {segment.revision}</small></article>)}</div>}</section>
  </main>;
}
