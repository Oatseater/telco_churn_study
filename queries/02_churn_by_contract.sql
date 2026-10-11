-- Business question: Does contract length change how likely a customer is to
-- leave, and where is the lost revenue concentrated?

WITH base AS (
    SELECT
        contract AS category,
        churned,
        monthly_charges,
        CASE WHEN churned = 1 THEN monthly_charges ELSE 0 END AS churned_charges
    FROM customers
)
SELECT
    category,
    CASE category WHEN 'Month-to-month' THEN 1 WHEN 'One year' THEN 2 ELSE 3 END AS sort_order,
    COUNT(*)                                       AS customers,
    COUNT(*) * 1.0 / SUM(COUNT(*)) OVER ()         AS share_of_customers,
    SUM(churned)                                   AS churned,
    AVG(churned)                                   AS churn_rate,
    AVG(monthly_charges)                           AS avg_monthly_charge,
    SUM(churned_charges) * 12                      AS annual_revenue_at_risk,
    SUM(churned_charges) * 1.0 / SUM(SUM(churned_charges)) OVER () AS share_of_revenue_at_risk
FROM base
GROUP BY category
ORDER BY sort_order;
