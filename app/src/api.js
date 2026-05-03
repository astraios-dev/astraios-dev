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
  modelInfo: () => apiFetch("/account/model-info"),
  saveApiKeys: (body) => apiFetch("/account/api-keys", { method: "POST", body: JSON.stringify(body) }),
  removeApiKeys: () => apiFetch("/account/api-keys", { method: "DELETE" }),
  saveTestnetKeys: (body) => apiFetch("/account/testnet-keys", { method: "POST", body: JSON.stringify(body) }),
  removeTestnetKeys: () => apiFetch("/account/testnet-keys", { method: "DELETE" }),

  marketPrices: () => apiFetch("/market/prices"),
  marketRefresh: () => apiFetch("/market/refresh", { method: "POST" }),

  tradeSymbols: () => apiFetch("/trade/symbols"),
  tradeKlines: (symbol, interval = "60", limit = 1000) =>
    apiFetch(`/trade/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`),
  tradePositions: (symbol, testnet = false) => apiFetch(`/trade/positions?testnet=${testnet}${symbol ? `&symbol=${symbol}` : ""}`),
  tradeOrders: (symbol, testnet = false) => apiFetch(`/trade/orders?testnet=${testnet}${symbol ? `&symbol=${symbol}` : ""}`),
  tradeWallet: (testnet = false) => apiFetch(`/trade/wallet?testnet=${testnet}`),
  tradeOrder: (body) => apiFetch("/trade/order", { method: "POST", body: JSON.stringify(body) }),
  tradeClose: (body) => apiFetch("/trade/close", { method: "POST", body: JSON.stringify(body) }),
  tradeLeverage: (body) => apiFetch("/trade/leverage", { method: "POST", body: JSON.stringify(body) }),
};
