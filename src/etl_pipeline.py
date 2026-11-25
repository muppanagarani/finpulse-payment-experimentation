import hashlib
import io
import logging
import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

RAW_DATA_PATH = Path("data/raw_paysim.csv")

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "finpulse_db")


def assign_experiment_group(user_ids: pd.Series) -> pd.Series:
    """Deterministically assign users 50/50 into Control vs Treatment using MD5 hashing."""
    def _hash_user(uid: str) -> str:
        digest = hashlib.md5(uid.encode("utf-8")).hexdigest()
        return "Treatment" if int(digest[:8], 16) % 2 == 0 else "Control"

    return user_ids.map(_hash_user)


def fast_pg_copy(df: pd.DataFrame, table_name: str, engine) -> None:
    """Bulk-load large DataFrames into PostgreSQL using native COPY FROM STDIN."""
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cursor:
            buffer = io.StringIO()
            df.to_csv(buffer, index=False, header=False)
            buffer.seek(0)
            cols = ", ".join(df.columns)
            cursor.copy_expert(f"COPY {table_name} ({cols}) FROM STDIN WITH CSV", buffer)
        raw_conn.commit()
    finally:
        raw_conn.close()


def run_etl() -> None:
    if not DB_PASSWORD:
        raise ValueError("DB_PASSWORD not found! Please check your .env file.")
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Missing {RAW_DATA_PATH}. Please place the Kaggle CSV inside data/raw_paysim.csv."
        )

    logging.info("Step 1/5: Loading raw PaySim transaction logs...")
    df = pd.read_csv(RAW_DATA_PATH)
    logging.info(f"Loaded {len(df):,} raw rows.")

    required_cols = {
        "step", "type", "amount", "nameOrig", "oldbalanceOrg",
        "newbalanceOrig", "nameDest", "isFraud", "isFlaggedFraud"
    }
    assert required_cols.issubset(df.columns), "Schema validation failed: missing columns!"
    assert df["nameOrig"].isna().sum() == 0, "Null user IDs detected!"
    assert (df["amount"] >= 0).all(), "Negative transaction amounts detected!"

    logging.info("Step 2/5: Mapping hourly steps to real timestamps...")
    base_time = pd.Timestamp("2026-01-01 00:00:00")
    df["event_timestamp"] = base_time + pd.to_timedelta(df["step"], unit="h")

    logging.info("Step 3/5: Building dim_users with deterministic A/B test assignment...")
    dim_users = (
        df.sort_values("event_timestamp")
        .groupby("nameOrig", as_index=False)
        .agg(
            first_seen_at=("event_timestamp", "min"),
            initial_balance=("oldbalanceOrg", "first"),
        )
        .rename(columns={"nameOrig": "user_id"})
    )
    dim_users["experiment_group"] = assign_experiment_group(dim_users["user_id"])
    dim_users = dim_users[["user_id", "experiment_group", "first_seen_at", "initial_balance"]]

    treatment_share = (dim_users["experiment_group"] == "Treatment").mean()
    logging.info(f"A/B Split Check -> Treatment Share: {treatment_share:.4%}")
    assert 0.495 <= treatment_share <= 0.505, "Sample Ratio Mismatch (SRM) detected!"

    logging.info("Step 4/5: Deriving product funnel statuses & Treatment conversion lift...")
    df = df.merge(dim_users[["user_id", "experiment_group"]], left_on="nameOrig", right_on="user_id", how="left")

    conditions = [
        df["isFlaggedFraud"] == 1,
        (df["amount"] > df["oldbalanceOrg"]) & (df["oldbalanceOrg"] > 0),
        (df["oldbalanceOrg"] == 0) & (df["amount"] > 0),
    ]
    choices = ["Blocked_Fraud", "Failed_Insufficient_Funds", "Dropped_At_Auth"]
    df["txn_status"] = np.select(conditions, choices, default="Settled")

    rng = np.random.default_rng(seed=42)
    recoverable_mask = (
        (df["experiment_group"] == "Treatment")
        & (df["txn_status"] == "Dropped_At_Auth")
        & (df["isFraud"] == 0)
    )
    lift_roll = rng.random(recoverable_mask.sum()) < 0.085
    df.loc[recoverable_mask, "txn_status"] = np.where(lift_roll, "Settled", "Dropped_At_Auth")

    fact_transactions = df[[
        "nameOrig", "nameDest", "event_timestamp", "type", "amount",
        "oldbalanceOrg", "newbalanceOrig", "txn_status", "isFraud", "isFlaggedFraud"
    ]].rename(columns={
        "nameOrig": "user_id",
        "nameDest": "recipient_id",
        "type": "txn_type",
        "oldbalanceOrg": "old_balance_orig",
        "newbalanceOrig": "new_balance_orig",
        "isFraud": "is_fraud",
        "isFlaggedFraud": "is_flagged_fraud",
    })
    fact_transactions["is_fraud"] = fact_transactions["is_fraud"].fillna(0).astype(int)
    fact_transactions["is_flagged_fraud"] = fact_transactions["is_flagged_fraud"].fillna(0).astype(int)
    fact_transactions["recipient_id"] = fact_transactions["recipient_id"].fillna("UNKNOWN")
    fact_transactions["old_balance_orig"] = fact_transactions["old_balance_orig"].fillna(0.0)
    fact_transactions["new_balance_orig"] = fact_transactions["new_balance_orig"].fillna(0.0)

    logging.info("Step 5/5: Creating Star Schema & bulk-loading into PostgreSQL (finpulse_db)...")
    encoded_password = quote_plus(DB_PASSWORD)
    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    schema_sql = Path("sql/01_schema.sql").read_text()
    with engine.begin() as conn:
        conn.execute(text(schema_sql))

    logging.info("Bulk loading dim_users...")
    fast_pg_copy(dim_users, "dim_users", engine)

    logging.info("Bulk loading fact_transactions (6.36M rows)...")
    fast_pg_copy(fact_transactions, "fact_transactions", engine)

    logging.info("ETL Pipeline completed successfully! Star Schema populated in PostgreSQL.")


if __name__ == "__main__":
    run_etl()