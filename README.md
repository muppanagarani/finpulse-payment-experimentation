# FinPulse: Payment Funnel Diagnostics & A/B Experimentation Engine

An end-to-end product analytics and experimentation pipeline built on FinTech payment transaction logs (**PaySim**) to diagnose checkout drop-offs, evaluate a **One-Click Checkout A/B experiment**, and model annualized revenue impact.

---

## Key Findings & Business Recommendations
* **Baseline Funnel Diagnostics:** Across **1,824 payment attempts** (₹6.39 Cr Settled GTV), overall payment settlement rate is **59.65%**, with primary drop-offs occurring at authorization (`Dropped_At_Auth`) and insufficient funds (`Failed_Insufficient_Funds`).
* **A/B Experiment Readout (Control vs. Treatment):**
  * **Control (Legacy Checkout):** `58.58%` conversion (`529 / 903` settled; ₹2.69 Cr GTV)
  * **Treatment (One-Click Checkout):** `60.69%` conversion (`559 / 921` settled; ₹3.71 Cr GTV)
  * **Observed Lift:** **+2.11% absolute lift** (**+3.60% relative improvement**)
* **Statistical Power & Rollout Decision:** A Two-Proportion Z-test (`StatsModels`) yielded `Z = 0.9194` and `p = 0.3579`. Because `n = 1,824` is currently underpowered to confirm significance at $\alpha = 0.05$, I recommended **extending the experiment to ~14,000 attempts** to reach 80% statistical power before rolling out to 100% of users.
* **Projected Financial Impact:** At a `1.20%` MDR take rate, scaling the observed `+2.11%` lift projects **~₹20.54 Cr in annualized net revenue gain**.

---

## Architecture & Tech Stack
* **Database & Data Modeling (`PostgreSQL`):** Normalized raw logs into a Star Schema (`dim_users` and `fact_transactions` with B-tree indexes) via `sql/01_schema.sql`.
* **ETL & Experiment Assignment (`Python`, `Pandas`, `SQLAlchemy`):** Automated schema validation, timestamp mapping, deterministic 50/50 user bucketing (MD5 hashing + Sample Ratio Mismatch check), and bulk PostgreSQL ingestion (`src/etl_pipeline.py`).
* **Product & Risk SQL Analytics (`PostgreSQL`):** Built queries using CTEs, conditional aggregation, `NTILE(4)` spend quartiles, and ticket-size drop-off segmentation (`sql/02_analytics.sql`).
* **Statistical Hypothesis Testing & Financial Modeling (`SciPy`, `StatsModels`, `Excel`):** Two-Proportion Z-test (`src/ab_testing.py`) paired with a 3-scenario sensitivity model (`excel/revenue_impact_model.xlsx`).
* **Executive BI Reporting (`Power BI`):** Direct PostgreSQL import with custom DAX measures across 3 interactive pages (`dashboard/finpulse_executive_dashboard.pbix`).

---

## Dashboard Previews

### 1. Executive Funnel & GTV Overview
![Funnel & GTV Overview](dashboard/screenshots/page1_funnel.png)

### 2. A/B Experiment Readout (Control vs. Treatment)
![A/B Experiment Readout](dashboard/screenshots/page2_ab_test.png)

### 3. Risk & Drop-Off Diagnostics
![Risk & Drop-Off Diagnostics](dashboard/screenshots/page3_risk.png)
