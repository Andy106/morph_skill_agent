const BASE = "/api/enumerations";

async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
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
  list: () => request(BASE),
  create: (data) => request(BASE, { method: "POST", body: JSON.stringify(data) }),
  update: (name, data) => request(`${BASE}/${enc(name)}`, { method: "PUT", body: JSON.stringify(data) }),
  remove: (name) => request(`${BASE}/${enc(name)}`, { method: "DELETE" }),
  validate: (name, value) => request(`${BASE}/${enc(name)}/validate?value=${enc(value)}`),
};
