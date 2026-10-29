-- =============================================================================
-- Metro Interstate Traffic Volume - relational schema (MySQL 8.x)
-- =============================================================================
-- Design
--   traffic_observations  1 row per hour (the time-series fact table)
--   weather_conditions    lookup of the 38 distinct (main, description) pairs
--   observation_weather   junction table: an hour can report several weather
--                         conditions (this is why the raw CSV has duplicate
--                         timestamps), so hour <-> condition is many-to-many
--   holidays              one row per holiday date; every hour on that date
--                         points to it (holiday is a property of the day)
--
-- Raw measurements are stored exactly as published (including the invalid
-- 0 K temperatures). Cleaning happens in the Python pipeline
-- (src/preprocessing.py), so the database stays the untouched source of truth.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS metro_traffic
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE metro_traffic;

DROP VIEW  IF EXISTS v_hourly_traffic;
DROP TABLE IF EXISTS observation_weather;
DROP TABLE IF EXISTS traffic_observations;
DROP TABLE IF EXISTS weather_conditions;
DROP TABLE IF EXISTS holidays;

-- -----------------------------------------------------------------------------
-- holidays
-- -----------------------------------------------------------------------------
CREATE TABLE holidays (
    holiday_id     SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    holiday_date   DATE              NOT NULL,
    holiday_name   VARCHAR(64)       NOT NULL,
    PRIMARY KEY (holiday_id),
    UNIQUE KEY uq_holiday_date (holiday_date)
) ENGINE = InnoDB COMMENT = 'US national and regional holidays (one row per date)';

-- -----------------------------------------------------------------------------
-- weather_conditions (lookup)
-- -----------------------------------------------------------------------------
CREATE TABLE weather_conditions (
    condition_id         SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    weather_main         VARCHAR(32)       NOT NULL COMMENT 'e.g. Rain, Snow, Clouds',
    weather_description  VARCHAR(64)       COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT 'e.g. light rain (case-sensitive: source has "Sky is Clear" and "sky is clear")',
    PRIMARY KEY (condition_id),
    UNIQUE KEY uq_condition (weather_main, weather_description)
) ENGINE = InnoDB COMMENT = 'Distinct weather categories reported by OpenWeatherMap';

-- -----------------------------------------------------------------------------
-- traffic_observations (time-series fact table)
-- -----------------------------------------------------------------------------
CREATE TABLE traffic_observations (
    observation_id   INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    date_time        DATETIME          NOT NULL COMMENT 'Local hour (America/Chicago)',
    traffic_volume   INT UNSIGNED      NOT NULL COMMENT 'Westbound vehicles in the hour (target)',
    temp             DECIMAL(6,2)      NULL     COMMENT 'Average temperature, Kelvin',
    rain_1h          DECIMAL(7,2)      NOT NULL DEFAULT 0 COMMENT 'Rain in the hour, mm',
    snow_1h          DECIMAL(5,2)      NOT NULL DEFAULT 0 COMMENT 'Snow in the hour, mm',
    clouds_all       TINYINT UNSIGNED  NOT NULL COMMENT 'Cloud cover, %',
    holiday_id       SMALLINT UNSIGNED NULL,
    created_at       TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (observation_id),
    UNIQUE KEY uq_observation_time (date_time),          -- one row per hour + fast range scans
    KEY idx_observation_holiday (holiday_id),
    CONSTRAINT fk_observation_holiday FOREIGN KEY (holiday_id)
        REFERENCES holidays (holiday_id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT chk_clouds CHECK (clouds_all BETWEEN 0 AND 100),
    CONSTRAINT chk_precip CHECK (rain_1h >= 0 AND snow_1h >= 0)
) ENGINE = InnoDB COMMENT = 'Hourly traffic volume and weather measurements, I-94 ATR 301';

-- -----------------------------------------------------------------------------
-- observation_weather (junction: many conditions per hour)
-- -----------------------------------------------------------------------------
CREATE TABLE observation_weather (
    observation_id   INT UNSIGNED      NOT NULL,
    condition_id     SMALLINT UNSIGNED NOT NULL,
    condition_rank   TINYINT UNSIGNED  NOT NULL DEFAULT 1 COMMENT 'Order reported in the source (1 = first)',
    PRIMARY KEY (observation_id, condition_id),
    KEY idx_ow_condition (condition_id),
    CONSTRAINT fk_ow_observation FOREIGN KEY (observation_id)
        REFERENCES traffic_observations (observation_id) ON DELETE CASCADE,
    CONSTRAINT fk_ow_condition FOREIGN KEY (condition_id)
        REFERENCES weather_conditions (condition_id) ON DELETE RESTRICT
) ENGINE = InnoDB COMMENT = 'Weather conditions reported for each hourly observation';

-- -----------------------------------------------------------------------------
-- Convenience view: one denormalised row per hour (used by the API)
-- -----------------------------------------------------------------------------
CREATE VIEW v_hourly_traffic AS
SELECT  o.observation_id,
        o.date_time,
        o.traffic_volume,
        o.temp,
        o.rain_1h,
        o.snow_1h,
        o.clouds_all,
        h.holiday_name                                                  AS holiday,
        GROUP_CONCAT(wc.weather_main ORDER BY ow.condition_rank SEPARATOR '|')        AS weather_main,
        GROUP_CONCAT(wc.weather_description ORDER BY ow.condition_rank SEPARATOR '|') AS weather_description
FROM    traffic_observations o
LEFT JOIN holidays            h  ON h.holiday_id      = o.holiday_id
LEFT JOIN observation_weather ow ON ow.observation_id = o.observation_id
LEFT JOIN weather_conditions  wc ON wc.condition_id   = ow.condition_id
GROUP BY o.observation_id, o.date_time, o.traffic_volume, o.temp, o.rain_1h,
         o.snow_1h, o.clouds_all, h.holiday_name;
