-- Business question: What contracts and internet products sit inside each
-- segment? This shapes which retention action fits each one.

WITH seg AS (
    SELECT segment, contract, internet_service, churned FROM customer_profile
),
totals AS (
    SELECT segment, COUNT(*) AS segment_customers FROM seg GROUP BY segment
)
SELECT
    s.segment,
    s.contract,
    COUNT(*)                                             AS customers,
    COUNT(*) * 1.0 / t.segment_customers                 AS share_of_segment,
    AVG(s.churned)                                       AS churn_rate,
    AVG(CASE WHEN s.internet_service = 'Fiber optic' THEN 1.0 ELSE 0.0 END) AS share_fiber
FROM seg AS s
JOIN totals AS t ON t.segment = s.segment
GROUP BY s.segment, s.contract, t.segment_customers
ORDER BY s.segment, s.contract;
