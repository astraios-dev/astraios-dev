import React, { useEffect, useRef, useState } from "react";

const navItems = [
  { label: "Platform", href: "#platform" },
  { label: "Stack", href: "#stack" },
  { label: "Protocol", href: "#protocol" },
  { label: "Team", href: "#team" },
  { label: "Surfaces", href: "#surfaces" },
  { label: "Deck", href: "/deck/" },
  { label: "Contact", href: "#contact" },
];

const principles = [
  {
    number: "I",
    title: "Signal over noise.",
    text: "Every model output earns its place. Users see trades they can act on, with confidence scores and the reasoning behind them — not a feed of predictions.",
  },
  {
    number: "II",
    title: "Data is the moat.",
    text: "Models converge; data does not. We combine market microstructure, macro regime signals, and behavioural data from our own users to compound edge that cannot be bought.",
  },
  {
    number: "III",
    title: "Paper-trade before live.",
    text: "Backtests lie. Every strategy runs on paper for at least thirty days before a single dollar routes through the execution layer.",
  },
];

const systemPanels = [
  {
    number: "01",
    title: "Data Layer",
    text: "Polygon and CCXT for prices, FRED for macro, SEC EDGAR for insider filings — normalised into a TimescaleDB store and streamed over Kafka for live inference.",
  },
  {
    number: "02",
    title: "Model Layer",
    text: "HMM + LSTM ensembles for regime detection, Temporal Fusion Transformers for multi-horizon forecasts, and PPO/SAC agents for portfolio optimisation.",
  },
  {
    number: "03",
    title: "Strategy Engine",
    text: "Signal generation with confidence scores, fractional Kelly position sizing, and a VectorBT harness that clears thousands of parameter sweeps per minute.",
  },
  {
    number: "04",
    title: "Execution Layer",
    text: "Paper trading by default via Alpaca. Live routing is opt-in, queued through Redis to decouple strategy from order flow, and logged end to end.",
  },
];

const teamMembers = [
  {
    initials: "AM",
    name: "Amyanshu",
    role: "Systems & Research",
    text: "Owns the modelling stack — regime detection, forecasting, and the feature store that keeps training and inference honest.",
  },
  {
    initials: "SG",
    name: "Swetagni",
    role: "Product & Platform",
    text: "Runs the consumer surface and the trading API. Translates model output into interfaces users can read, trust, and hand capital to.",
  },
];

const processSteps = [
  {
    number: "01",
    title: "Ingest",
    text: "Pull price, macro, and filings data into a single store. One source of truth for training, backtests, and live inference.",
  },
  {
    number: "02",
    title: "Model",
    text: "Baseline first. Only graduate to ensembles, transformers, or RL once the simpler model has been fairly beaten.",
  },
  {
    number: "03",
    title: "Backtest",
    text: "Strict time-based splits, survivorship-adjusted universes, and look-ahead checks before a strategy is allowed near paper trading.",
  },
  {
    number: "04",
    title: "Deploy",
    text: "Thirty days on paper, ONNX-exported inference path, and a kill switch wired into every live account from day one.",
  },
];

