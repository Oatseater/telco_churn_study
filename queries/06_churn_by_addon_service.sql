-- Business question: Among internet customers, do those who buy each add-on
-- service churn less than those who do not?
--
-- Restricted to internet customers: "No internet service" customers cannot buy
-- add-ons, so including them would mix "chose not to buy" with "could not buy".
-- This is association, not proof that the add-on causes retention.

WITH internet_customers AS (
    SELECT * FROM customers WHERE internet_service <> 'No'
),
long_format AS (
    SELECT 'Online security'   AS addon, online_security   AS has_addon, churned FROM internet_customers
    UNION ALL
    SELECT 'Online backup',              online_backup,                  churned FROM internet_customers
    UNION ALL
    SELECT 'Device protection',          device_protection,              churned FROM internet_customers
    UNION ALL
    SELECT 'Tech support',               tech_support,                   churned FROM internet_customers
    UNION ALL
    SELECT 'Streaming TV',               streaming_tv,                   churned FROM internet_customers
    UNION ALL
    SELECT 'Streaming movies',           streaming_movies,               churned FROM internet_customers
)
SELECT
    addon                                                          AS category,
    SUM(CASE WHEN has_addon = 'Yes' THEN 1 ELSE 0 END)             AS customers_with,
    AVG(CASE WHEN has_addon = 'Yes' THEN churned END)              AS churn_rate_with,
    SUM(CASE WHEN has_addon = 'No'  THEN 1 ELSE 0 END)             AS customers_without,
    AVG(CASE WHEN has_addon = 'No'  THEN churned END)              AS churn_rate_without,
    AVG(CASE WHEN has_addon = 'No'  THEN churned END)
      - AVG(CASE WHEN has_addon = 'Yes' THEN churned END)          AS churn_gap
FROM long_format
GROUP BY addon
ORDER BY churn_gap DESC;
