-- Business question: What share of customers churned, and how much recurring
-- revenue left with them?
--
-- Revenue at risk is defined as the monthly charges of churned customers,
-- annualised (x 12). Assumption: each churned customer would otherwise have kept
-- paying the same monthly charge for a year.

WITH base AS (
    SELECT
        churned,
        monthly_charges,
        CASE WHEN churned = 1 THEN monthly_charges ELSE 0 END AS churned_charges
    FROM customers
)
SELECT
    COUNT(*)                         AS customers,
    SUM(churned)                     AS churned,
    AVG(churned)                     AS churn_rate,
    SUM(monthly_charges)             AS monthly_revenue,
    AVG(monthly_charges)             AS avg_monthly_charge,
    SUM(churned_charges)             AS churned_monthly_revenue,
    SUM(churned_charges) * 12        AS annual_revenue_at_risk,
    SUM(churned_charges) / SUM(monthly_charges) AS share_of_revenue_churned
FROM base;
