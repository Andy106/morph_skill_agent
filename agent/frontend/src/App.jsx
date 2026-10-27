import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import Chips from "./Chips.jsx";
import Results from "./Results.jsx";

export default function App() {
  const [status, setStatus] = useState(null);
  const [schemas, setSchemas] = useState([]);
  const [selected, setSelected] = useState(null); // schema name
  const [detail, setDetail] = useState(null); // full schema incl. content and enum attributes
  const [showJson, setShowJson] = useState(false);
  const [results, setResults] = useState({}); // schema name -> analysis result, kept while the page is open
  const [running, setRunning] = useState(null); // schema name being analysed
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const fileInput = useRef(null);

  const loadStatus = () => api.status().then(setStatus).catch((e) => setError(e.message));
  const loadSchemas = () => api.listSchemas().then(setSchemas).catch((e) => setError(e.message));

  useEffect(() => {
    loadStatus();
    loadSchemas();
  }, []);

  useEffect(() => {
    setDetail(null);
    setShowJson(false);
    if (!selected) return;
    api.getSchema(selected).then(setDetail).catch((e) => setError(e.message));
  }, [selected]);

  useEffect(() => {
    if (!running) return;
    setElapsed(0);
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [running]);

  const run = async () => {
    setError("");
    setRunning(selected);
    try {
      const result = await api.analyze(selected);
      setResults((r) => ({ ...r, [selected]: result }));
    } catch (e) {
      setError(e.message);
      loadStatus();
    } finally {
      setRunning(null);
    }
  };

  const upload = async (ev) => {
    const file = ev.target.files?.[0];
    ev.target.value = "";
    if (!file) return;
    setError("");
    try {
      const saved = await api.uploadSchema(file.name, await file.text());
      await loadSchemas();
      setSelected(saved.name);
    } catch (e) {
      setError(e.message);
    }
  };

  const ready = status?.openai_key_set && status?.enum_api_reachable;
  const current = schemas.find((s) => s.name === selected);
  const result = selected ? results[selected] : null;
  const canRun = ready && current && !current.error && current.enum_attribute_count > 0 && !running;

  return (
    <div className="app">
      <header>
        <div>
          <h1>Schema Review Agent</h1>
          <p className="muted">Compare a JSON Schema's enumerations with the Enumeration Manager.</p>
        </div>
        <StatusBar status={status} onRefresh={loadStatus} />
      </header>

      {status && !status.openai_key_set && (
        <div className="error">OPENAI_API_KEY is not set. Add it to agent/.env and restart the agent API.</div>
      )}
      {status && !status.enum_api_reachable && <div className="error">{status.enum_api_error}</div>}

      <main>
        <aside className="panel">
          <div className="row between">
            <h2>Schemas</h2>
            <button onClick={() => fileInput.current?.click()} title="Add a schema file to the schemas folder">
              Upload…
            </button>
            <input ref={fileInput} type="file" accept=".json,application/json" hidden onChange={upload} />
          </div>
          {status && <p className="muted small break">{status.schemas_dir}</p>}
          {schemas.length === 0 && <p className="muted">No .json files in the schemas folder.</p>}
          <ul className="schema-list">
            {schemas.map((s) => (
              <li key={s.name}>
                <button className={`schema-item ${selected === s.name ? "active" : ""}`} onClick={() => setSelected(s.name)}>
                  <strong className="break">{s.name}</strong>
                  <span className="muted small">
                    {s.error
                      ? "Invalid JSON"
                      : `${s.title ?? "Untitled"} · ${s.enum_attribute_count} enum attribute${s.enum_attribute_count === 1 ? "" : "s"}`}
                  </span>
                  {results[s.name] && <span className="tag">analysed</span>}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="content">
          {error && <div className="error">{error}</div>}

          {!selected && (
            <div className="panel empty">
              <p>Select a schema on the left, then run the analysis.</p>
            </div>
          )}

          {selected && current && (
            <div className="panel">
              <div className="row between wrap">
                <div>
                  <h2 className="break">{current.name}</h2>
                  {current.description && <p className="muted">{current.description}</p>}
                </div>
                <button className="primary" onClick={run} disabled={!canRun}>
                  {running === selected ? `Analysing… ${elapsed}s` : result ? "Run again" : "Run analysis"}
                </button>
              </div>

              {current.error && <div className="error">{current.error}</div>}
              {!current.error && current.enum_attribute_count === 0 && (
                <p className="muted">This schema has no enum or const attributes, so there is nothing to compare.</p>
              )}
              {running === selected && (
                <p className="muted small">
                  The agent is reading the schema, fetching your enumerations and comparing them. This usually takes under a minute.
                </p>
              )}

              {detail?.enum_attributes?.length > 0 && (
                <>
                  <h3>Attributes to compare</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Attribute</th>
                          <th>Pointer</th>
                          <th>Values</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.enum_attributes.map((a) => (
                          <tr key={a.pointer}>
                            <td>
                              <code>{a.attribute}</code>
                              {a.kind === "const" && <span className="tag">const</span>}
                            </td>
                            <td className="muted small break">{a.pointer}</td>
                            <td>
                              <Chips values={a.values} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              {detail && (
                <button className="link" onClick={() => setShowJson(!showJson)}>
                  {showJson ? "Hide schema JSON" : "Show schema JSON"}
                </button>
              )}
              {showJson && <pre className="code">{detail.content}</pre>}
            </div>
          )}

          {result && <Results result={result} />}
        </section>
      </main>
    </div>
  );
}

function StatusBar({ status, onRefresh }) {
  if (!status) return <span className="muted small">Connecting to the agent API…</span>;
  return (
    <div className="status">
      <span className={`pill ${status.openai_key_set ? "ok" : "bad"}`}>OpenAI key {status.openai_key_set ? "set" : "missing"}</span>
      <span className="pill">Model: {status.model}</span>
      <span className={`pill ${status.enum_api_reachable ? "ok" : "bad"}`} title={status.enum_api_url}>
        Enumeration Manager {status.enum_api_reachable ? "connected" : "unreachable"}
      </span>
      <button className="ghost small" onClick={onRefresh} title="Check again">
        ↻
      </button>
    </div>
  );
}
