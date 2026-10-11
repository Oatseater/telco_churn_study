-- Business question: Which customer segments are largest, which churn most, and
-- where is the most revenue at risk?
--
-- Segments are defined in src/schema.sql (view customer_profile) from three
-- RFM-style axes: loyalty (tenure), value (monthly charge) and engagement
-- (number of services held).

WITH seg AS (
    SELECT
        segment,
        churned,
        monthly_charges,
        tenure_months,
        n_services,
        CASE WHEN churned = 1 THEN monthly_charges ELSE 0 END AS churned_charges
    FROM customer_profile
)
SELECT
    segment,
    CASE segment
        WHEN 'New High-Spend'          THEN 1
        WHEN 'New Standard'            THEN 2
        WHEN 'Established Thin Bundle' THEN 3
        WHEN 'Established Full Bundle' THEN 4
        ELSE 5
    END                                                       AS sort_order,
    COUNT(*)                                                  AS customers,
    COUNT(*) * 1.0 / SUM(COUNT(*)) OVER ()                    AS share_of_customers,
    SUM(churned)                                              AS churned,
    AVG(churned)                                              AS churn_rate,
    AVG(tenure_months)                                        AS avg_tenure_months,
    AVG(n_services)                                           AS avg_services,
    AVG(monthly_charges)                                      AS avg_monthly_charge,
    AVG(CASE WHEN churned = 1 THEN monthly_charges END)       AS avg_monthly_charge_churned,
    AVG(CASE WHEN churned = 0 THEN monthly_charges END)       AS avg_monthly_charge_retained,
    SUM(monthly_charges)                                      AS monthly_revenue,
    SUM(monthly_charges) * 1.0 / SUM(SUM(monthly_charges)) OVER () AS share_of_revenue,
    SUM(churned_charges) * 12                                 AS annual_revenue_at_risk,
    SUM(churned_charges) * 1.0 / SUM(SUM(churned_charges)) OVER () AS share_of_revenue_at_risk
FROM seg
GROUP BY segment
ORDER BY sort_order;
