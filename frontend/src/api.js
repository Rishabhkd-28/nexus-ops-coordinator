const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function req(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  start:           (transcript, rules) => req("POST", "/run/start", { transcript, rules }),
  status:          (id)                => req("GET",  `/run/${id}/status`),
  intake:          (id)                => req("POST", `/run/${id}/intake`),
  planning:        (id)                => req("POST", `/run/${id}/planning`),
  review:          (id)                => req("POST", `/run/${id}/review`),
  editFact:        (id, description)   => req("POST", `/run/${id}/edit-fact`, { description }),
  simulateFailure: (id, agent)         => req("POST", `/run/${id}/simulate-failure`, { agent }),
  clearFailure:    (id)                => req("POST", `/run/${id}/clear-failure`),
  reset:           (id)                => req("POST", `/run/${id}/reset`),
};
