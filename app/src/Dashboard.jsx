import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";
import { api } from "./api.js";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [signals, setSignals] = useState([]);
  const [positions, setPositions] = useState([]);
  const [stats, setStats] = useState(null);
  const [prices, setPrices] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Bybit state
  const [bybitPositions, setBybitPositions] = useState([]);
  const [wallet, setWallet] = useState(null);
  const [bybitError, setBybitError] = useState(null);
  const [orderForm, setOrderForm] = useState({ symbol: "BTCUSDT", side: "Buy", qty: "", tp: "", sl: "" });
  const [orderStatus, setOrderStatus] = useState(null);
  const [ordering, setOrdering] = useState(false);
  const [closing, setClosing] = useState(null);

  const loadData = useCallback(() => {
    return Promise.all([
      api.listSignals(),
      api.listPositions(),
      api.accountStats(),
      api.marketPrices().catch(() => ({ tickers: {} })),
    ]).then(([s, p, st, m]) => {
      setSignals(s);
      setPositions(p);
      setStats(st);
      setPrices(m.tickers || {});
      setLastUpdated(new Date());
    });
  }, []);

  const loadBybit = useCallback(() => {
    setBybitError(null);
    return Promise.all([
      api.tradePositions(),
      api.tradeWallet(),
    ]).then(([bp, w]) => {
      setBybitPositions(bp);
      setWallet(w);
    }).catch((e) => {
      setBybitError(e.message);
    });
  }, []);

  useEffect(() => {
    Promise.all([loadData(), loadBybit()])
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [loadData, loadBybit]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.marketRefresh();
      await Promise.all([loadData(), loadBybit()]);
    } catch {}
    setRefreshing(false);
  };

  const handleOrder = async (e) => {
    e.preventDefault();
    if (!orderForm.qty) return;
    setOrdering(true);
    setOrderStatus(null);
    try {
      const result = await api.tradeOrder({
        symbol: orderForm.symbol.toUpperCase(),
        side: orderForm.side,
        qty: orderForm.qty,
        tp: orderForm.tp || undefined,
        sl: orderForm.sl || undefined,
      });
      setOrderStatus({ ok: true, msg: `Order placed: ${result.order_id}` });
      setOrderForm((f) => ({ ...f, qty: "", tp: "", sl: "" }));
      await loadBybit();
    } catch (err) {
      setOrderStatus({ ok: false, msg: err.message });
    }
    setOrdering(false);
  };

  const handleClose = async (pos) => {
    setClosing(pos.symbol);
    try {
      await api.tradeClose({ symbol: pos.symbol, side: pos.side, qty: String(pos.size) });
      await loadBybit();
    } catch (err) {
      setOrderStatus({ ok: false, msg: `Close failed: ${err.message}` });
    }
    setClosing(null);
  };

  const portfolioStats = stats
    ? [
        { label: "Portfolio value", value: `$${stats.portfolio_value.toLocaleString()}` },
        { label: "Total P&L", value: `${stats.total_pnl >= 0 ? "+" : ""}$${stats.total_pnl.toLocaleString()}`, positive: stats.total_pnl >= 0 },
        { label: "Open positions", value: String(stats.open_positions) },
        { label: "Total signals", value: String(stats.total_signals) },
      ]
    : [];

  const walletStats = wallet
    ? [
        { label: "Equity", value: `$${fmtNum(wallet.equity)}` },
        { label: "Available", value: `$${fmtNum(wallet.available_balance)}` },
        { label: "Unrealised P&L", value: `$${fmtNum(wallet.unrealised_pnl)}`, positive: parseFloat(wallet.unrealised_pnl) >= 0 },
        { label: "Margin used", value: `$${fmtNum(wallet.margin_used)}` },
      ]
    : [];

  const priceTickers = Object.entries(prices);

  return (
    <div className="dash">
      <header className="dash-header">
        <Link to="/" className="dash-brand" aria-label="Astraios home">
          <span className="logo-mark logo-mark--small" role="img" aria-label="Astraios A mark" />
          <span className="brand-divider" aria-hidden="true" />
          <span className="wordmark" role="img" aria-label="Astraios wordmark" />
        </Link>

        <div className="dash-header__right">
          <span className="dash-user">{user?.name}</span>
          <span className="status-pill" role="status">
            <span className="status-pill__dot status-pill__dot--live" aria-hidden="true" />
            <span className="status-pill__text">Live trading</span>
          </span>
          <button type="button" className="dash-logout" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      <main className="dash-main">
        <div className="dash-welcome">
          <div>
            <p className="eyebrow">Dashboard</p>
            <h1>Good {getGreeting()}, {user?.name?.split(" ")[0]}.</h1>
          </div>
          <div className="dash-welcome__actions">
            <button
              type="button"
              className="refresh-btn"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              {refreshing ? "Refreshing…" : "Refresh data"}
            </button>
            {lastUpdated && (
              <span className="last-updated">
                Updated {lastUpdated.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
              </span>
            )}
          </div>
        </div>

        {loading ? (
          <div className="dash-loading">Loading…</div>
        ) : (
          <>
            {priceTickers.length > 0 && (
              <section className="market-strip" aria-label="Market prices">
                {priceTickers.map(([ticker, data]) => (
                  <div className="market-chip" key={ticker}>
                    <span className="market-chip__ticker">{ticker}</span>
                    <span className="market-chip__price">${data.price.toLocaleString()}</span>
                    <span className={`market-chip__change ${data.change_pct >= 0 ? "market-chip__change--up" : "market-chip__change--down"}`}>
                      {data.change_pct >= 0 ? "+" : ""}{data.change_pct}%
                    </span>
                  </div>
                ))}
              </section>
            )}

            {/* Bybit wallet */}
            {wallet && (
              <section className="dash-stats" aria-label="Bybit wallet">
                {walletStats.map((stat) => (
                  <div className="stat-card" key={stat.label}>
                    <dt>{stat.label}</dt>
                    <dd className={stat.positive === false ? "stat-negative" : stat.positive ? "stat-positive" : ""}>
                      {stat.value}
                    </dd>
                  </div>
                ))}
              </section>
            )}
            {bybitError && (
              <div className="bybit-error">Bybit: {bybitError}</div>
            )}

            {/* Trade form + Bybit positions */}
            <div className="dash-grid">
              <section className="dash-trade" aria-labelledby="trade-title">
                <div className="dash-section-head">
                  <h2 id="trade-title">Trade</h2>
                  <span className="dash-section-badge">USDT Perps</span>
                </div>

                <form className="trade-form" onSubmit={handleOrder}>
                  <div className="trade-form__row">
                    <input
                      type="text"
                      placeholder="Symbol"
                      value={orderForm.symbol}
                      onChange={(e) => setOrderForm((f) => ({ ...f, symbol: e.target.value }))}
                      className="trade-input"
                    />
                    <select
                      value={orderForm.side}
                      onChange={(e) => setOrderForm((f) => ({ ...f, side: e.target.value }))}
                      className="trade-select"
                    >
                      <option value="Buy">Long</option>
                      <option value="Sell">Short</option>
                    </select>
                    <input
                      type="text"
                      placeholder="Qty"
                      value={orderForm.qty}
                      onChange={(e) => setOrderForm((f) => ({ ...f, qty: e.target.value }))}
                      className="trade-input trade-input--qty"
                    />
                  </div>
                  <div className="trade-form__row">
                    <input
                      type="text"
                      placeholder="TP price (optional)"
                      value={orderForm.tp}
                      onChange={(e) => setOrderForm((f) => ({ ...f, tp: e.target.value }))}
                      className="trade-input"
                    />
                    <input
                      type="text"
                      placeholder="SL price (optional)"
                      value={orderForm.sl}
                      onChange={(e) => setOrderForm((f) => ({ ...f, sl: e.target.value }))}
                      className="trade-input"
                    />
                    <button
                      type="submit"
                      className={`trade-submit ${orderForm.side === "Buy" ? "trade-submit--buy" : "trade-submit--sell"}`}
                      disabled={ordering || !orderForm.qty}
                    >
                      {ordering ? "Placing…" : orderForm.side === "Buy" ? "Long" : "Short"}
                    </button>
                  </div>
                  {orderStatus && (
                    <p className={`trade-status ${orderStatus.ok ? "trade-status--ok" : "trade-status--err"}`}>
                      {orderStatus.msg}
                    </p>
                  )}
                </form>
              </section>

              <section className="dash-bybit-positions" aria-labelledby="bybit-positions-title">
                <div className="dash-section-head">
                  <h2 id="bybit-positions-title">Bybit positions</h2>
                  <span className="dash-section-badge">{bybitPositions.length} open</span>
                </div>

                {bybitPositions.length === 0 ? (
                  <p className="dash-empty">No open derivatives positions.</p>
                ) : (
                  <div className="positions-table-wrap">
                    <table className="positions-table bybit-table">
                      <thead>
                        <tr>
                          <th>Symbol</th>
                          <th>Side</th>
                          <th>Size</th>
                          <th>Entry</th>
                          <th>Mark</th>
                          <th>Unrl. P&L</th>
                          <th>Lev</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {bybitPositions.map((p) => (
                          <tr key={p.symbol + p.side}>
                            <td className="signal-ticker">{p.symbol}</td>
                            <td>
                              <span className={`signal-action signal-action--${p.side === "Buy" ? "buy" : "sell"}`}>
                                {p.side === "Buy" ? "LONG" : "SHORT"}
                              </span>
                            </td>
                            <td>{p.size}</td>
                            <td>${Number(p.entry_price).toLocaleString()}</td>
                            <td>${Number(p.mark_price).toLocaleString()}</td>
                            <td className={p.unrealised_pnl >= 0 ? "pnl-positive" : "pnl-negative"}>
                              {p.unrealised_pnl >= 0 ? "+" : ""}${p.unrealised_pnl.toLocaleString()}
                            </td>
                            <td>{p.leverage}x</td>
                            <td>
                              <button
                                type="button"
                                className="close-pos-btn"
                                onClick={() => handleClose(p)}
                                disabled={closing === p.symbol}
                              >
                                {closing === p.symbol ? "…" : "Close"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </div>

            {/* Signal + paper positions below */}
            <div className="dash-grid">
              <section className="dash-signals" aria-labelledby="signals-title">
                <div className="dash-section-head">
                  <h2 id="signals-title">Latest signals</h2>
                  <span className="dash-section-badge">{signals.length} active</span>
                </div>

                {signals.length === 0 ? (
                  <p className="dash-empty">No signals yet. They will appear here as the model generates them.</p>
                ) : (
                  <div className="signals-table-wrap">
                    <table className="signals-table">
                      <thead>
                        <tr>
                          <th>Ticker</th>
                          <th>Action</th>
                          <th>Confidence</th>
                          <th>Rationale</th>
                          <th>Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {signals.map((s) => (
                          <tr key={s.id}>
                            <td className="signal-ticker">{s.ticker}</td>
                            <td>
                              <span className={`signal-action signal-action--${s.action.toLowerCase()}`}>
                                {s.action}
                              </span>
                            </td>
                            <td>
                              <span className="signal-confidence">
                                <span className="signal-confidence__bar" style={{ width: `${s.confidence * 100}%` }} />
                                <span className="signal-confidence__label">{(s.confidence * 100).toFixed(0)}%</span>
                              </span>
                            </td>
                            <td className="signal-rationale">{s.rationale}</td>
                            <td className="signal-time">{formatTime(s.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className="dash-positions" aria-labelledby="positions-title">
                <div className="dash-section-head">
                  <h2 id="positions-title">Paper positions</h2>
                  <span className="dash-section-badge">{positions.length} held</span>
                </div>

                {positions.length === 0 ? (
                  <p className="dash-empty">No open positions.</p>
                ) : (
                  <div className="positions-table-wrap">
                    <table className="positions-table">
                      <thead>
                        <tr>
                          <th>Ticker</th>
                          <th>Qty</th>
                          <th>Entry</th>
                          <th>Current</th>
                          <th>P&L</th>
                        </tr>
                      </thead>
                      <tbody>
                        {positions.map((p) => (
                          <tr key={p.id}>
                            <td className="signal-ticker">{p.ticker}</td>
                            <td>{p.quantity}</td>
                            <td>${p.entry_price.toLocaleString()}</td>
                            <td>${p.current_price.toLocaleString()}</td>
                            <td className={p.pnl >= 0 ? "pnl-positive" : "pnl-negative"}>
                              {p.pnl >= 0 ? "+" : ""}${p.pnl.toLocaleString()}{" "}
                              <span className="pnl-pct">{p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct}%</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </div>

            <section className="dash-account" aria-labelledby="account-title">
              <div className="dash-section-head">
                <h2 id="account-title">Account</h2>
              </div>
              <dl className="account-grid">
                <div>
                  <dt>Email</dt>
                  <dd>{stats?.email}</dd>
                </div>
                <div>
                  <dt>Plan</dt>
                  <dd>{stats?.plan}</dd>
                </div>
                <div>
                  <dt>Execution mode</dt>
                  <dd>{stats?.execution_mode}</dd>
                </div>
                <div>
                  <dt>API access</dt>
                  <dd>{stats?.api_access ? "Enabled" : "Disabled"}</dd>
                </div>
              </dl>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function fmtNum(v) {
  return parseFloat(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
