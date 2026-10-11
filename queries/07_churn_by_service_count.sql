-- Business question: Are customers who hold more services (more engaged) less
-- likely to churn? This informs the engagement axis of the segmentation.

SELECT
    n_services                                     AS category,
    n_services                                     AS sort_order,
    COUNT(*)                                       AS customers,
    COUNT(*) * 1.0 / SUM(COUNT(*)) OVER ()         AS share_of_customers,
    SUM(churned)                                   AS churned,
    AVG(churned)                                   AS churn_rate,
    AVG(monthly_charges)                           AS avg_monthly_charge
FROM customer_profile
GROUP BY n_services
ORDER BY n_services;
