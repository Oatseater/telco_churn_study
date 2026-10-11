-- Business question: How differently do month-to-month, one-year and two-year
-- customers survive over time?
--
-- Same Kaplan-Meier method as 08_retention_curve_overall.sql, computed
-- separately within each contract type.

WITH RECURSIVE
months(t) AS (
    SELECT 1
    UNION ALL
    SELECT t + 1 FROM months WHERE t < (SELECT MAX(tenure_months) FROM customers)
),
contracts AS (
    SELECT contract, COUNT(*) AS customers FROM customers GROUP BY contract
),
life_table AS (
    SELECT
        c.contract,
        m.t                                                                  AS tenure_month,
        SUM(CASE WHEN c.tenure_months >= m.t THEN 1 ELSE 0 END)              AS at_risk,
        SUM(CASE WHEN c.tenure_months  = m.t AND c.churned = 1 THEN 1 ELSE 0 END) AS churned
    FROM months AS m
    CROSS JOIN customers AS c
    GROUP BY c.contract, m.t
),
survival(contract, tenure_month, at_risk, churned, retention) AS (
    SELECT contract, 0, customers, 0, 1.0 FROM contracts
    UNION ALL
    SELECT
        s.contract,
        l.tenure_month,
        l.at_risk,
        l.churned,
        s.retention * (1.0 - CASE WHEN l.at_risk > 0 THEN l.churned * 1.0 / l.at_risk ELSE 0 END)
    FROM survival AS s
    JOIN life_table AS l
      ON l.contract = s.contract
     AND l.tenure_month = s.tenure_month + 1
)
SELECT
    contract,
    tenure_month,
    at_risk,
    churned,
    CASE WHEN at_risk > 0 THEN churned * 1.0 / at_risk END AS monthly_churn_hazard,
    retention
FROM survival
ORDER BY contract, tenure_month;
