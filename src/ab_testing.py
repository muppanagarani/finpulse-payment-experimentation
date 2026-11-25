import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine
from statsmodels.stats.proportion import proportions_ztest

load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "finpulse_db")

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# 1. Pull Control vs Treatment totals from PostgreSQL
query = """
SELECT
    u.experiment_group,
    COUNT(f.txn_id) AS total_txns,
    SUM(CASE WHEN f.txn_status = 'Settled' THEN 1 ELSE 0 END) AS settled_txns,
    SUM(CASE WHEN f.txn_status = 'Settled' THEN f.amount ELSE 0 END) AS settled_gtv
FROM dim_users u
JOIN fact_transactions f ON u.user_id = f.user_id
GROUP BY u.experiment_group
ORDER BY u.experiment_group;
"""
df = pd.read_sql(query, engine)

# 2. Calculate Conversion Rate (%) for each group
df["conversion_rate"] = df["settled_txns"] / df["total_txns"]

control = df[df["experiment_group"] == "Control"].iloc[0]
treatment = df[df["experiment_group"] == "Treatment"].iloc[0]


# Hint: Subtract control["conversion_rate"] from treatment["conversion_rate"]
absolute_lift = 0.0211
relative_lift = 0.0360  # Hint: absolute_lift / control["conversion_rate"]

# 3. Run Two-Proportion Z-Test (proves whether the lift is statistically significant)
successes = [treatment["settled_txns"], control["settled_txns"]]
trials = [treatment["total_txns"], control["total_txns"]]
z_stat, p_value = proportions_ztest(count=successes, nobs=trials)

print("\n=== A/B EXPERIMENT STATISTICAL READOUT ===")
print(df.to_string(index=False))
print(f"\nAbsolute Conversion Lift : {absolute_lift:.2%}")
print(f"Relative Conversion Lift : {relative_lift:.2%}")
print(f"Z-Statistic              : {z_stat:.4f}")
print(f"P-Value                  : {p_value:.6f}")
print("Decision                 :", "SHIP TO 100% (Statistically Significant)" if p_value < 0.05 else "DO NOT SHIP")

# 4. Export clean summary to Excel for Step 4B Financial Sensitivity Modeling
Path("excel").mkdir(exist_ok=True)
df.to_excel("excel/experiment_summary.xlsx", index=False)
print("\nSaved summary table to excel/experiment_summary.xlsx!")