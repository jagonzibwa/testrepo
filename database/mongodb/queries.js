// =============================================================================
// MongoDB queries on metro_traffic.traffic_readings
// Run in mongosh:   mongosh "mongodb://localhost:27017/metro_traffic" database/mongodb/queries.js
// The same queries are run from Python (with saved output) by database/run_queries.py
// =============================================================================
const coll = db.getSiblingDB("metro_traffic").traffic_readings;
const show = (title, result) => { print(`\n=== ${title} ===`); printjson(result); };

// M1 - Latest reading (time-series "latest record")
show("M1 Latest reading",
  coll.find({}, { _id: 0, timestamp: 1, traffic_volume: 1, "weather.conditions": 1, holiday: 1 })
      .sort({ timestamp: -1 }).limit(1).toArray());

// M2 - Records in a date range: Monday 24 Sep 2018, 06:00-10:00
show("M2 Date range 2018-09-24 06:00 to 10:00",
  coll.find({ timestamp: { $gte: ISODate("2018-09-24T06:00:00Z"), $lte: ISODate("2018-09-24T10:00:00Z") } },
            { _id: 0, timestamp: 1, traffic_volume: 1, "weather.temp_k": 1, "weather.conditions.main": 1 })
      .sort({ timestamp: 1 }).toArray());

// M3 - Weekday rush-hour volume by weather condition ($unwind the embedded array)
show("M3 Weekday rush-hour volume by weather condition",
  coll.aggregate([
    { $match: { "calendar.is_weekend": false, "calendar.hour": { $in: [7, 8, 16, 17] }, holiday: null } },
    { $set: { primary: { $first: "$weather.conditions" } } },
    { $group: { _id: "$primary.main", rush_hours: { $sum: 1 }, avg_volume: { $avg: "$traffic_volume" } } },
    { $match: { rush_hours: { $gte: 30 } } },
    { $project: { _id: 0, weather_main: "$_id", rush_hours: 1, avg_volume: { $round: ["$avg_volume", 0] } } },
    { $sort: { avg_volume: -1 } }
  ]).toArray());

// M4 - Daily totals with a 7-day moving average ($setWindowFields), December 2016
show("M4 Daily totals + 7-day moving average (Dec 2016)",
  coll.aggregate([
    { $match: { timestamp: { $gte: ISODate("2016-11-24T00:00:00Z"), $lt: ISODate("2017-01-01T00:00:00Z") } } },
    { $group: { _id: { $dateTrunc: { date: "$timestamp", unit: "day" } },
                day_volume: { $sum: "$traffic_volume" }, hours: { $sum: 1 } } },
    { $setWindowFields: { sortBy: { _id: 1 }, output: {
        ma_7day: { $avg: "$day_volume", window: { documents: [-6, 0] } },
        prev_day: { $shift: { output: "$day_volume", by: -1 } } } } },
    { $project: { _id: 0, day: { $dateToString: { date: "$_id", format: "%Y-%m-%d" } }, hours: 1, day_volume: 1,
                  ma_7day: { $round: ["$ma_7day", 0] },
                  change_vs_prev_day: { $subtract: ["$day_volume", "$prev_day"] } } },
    { $sort: { day: -1 } },
    { $limit: 14 }
  ]).toArray());

// M5 - Average hourly volume and peak per holiday
show("M5 Holiday traffic summary",
  coll.aggregate([
    { $match: { holiday: { $type: "string" } } },
    { $group: { _id: "$holiday", hours: { $sum: 1 }, avg_volume: { $avg: "$traffic_volume" },
                peak_volume: { $max: "$traffic_volume" } } },
    { $project: { _id: 0, holiday: "$_id", hours: 1, peak_volume: 1, avg_volume: { $round: ["$avg_volume", 0] } } },
    { $sort: { avg_volume: 1 } }
  ]).toArray());
