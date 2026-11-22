-- Drop tables if re-running setup
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS dim_users;

-- 1. Dimension Table: Users & Experiment Assignment
CREATE TABLE dim_users (
    user_id VARCHAR(50) PRIMARY KEY,
    experiment_group VARCHAR(20) NOT NULL CHECK (experiment_group IN ('Control', 'Treatment')),
    first_seen_at TIMESTAMP NOT NULL,
    initial_balance NUMERIC(15, 2) NOT NULL
);

-- 2. Fact Table: Payment & Transaction Events
CREATE TABLE fact_transactions (
    txn_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL REFERENCES dim_users(user_id),
    recipient_id VARCHAR(50) NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    txn_type VARCHAR(20) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    old_balance_orig NUMERIC(15, 2) NOT NULL,
    new_balance_orig NUMERIC(15, 2) NOT NULL,
    txn_status VARCHAR(30) NOT NULL,
    is_fraud SMALLINT NOT NULL,
    is_flagged_fraud SMALLINT NOT NULL
);

-- 3. Performance Indexes for Analytics & Power BI Queries
CREATE INDEX idx_fact_timestamp ON fact_transactions(event_timestamp);
CREATE INDEX idx_fact_user_id ON fact_transactions(user_id);
CREATE INDEX idx_fact_status ON fact_transactions(txn_status);
CREATE INDEX idx_dim_exp_group ON dim_users(experiment_group);