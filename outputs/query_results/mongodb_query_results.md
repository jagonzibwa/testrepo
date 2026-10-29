# MongoDB query results

_Generated 2026-10-26 14:56 by `database/run_queries.py`. The same queries are in `database/mongodb/queries.js` for mongosh._

## M1 Latest reading (find + sort + limit)

```javascript
db.traffic_readings.find({}, {_id: 0, timestamp: 1, traffic_volume: 1, "weather.conditions": 1, holiday: 1})
  .sort({timestamp: -1}).limit(1)
```

**Result (1 documents):**

| timestamp           |   traffic_volume | holiday   | weather.conditions       |
|:--------------------|-----------------:|:----------|:-------------------------|
| 2018-09-30 23:00:00 |              954 |           | Clouds / overcast clouds |


## M2 Records in a date range (Mon 24 Sep 2018, 06:00-10:00)

```javascript
db.traffic_readings.find(
  {timestamp: {$gte: ISODate("2018-09-24T06:00:00Z"), $lte: ISODate("2018-09-24T10:00:00Z")}},
  {_id: 0, timestamp: 1, traffic_volume: 1, "weather.temp_k": 1, "weather.conditions.main": 1}
).sort({timestamp: 1})
```

**Result (5 documents):**

| timestamp           |   traffic_volume |   weather.temp_k | weather.conditions   |
|:--------------------|-----------------:|-----------------:|:---------------------|
| 2018-09-24 06:00:00 |             5747 |           287.33 | Thunderstorm         |
| 2018-09-24 07:00:00 |             6591 |           287.18 | Clouds               |
| 2018-09-24 08:00:00 |             5900 |           287.19 | Clouds               |
| 2018-09-24 09:00:00 |             4936 |           288.25 | Clear                |
| 2018-09-24 10:00:00 |             4351 |           290.03 | Clouds               |


## M3 Weekday rush-hour volume by primary weather condition (aggregation)

```javascript
db.traffic_readings.aggregate([
  {
    "$match": {
      "calendar.is_weekend": false,
      "calendar.hour": {
        "$in": [
          7,
          8,
          16,
          17
        ]
      },
      "holiday": null
    }
  },
  {
    "$set": {
      "primary": {
        "$first": "$weather.conditions"
      }
    }
  },
  {
    "$group": {
      "_id": "$primary.main",
      "rush_hours": {
        "$sum": 1
      },
      "avg_volume": {
        "$avg": "$traffic_volume"
      }
    }
  },
  {
    "$match": {
      "rush_hours": {
        "$gte": 30
      }
    }
  },
  {
    "$project": {
      "_id": 0,
      "weather_main": "$_id",
      "rush_hours": 1,
      "avg_volume": {
        "$round": [
          "$avg_volume",
          0
        ]
      }
    }
  },
  {
    "$sort": {
      "avg_volume": -1
    }
  }
])
```

**Result (9 documents):**

|   rush_hours | weather_main   |   avg_volume |
|-------------:|:---------------|-------------:|
|           33 | Fog            |         6132 |
|           58 | Drizzle        |         6107 |
|           44 | Thunderstorm   |         6068 |
|         1946 | Clouds         |         6059 |
|         1200 | Clear          |         6043 |
|           67 | Haze           |         6037 |
|          416 | Mist           |         6024 |
|          580 | Rain           |         5990 |
|          246 | Snow           |         5421 |


## M4 Daily totals with 7-day moving average, Dec 2016 ($setWindowFields)

