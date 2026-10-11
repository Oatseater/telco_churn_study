-- Business question: How does churn change over the customer lifetime? Is the
-- first year the danger zone?

WITH bucketed AS (
    SELECT
        CASE
            WHEN tenure_months <= 6  THEN '0-6 months'
            WHEN tenure_months <= 12 THEN '7-12 months'
            WHEN tenure_months <= 24 THEN '13-24 months'
            WHEN tenure_months <= 48 THEN '25-48 months'
            ELSE                          '49-72 months'
        END AS category,
        CASE
            WHEN tenure_months <= 6  THEN 1
            WHEN tenure_months <= 12 THEN 2
            WHEN tenure_months <= 24 THEN 3
            WHEN tenure_months <= 48 THEN 4
            ELSE                          5
        END AS sort_order,
        churned,
        monthly_charges,
        CASE WHEN churned = 1 THEN monthly_charges ELSE 0 END AS churned_charges
    FROM customers
)
SELECT
    category,
    sort_order,
    COUNT(*)                                       AS customers,
    COUNT(*) * 1.0 / SUM(COUNT(*)) OVER ()         AS share_of_customers,
    SUM(churned)                                   AS churned,
    AVG(churned)                                   AS churn_rate,
    AVG(monthly_charges)                           AS avg_monthly_charge,
    SUM(churned_charges) * 12                      AS annual_revenue_at_risk,
    SUM(churned_charges) * 1.0 / SUM(SUM(churned_charges)) OVER () AS share_of_revenue_at_risk
FROM bucketed
GROUP BY category, sort_order
ORDER BY sort_order;
