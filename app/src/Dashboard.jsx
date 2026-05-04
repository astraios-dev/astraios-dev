import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { createChart, ColorType } from "lightweight-charts";
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
  const [modelInfo, setModelInfo] = useState(null);
  const [bybitPositions, setBybitPositions] = useState([]);
  const [wallet, setWallet] = useState(null);
  const [bybitError, setBybitError] = useState(null);
  const symbolRef = useRef(null);
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const [allSymbols, setAllSymbols] = useState([]);
  const [symbolOpen, setSymbolOpen] = useState(false);
  const [symbolSearch, setSymbolSearch] = useState("");
  const [chartInterval, setChartInterval] = useState(() => localStorage.getItem("astraios_interval") || "60");
  const [leverage, setLeverage] = useState(() => localStorage.getItem("astraios_leverage") || "10");
  const [settingLev, setSettingLev] = useState(false);
  const [orderForm, setOrderForm] = useState(() => {
    const saved = localStorage.getItem("astraios_symbol");
    return { symbol: saved || "BTCUSDT", side: "Buy", qty: "", tp: "", sl: "" };
  });
  const [tradingMode, setTradingMode] = useState(() => localStorage.getItem("astraios_mode") || "live");
  const isLive = tradingMode === "live";
  const isDemo = !isLive;
  const [keysForm, setKeysForm] = useState({ apiKey: "", apiSecret: "" });
  const [keysStatus, setKeysStatus] = useState(null);
  const [savingKeys, setSavingKeys] = useState(false);
  const [showKeysForm, setShowKeysForm] = useState(false);
  const [testnetKeysForm, setTestnetKeysForm] = useState({ apiKey: "", apiSecret: "" });
  const [testnetKeysStatus, setTestnetKeysStatus] = useState(null);
  const [savingTestnetKeys, setSavingTestnetKeys] = useState(false);
  const [showTestnetKeysForm, setShowTestnetKeysForm] = useState(false);
  const [orderStatus, setOrderStatus] = useState(null);
  const [ordering, setOrdering] = useState(false);
  const [closing, setClosing] = useState(null);

  const [autoConfig, setAutoConfig] = useState(null);
  const [autoConfigForm, setAutoConfigForm] = useState(null);
  const [autoStats, setAutoStats] = useState(null);
  const [autoPnl, setAutoPnl] = useState(null);
  const [autoLog, setAutoLog] = useState([]);
  const [savingAuto, setSavingAuto] = useState(false);
  const [autoStatus, setAutoStatus] = useState(null);
  const [showAutoLog, setShowAutoLog] = useState(false);

  // Sync auto-trade mode with global toggle: Demo mode → auto-trade demo on, Live → keep current
  useEffect(() => {
    if (!autoConfigForm) return;
    if (isDemo) setAutoConfigForm((f) => ({ ...f, demo: true }));
  }, [isDemo]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // Stable ref to current mode — readable inside async callbacks without stale closure
  const tradingModeRef = useRef(tradingMode);
  useEffect(() => { tradingModeRef.current = tradingMode; }, [tradingMode]);

  const loadBybit = useCallback(() => {
    const modeAtCall = tradingModeRef.current;
    const demo = modeAtCall !== "live";
    return Promise.all([
      api.tradePositions(null, demo),
      api.tradeWallet(demo),
    ]).then(([bp, w]) => {
      // Discard if mode changed while this request was in flight
      if (tradingModeRef.current !== modeAtCall) return;
      setBybitPositions(bp);
      setWallet(w);
      setBybitError(null);
    }).catch((e) => {
      if (tradingModeRef.current !== modeAtCall) return;
      setBybitPositions([]);
      setWallet(null);
      setBybitError(e.message);
    });
  }, []);

  useEffect(() => {
    api.tradeSymbols().then(setAllSymbols).catch(() => {});
    api.modelInfo().then(setModelInfo).catch(() => {});
    api.autoTradeConfig().then((cfg) => {
      setAutoConfig(cfg);
      setAutoConfigForm(cfg);
      api.autoTradePnl(cfg?.demo ?? true).then(setAutoPnl).catch(() => {});
    }).catch(() => {});
    api.autoTradeStats().then(setAutoStats).catch(() => {});
    api.autoTradeLog().then(setAutoLog).catch(() => {});
  }, []);

  useEffect(() => {
    if (!symbolOpen) return;
    const handler = (e) => {
      if (symbolRef.current && !symbolRef.current.contains(e.target)) setSymbolOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [symbolOpen]);

  useEffect(() => {
    if (loading || !chartRef.current) return;
    try {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
        chartInstanceRef.current = null;
      }
      const el = chartRef.current;
      const chart = createChart(el, {
        layout: { background: { type: ColorType.Solid, color: "#050505" }, textColor: "#9a9a97", fontFamily: "Inter, sans-serif", fontSize: 11 },
        grid: { vertLines: { color: "#1a1a1a" }, horzLines: { color: "#1a1a1a" } },
        crosshair: { vertLine: { color: "#2a2a2a", labelBackgroundColor: "#141414" }, horzLine: { color: "#2a2a2a", labelBackgroundColor: "#141414" } },
        rightPriceScale: { borderColor: "#2a2a2a", autoScale: true },
        timeScale: { borderColor: "#2a2a2a", timeVisible: true, secondsVisible: false },
        width: el.clientWidth,
        height: 340,
      });
      chartInstanceRef.current = chart;
      api.tradeKlines(orderForm.symbol, chartInterval, 1000).then((data) => {
        if (!chartInstanceRef.current || !data.length) return;
        const lastPrice = data[data.length - 1].close;
        let precision = 2;
        let minMove = 0.01;
        if (lastPrice < 0.01) { precision = 8; minMove = 0.00000001; }
        else if (lastPrice < 1) { precision = 6; minMove = 0.000001; }
        else if (lastPrice < 100) { precision = 4; minMove = 0.0001; }
        else if (lastPrice < 10000) { precision = 2; minMove = 0.01; }
        else { precision = 1; minMove = 0.1; }
        const candleSeries = chart.addCandlestickSeries({
          upColor: "#2ecb71", downColor: "#e04040", borderDownColor: "#e04040", borderUpColor: "#2ecb71",
          wickDownColor: "#e04040", wickUpColor: "#2ecb71",
          priceFormat: { type: "price", precision, minMove },
        });
        const volumeSeries = chart.addHistogramSeries({
          priceFormat: { type: "volume" },
          priceScaleId: "vol",
        });
        volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
        candleSeriesRef.current = candleSeries;
        volumeSeriesRef.current = volumeSeries;
        candleSeries.setData(data.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })));
        volumeSeries.setData(data.map((c) => ({ time: c.time, value: c.volume, color: c.close >= c.open ? "rgba(46,203,113,0.15)" : "rgba(224,64,64,0.15)" })));
        chart.timeScale().fitContent();
      }).catch(() => {});
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      const ro = new ResizeObserver(() => { if (el.clientWidth > 0) chart.applyOptions({ width: el.clientWidth }); });
      ro.observe(el);
      return () => { ro.disconnect(); chart.remove(); chartInstanceRef.current = null; candleSeriesRef.current = null; volumeSeriesRef.current = null; };
    } catch (e) {
      console.error("Chart init failed:", e);
    }
  }, [loading, orderForm.symbol, chartInterval]);

  const lastCandleRef = useRef(null);
  useEffect(() => {
    if (loading || !candleSeriesRef.current) return;
    lastCandleRef.current = null;
    const id = setInterval(() => {
      api.tradeKlines(orderForm.symbol, chartInterval, 2).then((data) => {
        if (!candleSeriesRef.current || !data.length) return;
        const c = data[data.length - 1];
        const prev = lastCandleRef.current;
        if (prev && prev.time === c.time && prev.open === c.open && prev.high === c.high && prev.low === c.low && prev.close === c.close) return;
        lastCandleRef.current = c;
        candleSeriesRef.current.update({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close });
        if (volumeSeriesRef.current) {
          volumeSeriesRef.current.update({ time: c.time, value: c.volume, color: c.close >= c.open ? "rgba(46,203,113,0.15)" : "rgba(224,64,64,0.15)" });
        }
      }).catch(() => {});
    }, 1000);
    return () => clearInterval(id);
  }, [loading, orderForm.symbol, chartInterval]);

  useEffect(() => {
    Promise.all([loadData(), loadBybit()])
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [loadData, loadBybit]);

  // Clear stale data instantly on mode switch, then load fresh
  useEffect(() => {
    setBybitPositions([]);
    setWallet(null);
    setBybitError(null);
    loadBybit().catch(() => {});
  }, [isLive]); // eslint-disable-line react-hooks/exhaustive-deps

  // Polling: single stable interval — loadBybit reads mode from ref, never stale
  useEffect(() => {
    const id = setInterval(() => { loadBybit(); }, 1000);
    return () => clearInterval(id);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.marketRefresh();
      await Promise.all([loadData(), loadBybit()]);
    } catch {}
    setRefreshing(false);
  };

  const handleSaveKeys = async (e) => {
    e.preventDefault();
    if (!keysForm.apiKey || !keysForm.apiSecret) return;
    setSavingKeys(true);
    setKeysStatus(null);
    try {
      await api.saveApiKeys({ bybit_api_key: keysForm.apiKey, bybit_api_secret: keysForm.apiSecret });
      setKeysStatus({ ok: true, msg: "API keys saved." });
      setKeysForm({ apiKey: "", apiSecret: "" });
      setShowKeysForm(false);
      await Promise.all([loadData(), loadBybit()]);
    } catch (err) {
      setKeysStatus({ ok: false, msg: err.message });
    }
    setSavingKeys(false);
  };

  const handleRemoveKeys = async () => {
    try {
      await api.removeApiKeys();
      setKeysStatus({ ok: true, msg: "API keys removed." });
      await loadData();
    } catch (err) {
      setKeysStatus({ ok: false, msg: err.message });
    }
  };

  const handleSaveTestnetKeys = async (e) => {
    e.preventDefault();
    if (!testnetKeysForm.apiKey || !testnetKeysForm.apiSecret) return;
    setSavingTestnetKeys(true);
    setTestnetKeysStatus(null);
    try {
      await api.saveTestnetKeys({ bybit_api_key: testnetKeysForm.apiKey, bybit_api_secret: testnetKeysForm.apiSecret });
      setTestnetKeysStatus({ ok: true, msg: "Testnet keys saved." });
      setTestnetKeysForm({ apiKey: "", apiSecret: "" });
      setShowTestnetKeysForm(false);
      await Promise.all([loadData(), loadBybit()]);
    } catch (err) {
      setTestnetKeysStatus({ ok: false, msg: err.message });
    }
    setSavingTestnetKeys(false);
  };

  const handleRemoveTestnetKeys = async () => {
    try {
      await api.removeTestnetKeys();
      setTestnetKeysStatus({ ok: true, msg: "Testnet keys removed." });
      await loadData();
    } catch (err) {
      setTestnetKeysStatus({ ok: false, msg: err.message });
    }
  };

  const handleSaveAutoConfig = async (e) => {
    e.preventDefault();
    setSavingAuto(true);
    setAutoStatus(null);
    try {
      const result = await api.saveAutoTradeConfig(autoConfigForm);
      setAutoConfig(autoConfigForm);
      setAutoStatus({ ok: true, msg: result.enabled ? "Auto-trading enabled." : "Auto-trading disabled." });
      const [logs, stats, pnl] = await Promise.all([
        api.autoTradeLog(),
        api.autoTradeStats(),
        api.autoTradePnl(autoConfigForm.demo),
      ]);
      setAutoLog(logs);
      setAutoStats(stats);
      setAutoPnl(pnl);
    } catch (err) {
      setAutoStatus({ ok: false, msg: err.message });
    }
    setSavingAuto(false);
  };

  const handleLeverage = async (val) => {
    setLeverage(val);
    localStorage.setItem("astraios_leverage", val);
    setSettingLev(true);
    try {
      await api.tradeLeverage({ symbol: orderForm.symbol.toUpperCase(), leverage: val, demo: isDemo});
    } catch {}
    setSettingLev(false);
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
        demo: isDemo,
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
      await api.tradeClose({ symbol: pos.symbol, side: pos.side, qty: String(pos.size), demo: isDemo});
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

  const filteredSymbols = useMemo(() => {
    if (!symbolSearch) return allSymbols.slice(0, 50);
    const q = symbolSearch.toUpperCase();
    return allSymbols.filter((s) => s.symbol.includes(q)).slice(0, 50);
  }, [allSymbols, symbolSearch]);

  const FIRST_PAGE = 10;
  const REST_PAGE = 20;
  const [signalPage, setSignalPage] = useState(0);
  const signalPageCount = useMemo(() => {
    if (signals.length <= FIRST_PAGE) return 1;
    return 1 + Math.ceil((signals.length - FIRST_PAGE) / REST_PAGE);
  }, [signals.length]);
  const pagedSignals = useMemo(() => {
    if (signalPage === 0) return signals.slice(0, FIRST_PAGE);
    const start = FIRST_PAGE + (signalPage - 1) * REST_PAGE;
    return signals.slice(start, start + REST_PAGE);
  }, [signals, signalPage]);

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
          <button
            type="button"
            className="mode-toggle"
            onClick={() => setTradingMode((m) => { const next = m === "live" ? "demo" : "live"; localStorage.setItem("astraios_mode", next); return next; })}
          >
            <span className={`mode-toggle__opt${isLive ? " active" : ""}`}>
              <span className="status-pill__dot status-pill__dot--live" aria-hidden="true" />
              Live
            </span>
            <span className={`mode-toggle__opt${isDemo ? " active" : ""}`}>
              <span className="status-pill__dot" aria-hidden="true" />
              Demo
            </span>
          </button>
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
                    <span className="market-chip__top">
                      <span className="market-chip__ticker">{ticker}</span>
                      <span className={`market-chip__change ${data.change_pct >= 0 ? "market-chip__change--up" : "market-chip__change--down"}`}>
                        {data.change_pct >= 0 ? "+" : ""}{data.change_pct.toFixed(2)}%
                      </span>
                    </span>
                    <span className="market-chip__price">${fmtPrice(data.price)}</span>
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

            {/* Keys not configured prompt */}
            {((isLive && !stats?.has_api_keys) || (isDemo && !stats?.has_demo_keys)) ? (
              <section className="keys-prompt">
                <div className="keys-prompt__icon" aria-hidden="true" />
                <h3 className="keys-prompt__title">
                  {isLive ? "Connect your Bybit account" : "Connect Bybit Demo account"}
                </h3>
                <p className="keys-prompt__text">
                  {isLive
                    ? "Add your Bybit mainnet API key and secret to start live trading."
                    : "Add your Bybit Demo API keys to trade with virtual funds at real market prices."}
                </p>
                <button
                  type="button"
                  className="keys-prompt__btn"
                  onClick={() => {
                    if (isLive) setShowKeysForm(true);
                    else setShowTestnetKeysForm(true);
                    document.getElementById("account-title")?.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  {isLive ? "Add mainnet keys" : "Add demo keys"}
                </button>
              </section>
            ) : (
            <>
            {bybitError && (
              <div className="bybit-error">{isLive ? "Bybit" : "Bybit Demo"}: {bybitError}</div>
            )}

            {/* Trade terminal */}
            <section className="dash-trade" aria-labelledby="trade-title">
              <div className="dash-section-head">
                <h2 id="trade-title">Trade</h2>
                <span className="dash-section-badge">{isLive ? "USDT Perps" : "Demo"}</span>
              </div>

              <div className="trade-layout">
                {/* Chart panel */}
                <div className="trade-chart-panel">
                  <div className="trade-chart-bar">
                    <div ref={symbolRef} className="trade-field trade-field--symbol trade-field--compact" onClick={() => { if (!symbolOpen) { setSymbolOpen(true); setSymbolSearch(""); } }}>
                      <span className="symbol-selected">
                        <span className="symbol-selected__name">{orderForm.symbol}</span>
                        <span className="symbol-selected__caret" aria-hidden="true" />
                      </span>
                      {symbolOpen && (
                        <div className="symbol-dropdown" onClick={(e) => e.stopPropagation()}>
                          <div className="symbol-search-wrap">
                            <input
                              type="text"
                              className="symbol-search"
                              placeholder="Search…"
                              value={symbolSearch}
                              onChange={(e) => setSymbolSearch(e.target.value)}
                              autoFocus
                            />
                          </div>
                          <div className="symbol-list">
                            {filteredSymbols.map((s) => (
                              <button
                                key={s.symbol}
                                type="button"
                                className={`symbol-option${s.symbol === orderForm.symbol ? " symbol-option--active" : ""}`}
                                onClick={() => {
                                  setOrderForm((f) => ({ ...f, symbol: s.symbol }));
                                  localStorage.setItem("astraios_symbol", s.symbol);
                                  setSymbolOpen(false);
                                }}
                              >
                                <span className="symbol-option__name">{s.symbol}</span>
                                <span className={`symbol-option__chg ${parseFloat(s.change_pct) >= 0 ? "symbol-option__chg--up" : "symbol-option__chg--down"}`}>
                                  {(parseFloat(s.change_pct) * 100).toFixed(1)}%
                                </span>
                              </button>
                            ))}
                            {filteredSymbols.length === 0 && (
                              <span className="symbol-option symbol-option--empty">No matches</span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="interval-toggle">
                      {[["5", "5m"], ["15", "15m"], ["60", "1H"], ["240", "4H"], ["D", "1D"]].map(([val, label]) => (
                        <button
                          key={val}
                          type="button"
                          className={`interval-btn${chartInterval === val ? " active" : ""}`}
                          onClick={() => { setChartInterval(val); localStorage.setItem("astraios_interval", val); }}
                        >{label}</button>
                      ))}
                    </div>
                  </div>
                  <div className="trade-chart" ref={chartRef} />
                </div>

                {/* Order panel */}
                <form className="trade-order-panel" onSubmit={handleOrder}>
                  <div className="trade-side-toggle">
                    <button
                      type="button"
                      className={`trade-side-btn trade-side-btn--long${orderForm.side === "Buy" ? " active" : ""}`}
                      onClick={() => setOrderForm((f) => ({ ...f, side: "Buy" }))}
                    >Long</button>
                    <button
                      type="button"
                      className={`trade-side-btn trade-side-btn--short${orderForm.side === "Sell" ? " active" : ""}`}
                      onClick={() => setOrderForm((f) => ({ ...f, side: "Sell" }))}
                    >Short</button>
                  </div>

                  <div className="trade-field">
                    <span className="trade-field__label">Leverage</span>
                    <div className="leverage-selector">
                      {["1", "2", "5", "10", "20", "50", "100"].map((val) => (
                        <button
                          key={val}
                          type="button"
                          className={`leverage-btn${leverage === val ? " active" : ""}`}
                          onClick={() => handleLeverage(val)}
                          disabled={settingLev}
                        >{val}x</button>
                      ))}
                    </div>
                  </div>

                  <label className="trade-field">
                    <span className="trade-field__label">Quantity</span>
                    <input
                      type="text"
                      value={orderForm.qty}
                      onChange={(e) => setOrderForm((f) => ({ ...f, qty: e.target.value }))}
                      placeholder="0.00"
                    />
                  </label>
                  <div className="quick-size">
                    {["10", "25", "50", "100"].map((pct) => (
                      <button
                        key={pct}
                        type="button"
                        className="quick-size-btn"
                        onClick={() => {
                          if (!wallet) return;
                          const avail = parseFloat(wallet.available_balance) || 0;
                          const portion = avail * (parseInt(pct) / 100);
                          setOrderForm((f) => ({ ...f, qty: portion.toFixed(2) }));
                        }}
                      >{pct}%</button>
                    ))}
                  </div>

                  <label className="trade-field">
                    <span className="trade-field__label">Take profit</span>
                    <input
                      type="text"
                      value={orderForm.tp}
                      onChange={(e) => setOrderForm((f) => ({ ...f, tp: e.target.value }))}
                      placeholder="—"
                    />
                  </label>
                  <label className="trade-field">
                    <span className="trade-field__label">Stop loss</span>
                    <input
                      type="text"
                      value={orderForm.sl}
                      onChange={(e) => setOrderForm((f) => ({ ...f, sl: e.target.value }))}
                      placeholder="—"
                    />
                  </label>

                  <button
                    type="submit"
                    className={`trade-submit ${orderForm.side === "Buy" ? "trade-submit--buy" : "trade-submit--sell"}`}
                    disabled={ordering || !orderForm.qty}
                  >
                    {ordering ? "Placing…" : orderForm.side === "Buy" ? "Open long" : "Open short"}
                  </button>

                  {orderStatus && (
                    <p className={`trade-status ${orderStatus.ok ? "trade-status--ok" : "trade-status--err"}`}>
                      {orderStatus.msg}
                    </p>
                  )}
                </form>
              </div>
            </section>

            <section className="dash-bybit-positions" aria-labelledby="bybit-positions-title">
              <div className="dash-section-head">
                <h2 id="bybit-positions-title">{isLive ? "Open positions" : "Demo positions"}</h2>
                <span className="dash-section-badge">{bybitPositions.length} open</span>
              </div>

              {bybitPositions.length === 0 ? (
                <p className="dash-empty">No open derivatives positions.</p>
              ) : (
                <>
                  {/* Desktop table */}
                  <div className="positions-table-wrap pos-desktop">
                    <table className="positions-table">
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
                            <td>${fmtPrice(p.entry_price)}</td>
                            <td>${fmtPrice(p.mark_price)}</td>
                            <td className={p.unrealised_pnl >= 0 ? "pnl-positive" : "pnl-negative"}>
                              {p.unrealised_pnl >= 0 ? "+" : ""}${fmtPrice(p.unrealised_pnl)}
                            </td>
                            <td>{p.leverage}x</td>
                            <td>
                              <button type="button" className="close-pos-btn" onClick={() => handleClose(p)} disabled={closing === p.symbol}>
                                {closing === p.symbol ? "…" : "Close"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Mobile cards */}
                  <div className="pos-cards pos-mobile">
                    {bybitPositions.map((p) => (
                      <div className="pos-card" key={p.symbol + p.side}>
                        <div className="pos-card__head">
                          <span className="pos-card__symbol">{p.symbol}</span>
                          <span className={`signal-action signal-action--${p.side === "Buy" ? "buy" : "sell"}`}>
                            {p.side === "Buy" ? "LONG" : "SHORT"}
                          </span>
                          <span className={`pos-card__pnl ${p.unrealised_pnl >= 0 ? "pnl-positive" : "pnl-negative"}`}>
                            {p.unrealised_pnl >= 0 ? "+" : ""}${fmtPrice(p.unrealised_pnl)}
                          </span>
                        </div>
                        <div className="pos-card__details">
                          <div><span className="pos-card__label">Size</span><span>{p.size}</span></div>
                          <div><span className="pos-card__label">Entry</span><span>${fmtPrice(p.entry_price)}</span></div>
                          <div><span className="pos-card__label">Mark</span><span>${fmtPrice(p.mark_price)}</span></div>
                          <div><span className="pos-card__label">Lev</span><span>{p.leverage}x</span></div>
                        </div>
                        <button type="button" className="pos-card__close" onClick={() => handleClose(p)} disabled={closing === p.symbol}>
                          {closing === p.symbol ? "Closing…" : "Close position"}
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>
            </>
            )}

            {/* Signals */}
            <div className="dash-grid">
              <section className="dash-signals" aria-labelledby="signals-title">
                <div className="dash-section-head">
                  <h2 id="signals-title">{signalPage === 0 ? "Top trades" : "All signals"}</h2>
                  <div className="signals-head-right">
                    {modelInfo?.model_loaded && (
                      <span className="model-badge" title={`${modelInfo.n_features} features · d_model=${modelInfo.d_model} · ${modelInfo.n_layers}L · seq=${modelInfo.seq_len}`}>
                        Transformer · {modelInfo.val_acc}% val
                      </span>
                    )}
                    {modelInfo && !modelInfo.model_loaded && (
                      <span className="model-badge model-badge--heuristic">Heuristic</span>
                    )}
                    <span className="dash-section-badge">{signalPage === 0 ? `Top ${Math.min(FIRST_PAGE, signals.length)}` : `${signals.length} total`}</span>
                  </div>
                </div>

                {signals.length === 0 ? (
                  <p className="dash-empty">No signals yet. They will appear here as the engine generates them.</p>
                ) : (
                  <>
                    {/* Desktop table */}
                    <div className="signals-table-wrap sig-desktop">
                      <table className="signals-table">
                        <thead>
                          <tr>
                            {signalPage === 0 && <th>#</th>}
                            <th>Ticker</th>
                            <th>Action</th>
                            <th>Confidence</th>
                            <th>Rationale</th>
                            <th>Time</th>
                          </tr>
                        </thead>
                        <tbody>
                          {pagedSignals.map((s, i) => (
                            <tr key={s.id}>
                              {signalPage === 0 && <td className="signal-rank">{i + 1}</td>}
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

                    {/* Mobile cards */}
                    <div className="sig-cards sig-mobile">
                      {pagedSignals.map((s, i) => (
                        <div className="sig-card" key={s.id}>
                          <div className="sig-card__head">
                            {signalPage === 0 && <span className="sig-card__rank">{i + 1}</span>}
                            <span className="sig-card__ticker">{s.ticker}</span>
                            <span className={`signal-action signal-action--${s.action.toLowerCase()}`}>{s.action}</span>
                            <span className="sig-card__conf">{(s.confidence * 100).toFixed(0)}%</span>
                          </div>
                          <div className="sig-card__bar">
                            <span className="sig-card__bar-fill" style={{ width: `${s.confidence * 100}%` }} />
                          </div>
                          {s.rationale && <p className="sig-card__rationale">{s.rationale}</p>}
                        </div>
                      ))}
                    </div>

                    {signalPageCount > 1 && (
                      <nav className="signals-pager" aria-label="Signal pages">
                        <button
                          type="button"
                          className="pager-btn"
                          disabled={signalPage === 0}
                          onClick={() => setSignalPage((p) => p - 1)}
                          aria-label="Previous page"
                        >
                          Prev
                        </button>
                        <span className="pager-info">
                          {signalPage + 1} / {signalPageCount}
                        </span>
                        <button
                          type="button"
                          className="pager-btn"
                          disabled={signalPage >= signalPageCount - 1}
                          onClick={() => setSignalPage((p) => p + 1)}
                          aria-label="Next page"
                        >
                          Next
                        </button>
                      </nav>
                    )}
                  </>
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
                  <dt>Mainnet API</dt>
                  <dd>
                    {stats?.has_api_keys ? (
                      <span className="api-key-connected">Connected ({stats.api_key_hint})</span>
                    ) : (
                      <span className="api-key-none">Not configured</span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Demo API</dt>
                  <dd>
                    {stats?.has_demo_keys ? (
                      <span className="api-key-connected">Connected ({stats.demo_key_hint})</span>
                    ) : (
                      <span className="api-key-none">Not configured</span>
                    )}
                  </dd>
                </div>
              </dl>

              <div className="api-keys-section">
                {stats?.has_api_keys ? (
                  <div className="api-keys-actions">
                    <button type="button" className="api-keys-btn" onClick={() => setShowKeysForm((v) => !v)}>
                      {showKeysForm ? "Cancel" : "Update live keys"}
                    </button>
                    <button type="button" className="api-keys-btn api-keys-btn--danger" onClick={handleRemoveKeys}>
                      Remove
                    </button>
                  </div>
                ) : (
                  <button type="button" className="api-keys-btn" onClick={() => setShowKeysForm((v) => !v)}>
                    {showKeysForm ? "Cancel" : "Connect Bybit live"}
                  </button>
                )}
                {showKeysForm && (
                  <form className="api-keys-form" onSubmit={handleSaveKeys}>
                    <label className="trade-field">
                      <span className="trade-field__label">Live API Key</span>
                      <input type="text" value={keysForm.apiKey} onChange={(e) => setKeysForm((f) => ({ ...f, apiKey: e.target.value }))} placeholder="Mainnet API key" autoComplete="off" />
                    </label>
                    <label className="trade-field">
                      <span className="trade-field__label">Live API Secret</span>
                      <input type="password" value={keysForm.apiSecret} onChange={(e) => setKeysForm((f) => ({ ...f, apiSecret: e.target.value }))} placeholder="Mainnet API secret" autoComplete="off" />
                    </label>
                    <button type="submit" className="trade-submit trade-submit--buy" disabled={savingKeys || !keysForm.apiKey || !keysForm.apiSecret}>
                      {savingKeys ? "Saving…" : "Save"}
                    </button>
                  </form>
                )}
                {keysStatus && (
                  <p className={`trade-status ${keysStatus.ok ? "trade-status--ok" : "trade-status--err"}`}>{keysStatus.msg}</p>
                )}
              </div>

              <div className="api-keys-section">
                {stats?.has_demo_keys ? (
                  <div className="api-keys-actions">
                    <button type="button" className="api-keys-btn" onClick={() => setShowTestnetKeysForm((v) => !v)}>
                      {showTestnetKeysForm ? "Cancel" : "Update demo keys"}
                    </button>
                    <button type="button" className="api-keys-btn api-keys-btn--danger" onClick={handleRemoveTestnetKeys}>
                      Remove
                    </button>
                  </div>
                ) : (
                  <button type="button" className="api-keys-btn" onClick={() => setShowTestnetKeysForm((v) => !v)}>
                    {showTestnetKeysForm ? "Cancel" : "Connect Bybit demo"}
                  </button>
                )}
                {showTestnetKeysForm && (
                  <form className="api-keys-form" onSubmit={handleSaveTestnetKeys}>
                    <label className="trade-field">
                      <span className="trade-field__label">Demo API Key</span>
                      <input type="text" value={testnetKeysForm.apiKey} onChange={(e) => setTestnetKeysForm((f) => ({ ...f, apiKey: e.target.value }))} placeholder="Demo API key" autoComplete="off" />
                    </label>
                    <label className="trade-field">
                      <span className="trade-field__label">Demo API Secret</span>
                      <input type="password" value={testnetKeysForm.apiSecret} onChange={(e) => setTestnetKeysForm((f) => ({ ...f, apiSecret: e.target.value }))} placeholder="Demo API secret" autoComplete="off" />
                    </label>
                    <button type="submit" className="trade-submit trade-submit--buy" disabled={savingTestnetKeys || !testnetKeysForm.apiKey || !testnetKeysForm.apiSecret}>
                      {savingTestnetKeys ? "Saving…" : "Save"}
                    </button>
                  </form>
                )}
                {testnetKeysStatus && (
                  <p className={`trade-status ${testnetKeysStatus.ok ? "trade-status--ok" : "trade-status--err"}`}>{testnetKeysStatus.msg}</p>
                )}
              </div>
            </section>

            <section className="dash-auto-trade" aria-labelledby="auto-trade-title">
              <div className="dash-section-head">
                <h2 id="auto-trade-title">Auto-Trading</h2>
                <div className="auto-trade-head-right">
                  {autoConfig?.enabled
                    ? <span className="auto-trade-badge auto-trade-badge--on">ACTIVE — {autoConfig.demo ? "DEMO" : "LIVE"}</span>
                    : <span className="auto-trade-badge auto-trade-badge--off">OFF</span>
                  }
                  <span className="auto-trade-global-mode">{isLive ? "Global: Live" : "Global: Demo"}</span>
                </div>
              </div>

              {autoConfigForm && (
                <form className="auto-trade-form" onSubmit={handleSaveAutoConfig}>
                  <div className="auto-trade-toggle-row">
                    <label className="auto-trade-toggle">
                      <input
                        type="checkbox"
                        checked={autoConfigForm.enabled}
                        onChange={(e) => setAutoConfigForm((f) => ({ ...f, enabled: e.target.checked }))}
                      />
                      <span className="auto-trade-toggle__track" />
                      <span className="auto-trade-toggle__label">
                        {autoConfigForm.enabled ? "Enabled" : "Disabled"}
                      </span>
                    </label>

                    <div className="auto-trade-mode-select">
                      <span className="trade-field__label">Execution mode</span>
                      <div className="auto-trade-mode-btns">
                        <button
                          type="button"
                          className={`auto-trade-mode-btn${autoConfigForm.demo ? " active" : ""}`}
                          onClick={() => setAutoConfigForm((f) => ({ ...f, demo: true }))}
                        >Demo</button>
                        <button
                          type="button"
                          className={`auto-trade-mode-btn danger${!autoConfigForm.demo ? " active" : ""}`}
                          onClick={() => setAutoConfigForm((f) => ({ ...f, demo: false }))}
                        >Live</button>
                      </div>
                      {!autoConfigForm.demo && (
                        <p className="auto-trade-mode-warn">⚠ Live mode places real orders with real funds.</p>
                      )}
                    </div>
                  </div>

                  <div className="auto-trade-grid">
                    <label className="trade-field">
                      <span className="trade-field__label">Min Confidence</span>
                      <input
                        type="number" step="0.01" min="0.5" max="1"
                        value={autoConfigForm.confidence_threshold}
                        onChange={(e) => setAutoConfigForm((f) => ({ ...f, confidence_threshold: parseFloat(e.target.value) }))}
                      />
                    </label>
                    <label className="trade-field">
                      <span className="trade-field__label">Max Positions</span>
                      <input
                        type="number" min="1" max="10"
                        value={autoConfigForm.max_positions}
                        onChange={(e) => setAutoConfigForm((f) => ({ ...f, max_positions: parseInt(e.target.value) }))}
                      />
                    </label>
                    <label className="trade-field">
                      <span className="trade-field__label">Size % of Equity</span>
                      <input
                        type="number" step="0.1" min="0.1" max="50"
                        value={autoConfigForm.position_size_pct}
                        onChange={(e) => setAutoConfigForm((f) => ({ ...f, position_size_pct: parseFloat(e.target.value) }))}
                      />
                    </label>
                    <label className="trade-field">
                      <span className="trade-field__label">Leverage</span>
                      <input
                        type="number" min="1" max="20"
                        value={autoConfigForm.leverage}
                        onChange={(e) => setAutoConfigForm((f) => ({ ...f, leverage: parseInt(e.target.value) }))}
                      />
                    </label>
                    <label className="trade-field">
                      <span className="trade-field__label">Take Profit %</span>
                      <input
                        type="number" step="0.1" min="0.1"
                        value={autoConfigForm.tp_pct}
                        onChange={(e) => setAutoConfigForm((f) => ({ ...f, tp_pct: parseFloat(e.target.value) }))}
                      />
                    </label>
                    <label className="trade-field">
                      <span className="trade-field__label">Stop Loss %</span>
                      <input
                        type="number" step="0.1" min="0.1"
                        value={autoConfigForm.sl_pct}
                        onChange={(e) => setAutoConfigForm((f) => ({ ...f, sl_pct: parseFloat(e.target.value) }))}
                      />
                    </label>
                    <label className="trade-field auto-trade-symbols">
                      <span className="trade-field__label">Symbols (comma-separated)</span>
                      <input
                        type="text"
                        value={autoConfigForm.symbols}
                        onChange={(e) => setAutoConfigForm((f) => ({ ...f, symbols: e.target.value }))}
                        placeholder="BTCUSDT,ETHUSDT,SOLUSDT"
                      />
                    </label>
                  </div>

                  <button type="submit" className="trade-submit trade-submit--buy" disabled={savingAuto}>
                    {savingAuto ? "Saving…" : "Save configuration"}
                  </button>
                  {autoStatus && (
                    <p className={`trade-status ${autoStatus.ok ? "trade-status--ok" : "trade-status--err"}`}>
                      {autoStatus.msg}
                    </p>
                  )}
                </form>
              )}

              {autoStats && (
                <div className="auto-trade-stats">
                  <div className="dash-section-label" style={{marginBottom:"0.75rem"}}>Performance</div>
                  <div className="auto-stats-grid">
                    <div className="auto-stat">
                      <span className="auto-stat__label">Total orders</span>
                      <span className="auto-stat__value">{autoStats.total_orders}</span>
                    </div>
                    <div className="auto-stat">
                      <span className="auto-stat__label">Filled</span>
                      <span className="auto-stat__value val-up">{autoStats.filled}</span>
                    </div>
                    <div className="auto-stat">
                      <span className="auto-stat__label">Errors</span>
                      <span className={`auto-stat__value${autoStats.errors > 0 ? " val-down" : ""}`}>{autoStats.errors}</span>
                    </div>
                    <div className="auto-stat">
                      <span className="auto-stat__label">Fill rate</span>
                      <span className="auto-stat__value">{autoStats.success_rate}%</span>
                    </div>
                    <div className="auto-stat">
                      <span className="auto-stat__label">Today</span>
                      <span className="auto-stat__value">{autoStats.today_orders} orders</span>
                    </div>
                    <div className="auto-stat">
                      <span className="auto-stat__label">Active</span>
                      <span className={`auto-stat__value${autoStats.active_positions > 0 ? " val-up" : ""}`}>{autoStats.active_positions} positions</span>
                    </div>
                    <div className="auto-stat">
                      <span className="auto-stat__label">Avg confidence</span>
                      <span className="auto-stat__value">{autoStats.avg_confidence}%</span>
                    </div>
                    <div className="auto-stat">
                      <span className="auto-stat__label">Avg hold time</span>
                      <span className="auto-stat__value">
                        {autoStats.avg_hold_minutes >= 60
                          ? `${(autoStats.avg_hold_minutes / 60).toFixed(1)}h`
                          : `${autoStats.avg_hold_minutes}m`}
                      </span>
                    </div>
                    <div className="auto-stat">
                      <span className="auto-stat__label">Buy / Sell</span>
                      <span className="auto-stat__value">
                        <span className="val-up">{autoStats.by_side?.Buy ?? 0}</span>
                        {" / "}
                        <span className="val-down">{autoStats.by_side?.Sell ?? 0}</span>
                      </span>
                    </div>
                  </div>
                  {autoStats.top_symbols?.length > 0 && (
                    <div className="auto-stats-symbols">
                      <span className="dash-section-label" style={{marginBottom:"0.5rem",display:"block"}}>Top symbols</span>
                      {autoStats.top_symbols.map((s) => (
                        <div className="auto-stats-symbol-row" key={s.symbol}>
                          <span className="auto-stats-symbol-name">{s.symbol}</span>
                          <span className="auto-stats-symbol-bar-wrap">
                            <span
                              className="auto-stats-symbol-bar"
                              style={{width: `${Math.min(100, (s.filled / (autoStats.filled || 1)) * 100)}%`}}
                            />
                          </span>
                          <span className="auto-stats-symbol-count val-up">{s.filled} filled</span>
                          {s.errors > 0 && <span className="auto-stats-symbol-count val-down">{s.errors} err</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {autoPnl && (
                <div className="auto-pnl-section">
                  <div className="dash-section-label" style={{marginBottom:"0.75rem"}}>Realized P&amp;L</div>

                  <div className="auto-pnl-summary">
                    <div className="auto-pnl-total">
                      <span className="auto-stat__label">Net P&amp;L</span>
                      <span className={`auto-pnl-total__value ${autoPnl.summary.total_pnl >= 0 ? "val-up" : "val-down"}`}>
                        {autoPnl.summary.total_pnl >= 0 ? "+" : ""}{autoPnl.summary.total_pnl.toFixed(4)} USDT
                      </span>
                    </div>
                    <div className="auto-pnl-meta">
                      <div className="auto-stat">
                        <span className="auto-stat__label">Win rate</span>
                        <span className="auto-stat__value">{autoPnl.summary.win_rate}%</span>
                      </div>
                      <div className="auto-stat">
                        <span className="auto-stat__label">Trades</span>
                        <span className="auto-stat__value">
                          <span className="val-up">{autoPnl.summary.win_count}W</span>
                          {" / "}
                          <span className="val-down">{autoPnl.summary.loss_count}L</span>
                        </span>
                      </div>
                      <div className="auto-stat">
                        <span className="auto-stat__label">Avg win</span>
                        <span className="auto-stat__value val-up">+{autoPnl.summary.avg_win.toFixed(4)}</span>
                      </div>
                      <div className="auto-stat">
                        <span className="auto-stat__label">Avg loss</span>
                        <span className="auto-stat__value val-down">{autoPnl.summary.avg_loss.toFixed(4)}</span>
                      </div>
                      <div className="auto-stat">
                        <span className="auto-stat__label">Best trade</span>
                        <span className="auto-stat__value val-up">+{autoPnl.summary.largest_win.toFixed(4)}</span>
                      </div>
                      <div className="auto-stat">
                        <span className="auto-stat__label">Worst trade</span>
                        <span className="auto-stat__value val-down">{autoPnl.summary.largest_loss.toFixed(4)}</span>
                      </div>
                    </div>
                  </div>

                  {autoPnl.trades.length > 0 && (
                    <div className="auto-pnl-trades">
                      <table className="auto-trade-table">
                        <thead>
                          <tr>
                            <th>Time</th>
                            <th>Symbol</th>
                            <th>Side</th>
                            <th>Qty</th>
                            <th>Entry</th>
                            <th>Exit</th>
                            <th>P&amp;L</th>
                          </tr>
                        </thead>
                        <tbody>
                          {autoPnl.trades.map((t, i) => (
                            <tr key={i} className={t.pnl >= 0 ? "auto-trade-row--win" : "auto-trade-row--loss"}>
                              <td>{t.updated_time ? new Date(parseInt(t.updated_time)).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}) : "—"}</td>
                              <td>{t.symbol}</td>
                              <td className={t.side === "Buy" ? "val-up" : "val-down"}>{t.side}</td>
                              <td>{t.qty}</td>
                              <td>{t.entry_price.toFixed(4)}</td>
                              <td>{t.exit_price.toFixed(4)}</td>
                              <td className={t.pnl >= 0 ? "val-up" : "val-down"}>
                                {t.pnl >= 0 ? "+" : ""}{t.pnl.toFixed(4)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {autoPnl.trades.length === 0 && (
                    <p className="dash-empty">No closed trades yet.</p>
                  )}
                </div>
              )}

              <div className="auto-trade-log-header">
                <span className="dash-section-label">Trade Log</span>
                <button type="button" className="api-keys-btn" onClick={() => {
                  setShowAutoLog((v) => !v);
                  if (!showAutoLog) api.autoTradeLog().then(setAutoLog).catch(() => {});
                }}>
                  {showAutoLog ? "Hide" : `Show (${autoLog.length})`}
                </button>
              </div>
              {showAutoLog && (
                <div className="auto-trade-log">
                  {autoLog.length === 0 ? (
                    <p className="dash-empty">No auto-trades executed yet.</p>
                  ) : (
                    <table className="auto-trade-table">
                      <thead>
                        <tr>
                          <th>Time</th>
                          <th>Symbol</th>
                          <th>Action</th>
                          <th>Side</th>
                          <th>Qty</th>
                          <th>Conf</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {autoLog.map((l) => (
                          <tr key={l.id} className={l.status === "error" ? "auto-trade-row--error" : ""}>
                            <td>{new Date(l.created_at).toLocaleTimeString()}</td>
                            <td>{l.symbol}</td>
                            <td>{l.action}</td>
                            <td className={l.side === "Buy" ? "val-up" : "val-down"}>{l.side}</td>
                            <td>{l.qty}</td>
                            <td>{(l.confidence * 100).toFixed(0)}%</td>
                            <td>{l.status === "error" ? `❌ ${l.error?.slice(0, 40)}` : "✓"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </section>
          </>
        )}
      </main>

      <footer className="dash-footer">
        <div className="dash-footer__left">
          <span className="logo-mark logo-mark--tiny" role="img" aria-label="Astraios" />
          <span className="dash-footer__copy">© {new Date().getFullYear()} Astraios</span>
        </div>
        <div className="dash-footer__links">
          <a href="mailto:hello@astraios.tech">Contact</a>
          <a href="https://github.com/astraios-dev" rel="noreferrer noopener">GitHub</a>
        </div>
        <span className="dash-footer__disclaimer">Live derivatives trading via Bybit · not investment advice</span>
      </footer>
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

function fmtPrice(v) {
  const n = Number(v);
  if (n === 0) return "0.00";
  const abs = Math.abs(n);
  let decimals;
  if (abs >= 1000) decimals = 2;
  else if (abs >= 1) decimals = 4;
  else if (abs >= 0.01) decimals = 6;
  else decimals = 8;
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: decimals });
}
