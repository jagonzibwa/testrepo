-- =============================================================================
-- Analytical queries on the relational schema (MySQL 8.x)
-- Run all of them and save the results with:  python database/run_queries.py
-- Each query starts with a "-- name:" line that the runner uses as its title.
-- =============================================================================
USE metro_traffic;

-- name: Q1 Latest 5 hourly observations with weather conditions and holiday
SELECT  o.date_time,
        o.traffic_volume,
        ROUND(o.temp - 273.15, 1)                                               AS temp_c,
        o.clouds_all,
        GROUP_CONCAT(wc.weather_description ORDER BY ow.condition_rank SEPARATOR ', ') AS conditions,
        COALESCE(h.holiday_name, '-')                                           AS holiday
FROM    traffic_observations o
JOIN    observation_weather ow ON ow.observation_id = o.observation_id
JOIN    weather_conditions  wc ON wc.condition_id   = ow.condition_id
LEFT JOIN holidays          h  ON h.holiday_id      = o.holiday_id
GROUP BY o.observation_id, o.date_time, o.traffic_volume, o.temp, o.clouds_all, h.holiday_name
ORDER BY o.date_time DESC
LIMIT 5;

-- name: Q2 Average traffic by hour of day, weekday vs weekend (commuter peaks)
SELECT  HOUR(date_time)                                                         AS hour_of_day,
        ROUND(AVG(CASE WHEN DAYOFWEEK(date_time) BETWEEN 2 AND 6 THEN traffic_volume END)) AS weekday_avg,
        ROUND(AVG(CASE WHEN DAYOFWEEK(date_time) IN (1, 7)      THEN traffic_volume END)) AS weekend_avg
FROM    traffic_observations
GROUP BY HOUR(date_time)
ORDER BY hour_of_day;

-- name: Q3 Monthly summary for 2017 (date-range filter + aggregation)
SELECT  DATE_FORMAT(date_time, '%Y-%m')         AS month,
        COUNT(*)                                AS hours_observed,
        ROUND(AVG(traffic_volume))              AS avg_volume,
        MAX(traffic_volume)                     AS peak_volume,
        ROUND(AVG(temp) - 273.15, 1)            AS avg_temp_c,
        ROUND(SUM(rain_1h), 1)                  AS total_rain_mm
FROM    traffic_observations
WHERE   date_time >= '2017-01-01' AND date_time < '2018-01-01'
GROUP BY DATE_FORMAT(date_time, '%Y-%m')
ORDER BY month;

-- name: Q4 Holiday effect - average daily volume per holiday vs the average non-holiday day
-- Only complete days (24 observed hours) are compared.
WITH daily AS (
    SELECT  DATE(o.date_time)        AS day,
            SUM(o.traffic_volume)    AS day_volume,
            MAX(h.holiday_name)      AS holiday_name
    FROM    traffic_observations o
    LEFT JOIN holidays h ON h.holiday_id = o.holiday_id
    GROUP BY DATE(o.date_time)
    HAVING  COUNT(*) = 24
)
SELECT  holiday_name,
        COUNT(*)                     AS complete_days,
        ROUND(AVG(day_volume))       AS avg_daily_volume,
        ROUND(100 * (AVG(day_volume)
              / (SELECT AVG(day_volume) FROM daily WHERE holiday_name IS NULL) - 1), 1) AS pct_vs_normal_day
FROM    daily
WHERE   holiday_name IS NOT NULL
GROUP BY holiday_name
ORDER BY pct_vs_normal_day;

-- name: Q5 Daily totals with 7-day moving average and day-over-day change (window functions, Dec 2016)
WITH daily AS (
    SELECT DATE(date_time) AS day, SUM(traffic_volume) AS day_volume, COUNT(*) AS hours
    FROM   traffic_observations
    WHERE  date_time >= '2016-11-24' AND date_time < '2017-01-01'
    GROUP BY DATE(date_time)
)
SELECT  day,
        hours,
        day_volume,
        ROUND(AVG(day_volume) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)) AS ma_7day,
        day_volume - LAG(day_volume, 1) OVER (ORDER BY day)                                AS change_vs_prev_day,
        day_volume - LAG(day_volume, 7) OVER (ORDER BY day)                                AS change_vs_last_week
FROM    daily
ORDER BY day DESC
LIMIT 14;

-- name: Q6 Weekday rush-hour traffic by weather condition (junction-table join)
SELECT  wc.weather_main,
        COUNT(DISTINCT o.observation_id)  AS rush_hours,
        ROUND(AVG(o.traffic_volume))      AS avg_volume
FROM    traffic_observations o
JOIN    observation_weather ow ON ow.observation_id = o.observation_id AND ow.condition_rank = 1
JOIN    weather_conditions  wc ON wc.condition_id   = ow.condition_id
WHERE   HOUR(o.date_time) IN (7, 8, 16, 17)
  AND   DAYOFWEEK(o.date_time) BETWEEN 2 AND 6
  AND   o.holiday_id IS NULL
GROUP BY wc.weather_main
HAVING  COUNT(*) >= 30
ORDER BY avg_volume DESC;
