-- Business question: Of every 100 customers who join, how many are still with us
-- after N months? (Survival-style retention by tenure month.)
--
-- Method: Kaplan-Meier product-limit estimate. Each row is treated as one
-- customer's history: churners left at their recorded tenure; active customers
-- are censored (still with us) at their tenure.
--   at_risk(t)   = customers whose tenure is at least t
--   churned(t)   = customers who churned at tenure exactly t
--   retention(t) = retention(t-1) * (1 - churned(t) / at_risk(t))
-- The recursive CTE chains the monthly survival probabilities.

WITH RECURSIVE
months(t) AS (
    SELECT 1
    UNION ALL
    SELECT t + 1 FROM months WHERE t < (SELECT MAX(tenure_months) FROM customers)
),
life_table AS (
    SELECT
        m.t                                                                  AS tenure_month,
        SUM(CASE WHEN c.tenure_months >= m.t THEN 1 ELSE 0 END)              AS at_risk,
        SUM(CASE WHEN c.tenure_months  = m.t AND c.churned = 1 THEN 1 ELSE 0 END) AS churned
    FROM months AS m
    CROSS JOIN customers AS c
    GROUP BY m.t
),
survival(tenure_month, at_risk, churned, retention) AS (
    SELECT 0, (SELECT COUNT(*) FROM customers), 0, 1.0
    UNION ALL
    SELECT
        l.tenure_month,
        l.at_risk,
        l.churned,
        s.retention * (1.0 - CASE WHEN l.at_risk > 0 THEN l.churned * 1.0 / l.at_risk ELSE 0 END)
    FROM survival AS s
    JOIN life_table AS l ON l.tenure_month = s.tenure_month + 1
)
SELECT
    tenure_month,
    at_risk,
    churned,
    CASE WHEN at_risk > 0 THEN churned * 1.0 / at_risk END AS monthly_churn_hazard,
    retention
FROM survival
ORDER BY tenure_month;
