async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(formatError(body) || `Request failed (${res.status})`);
  }
  return body;
}

// FastAPI returns either a string detail or a list of validation errors.
function formatError(body) {
  if (!body?.detail) return null;
  if (typeof body.detail === "string") return body.detail;
  return body.detail.map((d) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ");
}

const enc = encodeURIComponent;

export const api = {
  status: () => request("/api/status"),
  listSchemas: () => request("/api/schemas"),
  getSchema: (name) => request(`/api/schemas/${enc(name)}`),
  uploadSchema: (name, content) => request("/api/schemas", { method: "POST", body: JSON.stringify({ name, content }) }),
  analyze: (schemaName) => request("/api/analyses", { method: "POST", body: JSON.stringify({ schema_name: schemaName }) }),
};
