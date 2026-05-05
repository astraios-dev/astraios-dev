# Agentic Engineering Grant Application
**Grant:** Superteam Earn — Agentic Engineering (200 USDG)
**Submit:** https://superteam.fun/earn/grants/agentic-engineering

---

## Step 1: Basics

**Project Title**
> Astraios — Quantitative ML Trading Platform

**One Line Description**
> A full-stack quant trading platform combining a multi-timeframe CNN-Transformer (68% accuracy, Sharpe +5.70) with autonomous execution on both Bybit (CEX) and Drift Protocol (Solana on-chain perps).

**TG username**
> t.me/astraios0x

**Wallet Address**
> AtxsFfyCqjnkcNxLqMeDX3Btcmo9pvENL9SC2vxDtTq7

---

## Step 2: Details

**Project Details**
> Astraios is a full-stack quantitative trading platform for cryptocurrency derivatives. The core problem: retail traders lack access to institutional-grade signal generation and autonomous execution infrastructure. Most retail tools offer lagging indicators and manual workflows — Astraios closes that gap with a production ML pipeline and a live autonomous trading engine that operates 24/7 without human intervention.
>
> The signal engine is MarketTransformer v6 — a CNN-Transformer architecture trained across 3 timeframes simultaneously (15m momentum, 1h trend, 4h regime), 28 features per timeframe (84 total), across 27 USDT perpetual symbols with 3 years of Binance futures history. The model achieves 68% directional accuracy and Sharpe +5.70 in out-of-sample backtesting with proper TP/SL simulation and fees. Training runs on AWS SageMaker ml.g5.12xlarge (4× NVIDIA A10G). Validation uses per-symbol walk-forward cross-validation with 24-bar embargo gaps to prevent label leakage.
>
> The auto-trader executes signals autonomously every 15 minutes on two venues: Bybit (CEX) with demo/live mode toggle, and Drift Protocol (Solana on-chain perps) with a browser wallet adapter (Phantom/Solflare) for identity plus an encrypted server-side trading keypair for autonomous execution. Risk controls include per-user confidence thresholds (≥65%), TP=3%/SL=1.5% (2:1 R:R), max positions, position sizing, and daily loss limits.
>
> The full platform was built with Claude Code as the primary agentic development tool — from ML architecture design, to SageMaker training pipeline, to FastAPI backend, to React dashboard, to Drift Protocol integration — across a focused sprint with full session transcripts as proof.

**Deadline**
> August 31, 2026 (IST)

**Proof of Work**
> - **GitHub**: https://github.com/astraios-dev/astraios-dev (public, 20+ commits Apr 26–May 5 2026)
> - **Whitepaper v2**: `docs/astraios-whitepaper.pdf` — 16 sections, full architecture, backtest results
> - **ML pipeline**: MarketTransformer v6 — 84-feature MTF CNN-Transformer, 68% val acc, Sharpe +5.70, SageMaker g5.12xlarge
> - **Auto-trader**: Autonomous execution on Bybit (demo/live) and Drift Protocol (Solana on-chain)
> - **Drift integration**: `api/services/solana_trader.py` — driftpy, 16 perp markets, Phantom wallet adapter
> - **Solana wallet adapter**: `@solana/wallet-adapter-react` + `WalletMultiButton` with Phantom/Solflare
> - **AI session transcripts**: `grant-application/claude-session.jsonl` (6.2 MB) + `grant-application/codex-session.jsonl` (64 KB)
> - **Crowdedness score**: 323 — cluster "Solana DEX and Trading Infrastructure", highest similarity 0.053 (Butter Trade)

**Personal X Profile**
> x.com/astraiosone

**Personal GitHub Profile**
> github.com/astraios-dev

**Where have you worked or built before?**
> Data Science Trainee at AlmaBetter (Jan 2026–present), building production ML pipelines and deploying neural network architectures. Prior projects include FedEx logistics EDA (3.6M transactions), relational database design (15-entity Zomato schema), and Tableau dashboard pipelines. B.Tech in Electronics & Instrumentation Engineering from OUTR (CGPA 7.74). Astraios is my first independent product — built end-to-end using Claude Code as the primary agentic engineering tool.

**Why are you the right person to build this?**
> ML and data science background with hands-on experience in PyTorch, FastAPI, PostgreSQL, and end-to-end model deployment — the exact stack powering Astraios. My EIE degree gave me a strong signals and systems foundation that directly applies to time-series ML. Currently deepening LLM and production ML knowledge at AlmaBetter. Astraios is the convergence of everything I've been training toward.

**What are you building, and who is it for?**
> Astraios is a quantitative trading platform for retail crypto traders who want institutional-grade signal generation and autonomous execution without the complexity of building it themselves. The platform runs a multi-timeframe CNN-Transformer that predicts price direction across 27 perpetual pairs at 68% accuracy, then automatically executes trades on Bybit and Drift Protocol every 15 minutes — no manual intervention required.

**Why did you decide to build this, and why now?**
> Crypto derivatives markets are the most liquid, 24/7 tradeable assets in the world — but the tools available to retail traders are years behind what institutional desks use. Quant funds run transformer models, multi-timeframe ensembles, and automated execution. Retail traders get RSI and manual entry. The gap is real and the technology to close it now exists. The timing is right because Solana's DeFi infrastructure finally has the speed and liquidity for on-chain perps to be viable for algo trading.

**What technologies are you using?**
> PyTorch CNN-Transformer on SageMaker, FastAPI + PostgreSQL backend, Bybit v5 API for CEX execution, driftpy + Drift Protocol for Solana on-chain perps, React 19 frontend, built end-to-end with Claude Code.

**Colosseum Crowdedness Score**
> 323 — cluster "Solana DEX and Trading Infrastructure" (323 projects, 23 winners). Highest similarity to existing projects is 0.053 (Butter Trade). No existing project combines a trained Transformer model with Drift Protocol auto-trading.

**AI Session Transcript**
> `grant-application/claude-session.jsonl` (6.2 MB) — Claude Code full session
> `grant-application/codex-session.jsonl` (64 KB) — Codex session

---

## Step 3: Milestones

**Goals and Milestones**
> **M1 — Regime-Conditional Model v7 (June 15, 2026)**
> Two-stage architecture: regime classifier (trending/ranging/high-vol) + regime-specific heads. Target: 70%+ val accuracy.
>
> **M2 — Limit Orders + Trailing Stop (June 30, 2026)**
> Replace market orders with smart limit placement at bid/ask. Trailing stop moves SL to breakeven after 1% profit.
>
> **M3 — WebSocket Real-Time Signal Engine (July 20, 2026)**
> Replace 15-min polling with Bybit WebSocket — re-evaluates on every 1h candle close. Signal latency <1 s.
>
> **M4 — Order Book Features + Model v8 (August 10, 2026)**
> 6 order book features (bid-ask imbalance, depth-weighted mid, large order presence). Target: 72%+ val accuracy.
>
> **M5 — Public Beta + Performance Dashboard (August 31, 2026)**
> Public beta with onboarding + live performance dashboard (signal accuracy, cumulative P&L, win rate).

**Primary KPI**
> Autonomous trade win rate ≥ 55% on live Bybit Demo and/or Drift Protocol (measured over 50+ closed trades)

**Final Tranche**
> Submit: Colosseum project link · GitHub repo · AI subscription receipt
