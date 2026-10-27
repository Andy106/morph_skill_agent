import { useEffect, useState } from "react";
import { api } from "./api.js";

const EMPTY_FORM = { name: "", description: "", values: [] };

export default function App() {
  const [enums, setEnums] = useState([]);
  const [selected, setSelected] = useState(null); // name of enum being edited, null = creating new
  const [form, setForm] = useState(EMPTY_FORM);
  const [newValue, setNewValue] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filter, setFilter] = useState("");

  const load = async () => {
    try {
      setEnums(await api.list());
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const flash = (msg) => {
    setNotice(msg);
    setTimeout(() => setNotice(""), 2500);
  };

  const startNew = () => {
    setSelected(null);
    setForm(EMPTY_FORM);
    setNewValue("");
    setError("");
  };

  const startEdit = (e) => {
    setSelected(e.name);
    setForm({ name: e.name, description: e.description ?? "", values: [...e.values] });
    setNewValue("");
    setError("");
  };

  const addValue = () => {
    const v = newValue.trim();
    if (!v) return;
    if (form.values.includes(v)) {
      setError(`'${v}' is already in the list`);
      return;
    }
    setForm({ ...form, values: [...form.values, v] });
    setNewValue("");
    setError("");
  };

  const removeValue = (v) => setForm({ ...form, values: form.values.filter((x) => x !== v) });

  const moveValue = (index, delta) => {
    const values = [...form.values];
    const target = index + delta;
    if (target < 0 || target >= values.length) return;
    [values[index], values[target]] = [values[target], values[index]];
    setForm({ ...form, values });
  };

  const save = async (ev) => {
    ev.preventDefault();
    setError("");
    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      values: form.values,
    };
    try {
      const saved = selected ? await api.update(selected, payload) : await api.create(payload);
      await load();
      startEdit(saved);
      flash(selected ? "Saved changes" : `Created '${saved.name}'`);
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (name) => {
    if (!window.confirm(`Delete enumeration '${name}'? This cannot be undone.`)) return;
    try {
      await api.remove(name);
      if (selected === name) startNew();
      await load();
      flash(`Deleted '${name}'`);
    } catch (e) {
      setError(e.message);
    }
  };

  const visible = enums.filter((e) => e.name.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="app">
      <header>
        <h1>Enumeration Manager</h1>
        <span className="muted">{enums.length} enumeration{enums.length === 1 ? "" : "s"}</span>
      </header>

      <main>
        <aside className="panel">
          <div className="row">
            <input placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} />
            <button onClick={startNew}>+ New</button>
          </div>
          {visible.length === 0 && <p className="muted">No enumerations yet.</p>}
          <ul className="enum-list">
            {visible.map((e) => (
              <li key={e.id} className={selected === e.name ? "active" : ""} onClick={() => startEdit(e)}>
                <div>
                  <strong>{e.name}</strong>
                  <div className="muted small">{e.values.join(", ")}</div>
                </div>
                <button
                  className="danger ghost"
                  title="Delete"
                  onClick={(ev) => {
                    ev.stopPropagation();
                    remove(e.name);
                  }}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="panel">
          <h2>{selected ? `Edit '${selected}'` : "New enumeration"}</h2>
          <form onSubmit={save}>
            <label>
              Name
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. environment"
                required
              />
              <span className="muted small">Letters, digits, '_' or '-'; must start with a letter.</span>
            </label>

            <label>
              Description
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Optional"
              />
            </label>

            <div className="field">
              <span>Allowed values</span>
              <div className="row">
                <input
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addValue();
                    }
                  }}
                  placeholder="Type a value and press Enter"
                />
                <button type="button" onClick={addValue}>
                  Add
                </button>
              </div>
              {form.values.length === 0 ? (
                <p className="muted small">Add at least one value.</p>
              ) : (
                <ol className="values">
                  {form.values.map((v, i) => (
                    <li key={v}>
                      <code>{v}</code>
                      <span className="actions">
                        <button type="button" className="ghost" onClick={() => moveValue(i, -1)} disabled={i === 0}>
                          ↑
                        </button>
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => moveValue(i, 1)}
                          disabled={i === form.values.length - 1}
                        >
                          ↓
                        </button>
                        <button type="button" className="ghost danger" onClick={() => removeValue(v)}>
                          ✕
                        </button>
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            {error && <div className="error">{error}</div>}
            {notice && <div className="notice">{notice}</div>}

            <div className="row end">
              {selected && (
                <button type="button" className="danger" onClick={() => remove(selected)}>
                  Delete
                </button>
              )}
              <button type="submit" className="primary" disabled={!form.name.trim() || form.values.length === 0}>
                {selected ? "Save changes" : "Create"}
              </button>
            </div>
          </form>

          {selected && <ValidateBox name={selected} />}
        </section>
      </main>
    </div>
  );
}

function ValidateBox({ name }) {
  const [value, setValue] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => setResult(null), [name]);

  const check = async (ev) => {
    ev.preventDefault();
    try {
      setResult(await api.validate(name, value));
    } catch (e) {
      setResult({ error: e.message });
    }
  };

  return (
    <form className="validate" onSubmit={check}>
      <h3>Test a value</h3>
      <div className="row">
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="e.g. prod" />
        <button type="submit">Check</button>
      </div>
      {result?.error && <div className="error">{result.error}</div>}
      {result && !result.error && (
        <div className={result.valid ? "notice" : "error"}>
          '{result.value}' is {result.valid ? "a valid" : "NOT a valid"} value for <code>{result.enumeration}</code>
        </div>
      )}
      <p className="muted small">
        API: <code>GET /api/enumerations/{name}/validate?value=…</code>
      </p>
    </form>
  );
}
