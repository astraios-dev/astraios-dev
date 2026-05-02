const BASE = "/api";

export async function apiFetch(path, opts = {}) {
  const token = localStorage.getItem("astraios_token");
  const headers = { "Content-Type": "application/json", ...opts.headers };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });

  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const msg = data?.detail || `Request failed (${res.status})`;
    throw new Error(msg);
  }

  return data;
}

export const api = {
  register: (body) => apiFetch("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body) => apiFetch("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => apiFetch("/auth/me"),

  listSignals: () => apiFetch("/signals"),
  createSignal: (body) => apiFetch("/signals", { method: "POST", body: JSON.stringify(body) }),
  deleteSignal: (id) => apiFetch(`/signals/${id}`, { method: "DELETE" }),

  listPositions: () => apiFetch("/portfolio"),
  createPosition: (body) => apiFetch("/portfolio", { method: "POST", body: JSON.stringify(body) }),
  updatePosition: (id, body) => apiFetch(`/portfolio/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deletePosition: (id) => apiFetch(`/portfolio/${id}`, { method: "DELETE" }),

  accountStats: () => apiFetch("/account/stats"),

  marketPrices: () => apiFetch("/market/prices"),
  marketRefresh: () => apiFetch("/market/refresh", { method: "POST" }),

  tradePositions: (symbol) => apiFetch(`/trade/positions${symbol ? `?symbol=${symbol}` : ""}`),
  tradeOrders: (symbol) => apiFetch(`/trade/orders${symbol ? `?symbol=${symbol}` : ""}`),
  tradeWallet: () => apiFetch("/trade/wallet"),
  tradeOrder: (body) => apiFetch("/trade/order", { method: "POST", body: JSON.stringify(body) }),
  tradeClose: (body) => apiFetch("/trade/close", { method: "POST", body: JSON.stringify(body) }),
  tradeLeverage: (body) => apiFetch("/trade/leverage", { method: "POST", body: JSON.stringify(body) }),
};
