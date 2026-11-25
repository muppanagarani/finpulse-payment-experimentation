-- ============================================================================
-- FinPulse Payment Funnel & Experimentation Analytics Queries
-- ============================================================================

-- Query 1: Payment Funnel Conversion & Drop-Off by Transaction Type
SELECT
    txn_type,
    COUNT(*) AS total_txns,
    SUM(CASE WHEN txn_status = 'Settled' THEN 1 ELSE 0 END) AS settled_txns,
    SUM(CASE WHEN txn_status = 'Dropped_At_Auth' THEN 1 ELSE 0 END) AS dropped_auth_txns,
    ROUND(
        SUM(CASE WHEN txn_status = 'Settled' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS settlement_rate_pct,
    ROUND(
        SUM(CASE WHEN txn_status = 'Settled' THEN amount ELSE 0 END),
        2
    ) AS settled_gtv
FROM fact_transactions
GROUP BY txn_type
ORDER BY total_txns DESC;


-- Query 2: A/B Experiment Readout (Control vs. Treatment Performance)
SELECT
    u.experiment_group,
    COUNT(DISTINCT u.user_id) AS total_users,
    COUNT(f.txn_id) AS total_txns,
    SUM(CASE WHEN f.txn_status = 'Settled' THEN 1 ELSE 0 END) AS settled_txns,
    ROUND(
        SUM(CASE WHEN f.txn_status = 'Settled' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS settlement_rate_pct,
    ROUND(
        SUM(CASE WHEN f.txn_status = 'Settled' THEN f.amount ELSE 0 END),
        2
    ) AS settled_gtv
FROM dim_users AS u
JOIN fact_transactions AS f
    ON u.user_id = f.user_id
GROUP BY u.experiment_group;


-- Query 3: Ticket-Size Bracket Drop-Off & Fraud Velocity Analysis
WITH amount_brackets AS (
    SELECT
        CASE
            WHEN amount < 10000 THEN '1. Micro (< 10K)'
            WHEN amount BETWEEN 10000 AND 100000 THEN '2. Mid-Tier (10K - 100K)'
            WHEN amount BETWEEN 100000.01 AND 500000 THEN '3. High-Value (100K - 500K)'
            ELSE '4. Enterprise (> 500K)'
        END AS amount_tier,
        txn_status,
        is_fraud,
        amount
    FROM fact_transactions
)
SELECT
    amount_tier,
    COUNT(*) AS total_txns,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total_volume,
    SUM(CASE WHEN txn_status = 'Settled' THEN 1 ELSE 0 END) AS settled_txns,
    ROUND(
        SUM(CASE WHEN txn_status = 'Settled' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS settlement_rate_pct,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS fraud_txns
FROM amount_brackets
GROUP BY amount_tier
ORDER BY amount_tier;


-- Query 4: Customer Spending Tiers (RFM Monetary Quartiles via NTILE)
WITH user_spend AS (
    SELECT
        user_id,
        SUM(amount) AS total_spend,
        NTILE(4) OVER (ORDER BY SUM(amount) DESC) AS spend_tier
    FROM fact_transactions
    WHERE txn_status = 'Settled'
    GROUP BY user_id
)
SELECT
    spend_tier,
    COUNT(*) AS user_count,
    ROUND(MIN(total_spend), 2) AS min_spend,
    ROUND(AVG(total_spend), 2) AS avg_spend,
    ROUND(MAX(total_spend), 2) AS max_spend
FROM user_spend
GROUP BY spend_tier
ORDER BY spend_tier;