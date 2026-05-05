# Amyanshu Jenamani
**Machine Learning · Data Science · Deep Learning · NLP · LLMs**

Bhubaneswar, Odisha, India · amyanshu@astraios.tech · [linkedin.com/in/amyanshu-jenamani](https://linkedin.com/in/amyanshu-jenamani) · [astraios.tech](https://astraios.tech)

---

## Professional Summary

Machine learning engineer and builder with a B.Tech in Electronics and Instrumentation Engineering, specializing in deep learning, time-series ML, and production AI systems. Built Astraios — a full-stack quantitative trading platform with a multi-timeframe CNN-Transformer achieving 68% directional accuracy and Sharpe +5.70 — using Claude Code as the primary agentic engineering tool. Experienced in end-to-end ML pipelines, Solana DeFi integration (Drift Protocol), and deploying real-money automated trading systems. Open to roles at the intersection of ML systems, DeFi infrastructure, and agentic engineering.

---

## Technical Skills

| Domain | Skills |
|---|---|
| **ML & Deep Learning** | PyTorch, CNN-Transformer architectures, time-series forecasting, walk-forward CV, focal loss, SageMaker |
| **Data Science** | EDA, statistical analysis, hypothesis testing, feature engineering, scikit-learn, Pandas, NumPy |
| **Backend** | FastAPI, PostgreSQL, asyncpg, SQLAlchemy, Alembic, REST APIs, Fernet encryption, JWT auth |
| **Solana / DeFi** | driftpy, Drift Protocol perps, @solana/wallet-adapter-react, Phantom/Solflare integration |
| **Frontend** | React 19, Vite, lightweight-charts, pure CSS |
| **MLOps & Infra** | AWS SageMaker (g5.12xlarge), S3, boto3, Git, GitHub |
| **Agentic Dev** | Claude Code (Anthropic) — full platform built via AI-assisted engineering |
| **Visualization** | Tableau, Power BI, Matplotlib, Seaborn |

---

## Projects

### Astraios — Quantitative ML Trading Platform
*Ongoing · [astraios.tech](https://astraios.tech) · [github.com/astraios-dev/astraios-dev](https://github.com/astraios-dev/astraios-dev)*

Full-stack quant trading platform built end-to-end with Claude Code in a 2-week agentic sprint.

- **MarketTransformer v6**: CNN-Transformer trained on 3 timeframes (15m/1h/4h), 84 features, 27 USDT perp symbols, 3 years of Binance futures history — 68% directional accuracy, Sharpe +5.70, CV mean 62.6% ± 0.4%
- **Training pipeline**: AWS SageMaker ml.g5.12xlarge (4× NVIDIA A10G), per-symbol walk-forward CV, 24-bar embargo, cost-sensitive focal loss, return-quantile labels (top/bottom 30%)
- **Auto-trader**: Autonomous execution every 15 min on Bybit (CEX, demo/live) and Drift Protocol (Solana on-chain perps via driftpy) with per-user risk controls (confidence gate, TP/SL, position sizing)
- **Drift DEX layer**: driftpy integration across 16 perp markets, Phantom/Solflare wallet adapter, server-side Fernet-encrypted trading keypair
- **Backend**: FastAPI + asyncpg + PostgreSQL, JWT auth, rate limiting, Fernet key encryption at rest
- **Frontend**: React 19 + Vite + lightweight-charts, 1s live position polling, dark editorial design
- **Evaluation**: TP/SL backtest (24-bar horizon, fee-adjusted), ECE calibration, per-symbol Sharpe breakdown

---

### FedEx Logistics Performance Analysis
*2026 · AlmaBetter Capstone · Python, Pandas, NumPy, Matplotlib, Seaborn*

- Analyzed 3.6M international shipment transactions across 80+ countries and 15 commodity categories
- End-to-end data cleaning: missing-value imputation, currency normalization, outlier treatment on freight cost and gross weight
- Hypothesis testing (t-tests, chi-square) to validate delivery cost and route efficiency patterns
- Delivered structured report with 5 actionable findings on cost outliers, seasonal volume, and country-level mix

---

### Product Dissection — Relational Database Design
*2026 · AlmaBetter Capstone · SQL, PostgreSQL, dbdiagram.io, ER Modelling*

- Reverse-engineered a Zomato-style food-ordering app into a normalized relational schema of 15+ entities
- Modelled to 3NF with primary/foreign keys, composite keys on junction tables, indexed for query performance
- Wrote analytical SQL (window functions, CTEs, 5+ table joins) for product questions: top restaurants, repeat-order cohorts, delivery SLA breaches

---

### Transforming EDAs to Dashboards
*2026 · AlmaBetter Capstone · Tableau, Power BI, SQL, Excel*

- Translated notebook EDA into a multi-page interactive Tableau dashboard with cross-filtered views for executive, operational, and drill-down audiences
- Designed KPI cards, trend charts, and geospatial maps against a star-schema data model
- Applied visualization best practices: consistent color encoding, minimal chart junk, accessibility contrast

---

## Experience

**Data Science Trainee** — AlmaBetter *(January 2026 – Present)*
- Building production ML pipelines covering data preprocessing, feature engineering, model training, optimization, and deployment
- Deep learning and NLP with emphasis on LLM internals and research-to-production workflows
- End-to-end ML systems with scalability and evaluation discipline

---

## Education

**B.Tech, Electronics and Instrumentation Engineering**
Odisha University of Technology and Research (OUTR) · Sep 2019 – Jun 2025 · CGPA: 7.74 / 10

**Class 12 (PCMB)**
DAV Public School, Chandrasekharpur · 2018 · 80.4%

**Class 10**
Montfort School, Dhenkanal · 93%

---

## Links

- **Project**: [astraios.tech](https://astraios.tech)
- **GitHub**: [github.com/astraios-dev](https://github.com/astraios-dev)
- **LinkedIn**: [linkedin.com/in/amyanshu-jenamani](https://linkedin.com/in/amyanshu-jenamani)
- **X**: [x.com/astraiosone](https://x.com/astraiosone)
- **Email**: amyanshu@astraios.tech