function App() {
  useScrollReveal();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    const mq = window.matchMedia("(min-width: 981px)");
    const onWide = (e) => {
      if (e.matches) setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    mq.addEventListener("change", onWide);
    return () => {
      window.removeEventListener("keydown", onKey);
      mq.removeEventListener("change", onWide);
    };
  }, [menuOpen]);

  return (
    <div className="site">
      <header className={`site-header${menuOpen ? " site-header--menu-open" : ""}`}>
        <button
          type="button"
          className="nav-toggle"
          aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={menuOpen}
          aria-controls="primary-navigation"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span className="nav-toggle__bar" aria-hidden="true" />
          <span className="nav-toggle__bar" aria-hidden="true" />
          <span className="nav-toggle__bar" aria-hidden="true" />
        </button>

        <a className="brand-lockup" href="#top" aria-label="Astraios home">
          <LogoMark size="small" />
          <span className="brand-divider" aria-hidden="true" />
          <Wordmark />
        </a>

        <nav
          id="primary-navigation"
          aria-label="Primary navigation"
          data-open={menuOpen ? "true" : "false"}
        >
          {navItems.map((item) => (
            <a key={item.label} href={item.href} onClick={() => setMenuOpen(false)}>
              {item.label}
            </a>
          ))}
        </nav>

        <span className="status-pill" role="status">
          <span className="status-pill__dot" aria-hidden="true" />
          <span className="status-pill__text">Private beta — Q2 2026</span>
        </span>
      </header>

      <main id="top">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero__label">
            <span>1.</span>
            <span>Quantitative Intelligence</span>
          </div>

          <div className="hero__mark" aria-hidden="true">
            <LogoMark size="large" />
          </div>

          <div className="hero__content">
            <p className="eyebrow">Astraios Quant Platform</p>
            <h1 id="hero-title">
              Markets,
              <br />
              made legible.
            </h1>
            <p>
              An ML platform for retail and semi-pro traders. We read market
              microstructure, macro regime, and filings data in parallel, then
              surface trades with confidence scores and an auto-execution API
              behind them.
            </p>
            <div className="hero__actions">
              <a className="primary-action" href="#contact">
                Request access
              </a>
              <a className="secondary-action" href="#stack">
                Read the system
                <span aria-hidden="true">↓</span>
              </a>
            </div>
          </div>

          <dl className="hero__meta" aria-label="Platform metadata">
            <div>
              <dt>Company</dt>
              <dd>Astraios</dd>
            </div>
            <div>
              <dt>Coverage</dt>
              <dd>US equities · Crypto</dd>
            </div>
            <div>
              <dt>Execution</dt>
              <dd>Paper default · Alpaca API</dd>
            </div>
            <div>
              <dt>Since</dt>
              <dd>MMXXVI</dd>
            </div>
          </dl>
        </section>

        <section className="principles" aria-labelledby="principles-title" data-reveal>
          <div className="section-label">
            <span>2.</span>
            <span>Operating Principles</span>
          </div>

          <h2 id="principles-title" className="sr-only">
            Operating principles
          </h2>

          <ol className="principle-list">
            {principles.map((p) => (
              <li className="principle" key={p.number}>
                <span className="principle__number">{p.number}</span>
                <div>
                  <h3>{p.title}</h3>
                  <p>{p.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="lockup-band" id="platform" aria-labelledby="platform-title" data-reveal>
          <div className="section-label">
            <span>3.</span>
            <span>Two Products, One Engine</span>
          </div>

          <div className="display-lockup">
            <LogoMark size="medium" />
            <span className="lockup-divider" aria-hidden="true" />
            <Wordmark />
          </div>

          <div className="identity-copy">
            <h2 id="platform-title">A signal layer for humans, an execution layer for code.</h2>
            <p>
              The consumer app reads the same strategy engine the auto-trading
              API does. Retail traders see ranked signals with explainability;
              developers and allocators route orders through a paper-first API
              with the same confidence scores attached.
            </p>
          </div>
        </section>

        <section className="systems-section" id="stack" aria-labelledby="stack-title" data-reveal>
          <div className="section-label">
            <span>4.</span>
            <span>Architecture</span>
          </div>

          <div className="systems-heading">
            <h2 id="stack-title">Four layers from raw market data to routed order.</h2>
            <a href="#contact" className="text-link">
              Request access
            </a>
          </div>

          <div className="system-grid">
            {systemPanels.map((panel) => (
              <article className="system-panel" key={panel.title}>
                <span>{panel.number}</span>
                <h3>{panel.title}</h3>
                <p>{panel.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="process" id="protocol" aria-labelledby="protocol-title" data-reveal>
          <div className="section-label">
            <span>5.</span>
            <span>Research Protocol</span>
          </div>

          <div className="process__heading">
            <h2 id="protocol-title">From raw ticks to live capital, in four disciplined moves.</h2>
            <p>
              A strategy only earns a live account by clearing every stage.
              Backtest performance alone is not enough — survivorship,
              look-ahead, and paper drift are all grounds for rejection.
            </p>
          </div>

          <ol className="process__steps">
            {processSteps.map((step) => (
              <li className="process-step" key={step.number}>
                <span className="process-step__number">{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="team" id="team" aria-labelledby="team-title" data-reveal>
          <div className="section-label">
            <span>6.</span>
            <span>Operators</span>
          </div>

          <div className="team__heading">
            <h2 id="team-title">A two-person team, research and product.</h2>
            <p>
              Small enough to ship without coordination cost. One owns the
              models and data, the other owns the surface and API — and both
              sit inside the same live trading loop.
            </p>
          </div>

          <ul className="team__grid">
            {teamMembers.map((member) => (
              <li className="team-card" key={member.name}>
                <span className="team-card__mark" aria-hidden="true">
                  {member.initials}
                </span>
                <div className="team-card__body">
                  <p className="eyebrow">{member.role}</p>
                  <h3>{member.name}</h3>
                  <p>{member.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="contrast-section" id="surfaces" aria-label="Platform surfaces" data-reveal>
          <div className="contrast-panel contrast-panel--light">
            <div className="section-label">
              <span>7A.</span>
              <span>Consumer App</span>
            </div>
            <p className="surface-copy">
              Ranked signals, confidence scores, and the reasoning behind each
              trade — so a retail user can read the call before taking it.
            </p>
          </div>

          <div className="contrast-panel contrast-panel--dark">
            <div className="section-label">
              <span>7B.</span>
              <span>Trading API</span>
            </div>
            <p className="surface-copy">
              REST for strategy state, WebSocket for live signals. Paper
              accounts by default; live routing is opt-in with a per-account
              kill switch.
            </p>
          </div>

          <div className="contrast-panel contrast-panel--icon">
            <div className="section-label">
              <span>7C.</span>
              <span>Telemetry</span>
            </div>
            <div className="app-icon" aria-hidden="true">
              <LogoMark size="tiny" inverted />
            </div>
          </div>
        </section>

        <section className="contact-section" id="contact" aria-labelledby="contact-title" data-reveal>
          <div className="contact-section__copy">
            <p className="eyebrow">Private Beta</p>
            <h2 id="contact-title">Ready to see the signal.</h2>
            <p>
              We are onboarding a small group of traders and developers onto
              paper accounts first. If you want a seat — or an API key for the
              execution layer — start the conversation here.
            </p>
            <p className="contact-section__fineprint">
              Astraios is a technology platform. Nothing on this site is
              investment advice, and access to the live execution layer is
              gated behind paper trading and broker onboarding.
            </p>
          </div>

          <a className="primary-action primary-action--large" href="mailto:hello@astraios.tech">
            Request access
            <span aria-hidden="true">→</span>
          </a>
        </section>
      </main>

      <Footer />
    </div>
  );
}

function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="site-footer">
      <div className="site-footer__brand">
        <LogoMark size="tiny" />
        <Wordmark />
      </div>

      <div className="site-footer__columns">
        <div>
          <p className="footer-label">Access</p>
          <a href="mailto:hello@astraios.tech">hello@astraios.tech</a>
        </div>
        <div>
          <p className="footer-label">Elsewhere</p>
          <a href="https://github.com/astraios-dev" rel="noreferrer noopener">GitHub</a>
        </div>
        <div>
          <p className="footer-label">Status</p>
          <span>Private beta · {year}</span>
        </div>
      </div>

      <p className="site-footer__meta">
        © {year} Astraios. Technology platform · not investment advice.
      </p>
    </footer>
  );
}

function Wordmark() {
  return <span className="wordmark" role="img" aria-label="Astraios wordmark" />;
}

function LogoMark({ inverted = false, size = "medium" }) {
  return (
    <span
      className={`logo-mark logo-mark--${size}${inverted ? " logo-mark--inverted" : ""}`}
      role="img"
      aria-label="Astraios A mark"
    />
  );
}

function useScrollReveal() {
  const observer = useRef(null);

  useEffect(() => {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const targets = document.querySelectorAll("[data-reveal]");

    if (prefersReduced || typeof IntersectionObserver === "undefined") {
      targets.forEach((el) => el.classList.add("is-revealed"));
      return undefined;
    }

    observer.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-revealed");
            observer.current.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
    );

    targets.forEach((el) => observer.current.observe(el));
    return () => observer.current?.disconnect();
  }, []);
}

export default App;
