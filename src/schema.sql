-- Derived view used by the analysis queries.
-- Segment rules live here, in one place. tests/test_data_integrity.py checks
-- that they match the thresholds documented in src/config.py.
--
-- Loyalty  (recency proxy): tenure_months
-- Value                   : monthly_charges
-- Engagement              : n_services, the number of services held out of 9
--                           (phone, multiple lines, internet, six add-ons)

DROP VIEW IF EXISTS customer_profile;

CREATE VIEW customer_profile AS
WITH flags AS (
    SELECT
        c.*,
        CASE WHEN phone_service     = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN multiple_lines    = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN internet_service <> 'No'  THEN 1 ELSE 0 END
      + CASE WHEN online_security   = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN online_backup     = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN device_protection = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN tech_support      = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN streaming_tv      = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN streaming_movies  = 'Yes' THEN 1 ELSE 0 END AS n_services,
        CASE WHEN online_security   = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN online_backup     = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN device_protection = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN tech_support      = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN streaming_tv      = 'Yes' THEN 1 ELSE 0 END
      + CASE WHEN streaming_movies  = 'Yes' THEN 1 ELSE 0 END AS n_addons
    FROM customers AS c
)
SELECT
    flags.*,
    CASE
        WHEN tenure_months <  12 AND monthly_charges >= 70                     THEN 'New High-Spend'
        WHEN tenure_months <  12                                               THEN 'New Standard'
        WHEN monthly_charges >= 70 AND n_services <  5                         THEN 'Established Thin Bundle'
        WHEN monthly_charges >= 70 AND n_services >= 5                         THEN 'Established Full Bundle'
        ELSE                                                                        'Established Low-Spend'
    END AS segment
FROM flags;