```javascript
db.traffic_readings.aggregate([
  {
    "$match": {
      "timestamp": {
        "$gte": "ISODate(\"2016-11-24T00:00:00Z\")",
        "$lt": "ISODate(\"2017-01-01T00:00:00Z\")"
      }
    }
  },
  {
    "$group": {
      "_id": {
        "$dateTrunc": {
          "date": "$timestamp",
          "unit": "day"
        }
      },
      "day_volume": {
        "$sum": "$traffic_volume"
      },
      "hours": {
        "$sum": 1
      }
    }
  },
  {
    "$setWindowFields": {
      "sortBy": {
        "_id": 1
      },
      "output": {
        "ma_7day": {
          "$avg": "$day_volume",
          "window": {
            "documents": [
              -6,
              0
            ]
          }
        },
        "prev_day": {
          "$shift": {
            "output": "$day_volume",
            "by": -1
          }
        }
      }
    }
  },
  {
    "$project": {
      "_id": 0,
      "day": {
        "$dateToString": {
          "date": "$_id",
          "format": "%Y-%m-%d"
        }
      },
      "hours": 1,
      "day_volume": 1,
      "ma_7day": {
        "$round": [
          "$ma_7day",
          0
        ]
      },
      "change_vs_prev_day": {
        "$subtract": [
          "$day_volume",
          "$prev_day"
        ]
      }
    }
  },
  {
    "$sort": {
      "day": -1
    }
  },
  {
    "$limit": 14
  }
])
```

**Result (14 documents):**

|   day_volume |   hours | day        |   ma_7day |   change_vs_prev_day |
|-------------:|--------:|:-----------|----------:|---------------------:|
|        64473 |      24 | 2016-12-31 |     67419 |               -17261 |
|        81734 |      24 | 2016-12-30 |     65896 |                 -632 |
|        82366 |      24 | 2016-12-29 |     64307 |                 1344 |
|        81022 |      24 | 2016-12-28 |     64672 |                 5404 |
|        75618 |      24 | 2016-12-27 |     65297 |                23776 |
|        51842 |      24 | 2016-12-26 |     67143 |                16967 |
|        34875 |      24 | 2016-12-25 |     70924 |               -18940 |
|        53815 |      24 | 2016-12-24 |     71705 |               -16795 |
|        70610 |      24 | 2016-12-23 |     71083 |               -14310 |
|        84920 |      24 | 2016-12-22 |     69790 |                 -482 |
|        85402 |      24 | 2016-12-21 |     70131 |                -3132 |
|        88534 |      24 | 2016-12-20 |     70269 |                10221 |
|        78313 |      24 | 2016-12-19 |     70098 |                37969 |
|        40344 |      21 | 2016-12-18 |     69875 |                -9115 |


## M5 Holiday traffic summary (aggregation)

```javascript
db.traffic_readings.aggregate([
  {
    "$match": {
      "holiday": {
        "$type": "string"
      }
    }
  },
  {
    "$group": {
      "_id": "$holiday",
      "hours": {
        "$sum": 1
      },
      "avg_volume": {
        "$avg": "$traffic_volume"
      },
      "peak_volume": {
        "$max": "$traffic_volume"
      }
    }
  },
  {
    "$project": {
      "_id": 0,
      "holiday": "$_id",
      "hours": 1,
      "peak_volume": 1,
      "avg_volume": {
        "$round": [
          "$avg_volume",
          0
        ]
      }
    }
  },
  {
    "$sort": {
      "avg_volume": 1
    }
  }
])
```

**Result (11 documents):**

|   hours |   peak_volume | holiday                   |   avg_volume |
|--------:|--------------:|:--------------------------|-------------:|
|     113 |          3946 | Christmas Day             |         1764 |
|     112 |          3933 | New Years Day             |         1795 |
|     107 |          3649 | Thanksgiving Day          |         1996 |
|     117 |          4032 | Memorial Day              |         2096 |
|     120 |          4380 | Independence Day          |         2155 |
|     118 |          4660 | Labor Day                 |         2346 |
|      69 |          4852 | Martin Luther King Jr Day |         2732 |
|     115 |          5512 | Washingtons Birthday      |         2831 |
|     108 |          6494 | Veterans Day              |         3302 |
|     105 |          6676 | Columbus Day              |         3394 |
|     119 |          6823 | State Fair                |         3837 |

