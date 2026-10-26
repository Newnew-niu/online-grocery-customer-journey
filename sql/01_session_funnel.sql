-- Module 2: session-level funnel table from the GA4 public sample.
--
-- Data: bigquery-public-data.ga4_obfuscated_sample_ecommerce
--       Google Merchandise Store (a real online shop that sells Google-branded
--       products, NOT a grocery store), 1 Nov 2020 - 31 Jan 2021.
--       Google obfuscated the data, so some values show as '<Other>' or '(data deleted)'.
--
-- Output: one row per session (user_pseudo_id + ga_session_id) with
--   - a 0/1 flag for each funnel step
--   - device, first-touch traffic source/medium, new vs returning
--   - purchase revenue (USD)
--
-- Cost control: only the columns we need, and an explicit date range.

WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')     AS ga_session_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_number') AS ga_session_number,
    event_name,
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    device.category        AS device_category,
    traffic_source.medium  AS first_medium,   -- how the USER was first acquired
    traffic_source.source  AS first_source,
    ecommerce.purchase_revenue_in_usd AS purchase_revenue_usd
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
)

SELECT
  user_pseudo_id,
  ga_session_id,
  MIN(event_date)              AS session_date,
  ANY_VALUE(device_category)   AS device_category,
  ANY_VALUE(first_medium)      AS first_medium,
  ANY_VALUE(first_source)      AS first_source,
  MIN(ga_session_number)       AS session_number,      -- 1 = the user's first session
  MAX(IF(event_name = 'view_item',        1, 0)) AS view_item,
  MAX(IF(event_name = 'add_to_cart',      1, 0)) AS add_to_cart,
  MAX(IF(event_name = 'begin_checkout',   1, 0)) AS begin_checkout,
  MAX(IF(event_name = 'add_payment_info', 1, 0)) AS add_payment_info,
  MAX(IF(event_name = 'purchase',         1, 0)) AS purchase,
  COUNTIF(event_name = 'purchase')               AS purchase_events,
  SUM(IF(event_name = 'purchase', purchase_revenue_usd, 0)) AS revenue_usd
FROM events
WHERE ga_session_id IS NOT NULL
GROUP BY user_pseudo_id, ga_session_id
