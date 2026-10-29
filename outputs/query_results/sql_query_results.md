# SQL query results (MySQL)

_Generated 2026-10-26 14:56 by `database/run_queries.py` from `database/sql/queries.sql`._

## Q1 Latest 5 hourly observations with weather conditions and holiday

```sql
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
```

**Result (5 rows):**

| date_time           |   traffic_volume |   temp_c |   clouds_all | conditions             | holiday   |
|:--------------------|-----------------:|---------:|-------------:|:-----------------------|:----------|
| 2018-09-30 23:00:00 |              954 |      9   |           90 | overcast clouds        | -         |
| 2018-09-30 22:00:00 |             1450 |      8.9 |           90 | overcast clouds        | -         |
| 2018-09-30 21:00:00 |             2159 |      9.6 |           90 | proximity thunderstorm | -         |
| 2018-09-30 20:00:00 |             2781 |      9.6 |           90 | overcast clouds        | -         |
| 2018-09-30 19:00:00 |             3543 |     10.3 |           75 | broken clouds          | -         |


## Q2 Average traffic by hour of day, weekday vs weekend (commuter peaks)

```sql
SELECT  HOUR(date_time)                                                         AS hour_of_day,
        ROUND(AVG(CASE WHEN DAYOFWEEK(date_time) BETWEEN 2 AND 6 THEN traffic_volume END)) AS weekday_avg,
        ROUND(AVG(CASE WHEN DAYOFWEEK(date_time) IN (1, 7)      THEN traffic_volume END)) AS weekend_avg
FROM    traffic_observations
GROUP BY HOUR(date_time)
ORDER BY hour_of_day;
```

**Result (24 rows):**

|   hour_of_day |   weekday_avg |   weekend_avg |
|--------------:|--------------:|--------------:|
|             0 |           655 |          1323 |
|             1 |           400 |           818 |
|             2 |           303 |           620 |
|             3 |           363 |           399 |
|             4 |           830 |           382 |
|             5 |          2699 |           643 |
|             6 |          5375 |          1103 |
|             7 |          6061 |          1600 |
|             8 |          5509 |          2354 |
|             9 |          4901 |          3133 |
|            10 |          4401 |          3718 |
|            11 |          4663 |          4082 |
|            12 |          4874 |          4403 |
|            13 |          4880 |          4408 |
|            14 |          5182 |          4393 |
|            15 |          5629 |          4372 |
|            16 |          6241 |          4375 |
|            17 |          5823 |          4186 |
|            18 |          4485 |          3853 |
|            19 |          3332 |          3258 |
|            20 |          2877 |          2851 |
|            21 |          2702 |          2693 |
|            22 |          2149 |          2411 |
|            23 |          1404 |          1708 |


## Q3 Monthly summary for 2017 (date-range filter + aggregation)

```sql
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
```

**Result (12 rows):**

| month   |   hours_observed |   avg_volume |   peak_volume |   avg_temp_c |   total_rain_mm |
|:--------|-----------------:|-------------:|--------------:|-------------:|----------------:|
| 2017-01 |              744 |         3120 |          6772 |         -6.5 |               0 |
| 2017-02 |              657 |         3389 |          7154 |         -1.4 |               0 |
| 2017-03 |              740 |         3505 |          7280 |          0.5 |               0 |
| 2017-04 |              711 |         3416 |          7065 |          9.3 |               0 |
| 2017-05 |              744 |         3411 |          7126 |         13.9 |               0 |
| 2017-06 |              720 |         3447 |          6747 |         20.6 |               0 |
| 2017-07 |              738 |         3299 |          6827 |         22.6 |               0 |
| 2017-08 |              743 |         3517 |          6997 |         19   |               0 |
| 2017-09 |              716 |         3456 |          7117 |         18.4 |               0 |
| 2017-10 |              744 |         3472 |          6985 |         10   |               0 |
| 2017-11 |              716 |         3368 |          6923 |          0.7 |               0 |
| 2017-12 |              740 |         3125 |          6757 |         -7.4 |               0 |


## Q4 Holiday effect - average daily volume per holiday vs the average non-holiday day

```sql
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
```

**Result (11 rows):**

| holiday_name              |   complete_days |   avg_daily_volume |   pct_vs_normal_day |
|:--------------------------|----------------:|-------------------:|--------------------:|
| New Years Day             |               3 |              43996 |               -44.7 |
| Christmas Day             |               3 |              45600 |               -42.7 |
| Thanksgiving Day          |               2 |              48329 |               -39.2 |
| Memorial Day              |               4 |              50323 |               -36.7 |
| Independence Day          |               5 |              51724 |               -35   |
| Labor Day                 |               4 |              55805 |               -29.8 |
| Martin Luther King Jr Day |               2 |              66414 |               -16.5 |
| Washingtons Birthday      |               4 |              66891 |               -15.9 |
| Veterans Day              |               3 |              80473 |                 1.2 |
| Columbus Day              |               2 |              83027 |                 4.4 |
| State Fair                |               4 |              91280 |                14.8 |


## Q5 Daily totals with 7-day moving average and day-over-day change (window functions, Dec 2016)

```sql
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
```

**Result (14 rows):**

| day        |   hours |   day_volume |   ma_7day |   change_vs_prev_day |   change_vs_last_week |
|:-----------|--------:|-------------:|----------:|---------------------:|----------------------:|
| 2016-12-31 |      24 |        64473 |     67419 |               -17261 |                 10658 |
| 2016-12-30 |      24 |        81734 |     65896 |                 -632 |                 11124 |
| 2016-12-29 |      24 |        82366 |     64307 |                 1344 |                 -2554 |
| 2016-12-28 |      24 |        81022 |     64672 |                 5404 |                 -4380 |
| 2016-12-27 |      24 |        75618 |     65297 |                23776 |                -12916 |
| 2016-12-26 |      24 |        51842 |     67143 |                16967 |                -26471 |
| 2016-12-25 |      24 |        34875 |     70924 |               -18940 |                 -5469 |
| 2016-12-24 |      24 |        53815 |     71705 |               -16795 |                  4356 |
| 2016-12-23 |      24 |        70610 |     71083 |               -14310 |                  9049 |
| 2016-12-22 |      24 |        84920 |     69790 |                 -482 |                 -2383 |
| 2016-12-21 |      24 |        85402 |     70131 |                -3132 |                  -964 |
| 2016-12-20 |      24 |        88534 |     70269 |                10221 |                  1191 |
| 2016-12-19 |      24 |        78313 |     70098 |                37969 |                  1563 |
| 2016-12-18 |      21 |        40344 |     69875 |                -9115 |                 -4078 |


## Q6 Weekday rush-hour traffic by weather condition (junction-table join)

```sql
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
```

**Result (9 rows):**

| weather_main   |   rush_hours |   avg_volume |
|:---------------|-------------:|-------------:|
| Fog            |           33 |         6132 |
| Drizzle        |           58 |         6107 |
| Thunderstorm   |           44 |         6068 |
| Clouds         |         1946 |         6059 |
| Clear          |         1200 |         6043 |
| Haze           |           67 |         6037 |
| Mist           |          416 |         6024 |
| Rain           |          580 |         5990 |
| Snow           |          246 |         5421 |

