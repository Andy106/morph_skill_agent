import { useState } from "react";
import Chips from "./Chips.jsx";

const SECTIONS = [
  { status: "same", title: "Same", action: "No change needed" },
  { status: "similar", title: "Similar", action: "Change the JSON Schema to match the enumeration" },
  { status: "different", title: "Different", action: "Add a new enumeration to the app" },
];

function pretty(text) {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function download(markdown) {
  const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "output.md";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Results({ result }) {
  const [filter, setFilter] = useState("all");
  const counts = Object.fromEntries(SECTIONS.map((s) => [s.status, result.findings.filter((f) => f.status === s.status).length]));
  const shown = SECTIONS.filter((s) => filter === "all" || filter === s.status);

  return (
    <div className="panel">
      <div className="row between wrap">
        <div>
          <h2>Results</h2>
          <p className="muted small">
            {new Date(result.completed_at).toLocaleString()} · {result.model} · {result.duration_seconds}s
          </p>
          {result.output_path && <p className="muted small break">Saved to {result.output_path}</p>}
          {result.output_error && <p className="small break warning">{result.output_error}</p>}
        </div>
        <button className="primary" onClick={() => download(result.markdown)}>
          Download output.md
        </button>
      </div>

      <p>{result.summary}</p>

      <div className="tiles">
        <button className={`tile ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")}>
          <span className="tile-count">{result.findings.length}</span>
          <span>All</span>
        </button>
        {SECTIONS.map((s) => (
          <button key={s.status} className={`tile ${s.status} ${filter === s.status ? "active" : ""}`} onClick={() => setFilter(s.status)}>
            <span className="tile-count">{counts[s.status]}</span>
            <span>{s.title}</span>
          </button>
        ))}
      </div>

      {result.missing_pointers.length > 0 && (
        <div className="warning">
          The agent did not report on: {result.missing_pointers.map((p) => <code key={p}>{p}</code>)}. Try running it again.
        </div>
      )}

      {shown.map((s) => (
        <section key={s.status}>
          <h3>
            <span className={`badge ${s.status}`}>{s.title}</span> {s.action}
          </h3>
          {counts[s.status] === 0 && <p className="muted">None.</p>}
          {result.findings
            .filter((f) => f.status === s.status)
            .map((f) => (
              <Finding key={f.schema_pointer} finding={f} />
            ))}
        </section>
      ))}
    </div>
  );
}

function Finding({ finding: f }) {
  return (
    <article className={`finding ${f.status}`}>
      <div className="row between wrap">
        <div>
          <strong>
            <code>{f.attribute}</code>
          </strong>
          {f.matched_enumeration && (
            <span className="muted">
              {" "}
              → enumeration <code>{f.matched_enumeration}</code>
            </span>
          )}
        </div>
        <span className="muted small break">{f.schema_pointer}</span>
      </div>
      <div className="small">
        Schema values: <Chips values={f.schema_values} />
      </div>
      {f.value_mapping?.length > 0 && (
        <div className="small">
          Value changes:{" "}
          {f.value_mapping.map((m) => (
            <span key={m.schema_value} className="mapping">
              <code>{m.schema_value}</code> → {m.enumeration_value ? <code>{m.enumeration_value}</code> : <em>dropped</em>}
            </span>
          ))}
        </div>
      )}
      <p>{f.explanation}</p>

      {f.proposed_schema_fragment && (
        <CodeBlock label={`Replace ${f.schema_pointer} with:`} text={pretty(f.proposed_schema_fragment)} />
      )}

      {f.value_conflicts?.length > 0 && (
        <div className="decide">
          <strong>Decide:</strong> with the new values, these defaults/examples in the schema would become invalid.
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Location</th>
                  <th>Value</th>
                  <th>Options</th>
                </tr>
              </thead>
              <tbody>
                {f.value_conflicts.map((c) => (
                  <tr key={c.location}>
                    <td className="break">
                      <code>{c.location}</code>
                    </td>
                    <td>
                      <code>{c.value}</code>
                    </td>
                    <td>
                      <ul className="options">
                        {c.suggested_value && (
                          <li>
                            Change it to <code>{c.suggested_value}</code>
                          </li>
                        )}
                        <li>Remove it</li>
                        <li>
                          Keep it and add <code>{c.value}</code> to the <code>{f.matched_enumeration}</code> enumeration
                        </li>
                      </ul>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {f.proposed_enumeration && (
        <>
          <div className="small">
            Proposed enumeration <code>{f.proposed_enumeration.name}</code>: {f.proposed_enumeration.description}
          </div>
          <CodeBlock
            label="To create it: POST /api/enumerations"
            text={JSON.stringify(
              {
                name: f.proposed_enumeration.name,
                description: f.proposed_enumeration.description,
                values: f.proposed_enumeration.values,
              },
              null,
              2
            )}
          />
        </>
      )}
    </article>
  );
}

function CodeBlock({ label, text }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable; the text is still selectable */
    }
  };
  return (
    <div className="codeblock">
      <div className="row between">
        <span className="muted small break">{label}</span>
        <button className="ghost small" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="code">{text}</pre>
    </div>
  );
}
