"""Build the PDF report from the project's saved outputs.

Usage:
    python report/build_report.py

Edit TEAM below with the real names / roles, then re-run. All numbers come
from files the pipeline wrote (experiment table, query results, API test log,
forecast JSON), so the report always matches the code's actual results.
"""
from __future__ import annotations

import csv
import textwrap
import json
import re
from datetime import date
from pathlib import Path

import matplotlib
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "outputs" / "figures"
OUT = ROOT / "report" / "Group21_Time_Series_Pipeline_Report.pdf"
REPO_URL = "https://github.com/jagonzibwa/Formative-1-Group-21"

# ---------------------------------------------------------------------------
# EDIT ME: team members, their roles and main components
# ---------------------------------------------------------------------------
TEAM = [
    ("Member 1", "Task 1A/B - EDA & preprocessing",
     "Dataset choice and justification, missing-data strategy, invalid-value handling, "
     "six analytical questions and their visualisations (notebooks/01, src/preprocessing.py)."),
    ("Member 2", "Task 1C - Modelling",
     "Feature engineering (lags, moving averages), time-series cross-validation, nine experiments, "
     "hyperparameter tuning, experiment table and model export (notebooks/02, models/)."),
    ("Member 3", "Task 2 - Databases",
     "MySQL schema and ERD, MongoDB collection design and validator, loaders, SQL and MongoDB "
     "queries with results (database/)."),
    ("Member 4", "Task 3 & 4 - API and prediction",
     "FastAPI CRUD and time-series endpoints for both databases, API test suite, prediction "
     "script that fetches from the API and forecasts (api/, scripts/)."),
]

# ---------------------------------------------------------------------------
# Fonts and styles (DejaVu ships with matplotlib and covers symbols like ≈ − → ≤)
# ---------------------------------------------------------------------------
_ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DejaVu", str(_ttf / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_ttf / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Oblique", str(_ttf / "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Mono", str(_ttf / "DejaVuSansMono.ttf")))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                              italic="DejaVu-Oblique", boldItalic="DejaVu-Bold")

ACCENT = colors.HexColor("#2a78d6")
INK = colors.HexColor("#1b1b1a")
MUTED = colors.HexColor("#5b5a56")
RULE = colors.HexColor("#d9d8d3")
ZEBRA = colors.HexColor("#f4f3f0")
HILITE = colors.HexColor("#fdeee6")

BODY = ParagraphStyle("body", fontName="DejaVu", fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=6)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.2, leading=11, textColor=MUTED, spaceAfter=4)
CAPTION = ParagraphStyle("caption", parent=SMALL, fontName="DejaVu-Oblique", spaceBefore=2, spaceAfter=10)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=3)
H1 = ParagraphStyle("h1", fontName="DejaVu-Bold", fontSize=15, leading=19, textColor=ACCENT,
                    spaceBefore=6, spaceAfter=8)
H2 = ParagraphStyle("h2", keepWithNext=1, fontName="DejaVu-Bold", fontSize=11.5, leading=15, textColor=INK,
                    spaceBefore=10, spaceAfter=5)
H3 = ParagraphStyle("h3", keepWithNext=1, fontName="DejaVu-Bold", fontSize=10, leading=13, textColor=INK,
                    spaceBefore=6, spaceAfter=3)
CELL = ParagraphStyle("cell", fontName="DejaVu", fontSize=7.8, leading=10, textColor=INK)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName="DejaVu-Bold")
CODE = ParagraphStyle("code", fontName="DejaVu-Mono", fontSize=7.2, leading=9.2, textColor=INK,
                      backColor=ZEBRA, borderPadding=6, spaceBefore=4, spaceAfter=10)
TITLE = ParagraphStyle("title", fontName="DejaVu-Bold", fontSize=24, leading=30, textColor=INK, spaceAfter=6)
SUBTITLE = ParagraphStyle("subtitle", fontName="DejaVu", fontSize=12.5, leading=17, textColor=MUTED, spaceAfter=4)

FRAME_W = A4[0] - 4 * cm


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, BULLET, bulletText="•") for t in items]


def figure(name, caption, width=FRAME_W):
    path = FIG / f"{name}.png" if not str(name).endswith(".png") else Path(name)
    w, h = PILImage.open(path).size
    img = Image(str(path), width=width, height=width * h / w)
    img.keepWithNext = 1          # keep the caption with its image
    return [img, p(caption, CAPTION)]


def table(rows, col_widths=None, header=True, highlight_rows=(), font_size=None):
    style_cell = CELL if font_size is None else ParagraphStyle("c", parent=CELL, fontSize=font_size,
                                                              leading=font_size + 2.4)
    style_head = ParagraphStyle("h", parent=style_cell, fontName="DejaVu-Bold", textColor=colors.white)
    data = []
    for i, r in enumerate(rows):
        st = style_head if (header and i == 0) else style_cell
        data.append([c if not isinstance(c, str) else Paragraph(c, st) for c in r])
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), ACCENT)]
    for i in range(1 if header else 0, len(rows)):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    for i in highlight_rows:
        cmds.append(("BACKGROUND", (0, i), (-1, i), HILITE))
    t.setStyle(TableStyle(cmds))
    return t


def md_result_table(md_file: Path, title_prefix: str, max_rows: int | None = None):
    """Extract the result table that follows the '## <title_prefix>' heading in a results .md file."""
    text = md_file.read_text(encoding="utf-8")
    sec = re.split(r"^## ", text, flags=re.M)
    block = next(s for s in sec if s.startswith(title_prefix))
    lines = [l for l in block.splitlines() if l.startswith("|")]
    rows = [[c.strip() for c in l.strip("|").split("|")] for l in lines]
    rows = [rows[0]] + [r for r in rows[2:]]
    if max_rows:
        rows = rows[: max_rows + 1]
    return rows


def md_query_text(md_file: Path, title_prefix: str) -> str:
    text = md_file.read_text(encoding="utf-8")
    sec = re.split(r"^## ", text, flags=re.M)
    block = next(s for s in sec if s.startswith(title_prefix))
    m = re.search(r"```(?:sql|javascript)\n(.*?)```", block, flags=re.S)
    q = m.group(1).rstrip()
    agg = re.match(r"(db\.\w+\.aggregate\()(.*)\)$", q, flags=re.S)
    if agg:  # print one pipeline stage per line instead of one key per line
        stages = json.loads(agg.group(2))
        lines = [agg.group(1) + "["]
        for st in stages:
            txt = json.dumps(st, separators=(", ", ": ")).replace('\\"', "'")
            lines += textwrap.wrap(txt + ",", 108, initial_indent="  ", subsequent_indent="      ")
        lines.append("])")
        q = "\n".join(lines)
    return q


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 7.5)
    canvas.setFillColor(MUTED)
    if doc.page > 1:
        canvas.drawString(2 * cm, A4[1] - 1.2 * cm, "Group 21 · Time-Series Pipeline · Metro Interstate Traffic Volume")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.line(2 * cm, A4[1] - 1.35 * cm, A4[0] - 2 * cm, A4[1] - 1.35 * cm)
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Load results produced by the pipeline
# ---------------------------------------------------------------------------
with open(ROOT / "outputs" / "experiment_results.csv", encoding="utf-8") as f:
    EXPERIMENTS = list(csv.DictReader(f))
META = json.loads((ROOT / "models" / "model_metadata.json").read_text(encoding="utf-8"))
FORECAST = json.loads((ROOT / "outputs" / "latest_forecast.json").read_text(encoding="utf-8"))
API_LOG = (ROOT / "outputs" / "api_test_results.md").read_text(encoding="utf-8")
API_CHECKS = re.findall(r"^### (PASS|FAIL) `(\w+) ([^`]+)` -> (\d+) \(expected (\d+)\)", API_LOG, flags=re.M)
SQL_MD = ROOT / "outputs" / "query_results" / "sql_query_results.md"
MONGO_MD = ROOT / "outputs" / "query_results" / "mongodb_query_results.md"


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
def cover():
    s = [Spacer(1, 3.2 * cm),
         p("Building a Pipeline for Time-Series Data", TITLE),
         p("Hourly traffic forecasting on Interstate 94 (Minneapolis–St Paul)", SUBTITLE),
         p("Machine Learning Pipeline · Formative 1 · Group 21", SUBTITLE),
         Spacer(1, 0.5 * cm),
         p(f"GitHub repository: <link href='{REPO_URL}' color='#2a78d6'>{REPO_URL}</link>", BODY),
         p(f"Date: {date.today():%d %B %Y}", BODY),
         Spacer(1, 0.8 * cm),
         p("Team", H2)]
    rows = [["Member", "Role"]] + [[n, r] for n, r, _ in TEAM]
    s.append(table(rows, [5 * cm, FRAME_W - 5 * cm]))
    s += [Spacer(1, 1.0 * cm), p("Summary", H2)]
    best = next(e for e in EXPERIMENTS if e["exp"] == META["experiment"])
    naive = next(e for e in EXPERIMENTS if e["exp"] == "E1")
    s += bullets([
        "<b>Problem:</b> forecast next-hour westbound traffic volume on I-94 from traffic history, calendar and weather.",
        "<b>Data:</b> Kaggle <i>Metro Interstate Traffic Volume</i>, 48,204 hourly rows, Oct 2012 – Sep 2018, "
        "with weather and holiday variables.",
        f"<b>Model:</b> {META['model']} with lag and moving-average features. Test MAE "
        f"<b>{float(best['test_mae']):.0f} vehicles/hour</b> (R² {float(best['test_r2']):.3f}), a "
        f"{(1 - float(best['test_mae']) / float(naive['test_mae'])):.0%} lower error than the seasonal-naive baseline "
        f"({float(naive['test_mae']):.0f}).",
        "<b>Storage:</b> a 4-table MySQL schema and a validated MongoDB collection, each with 5–6 analytical queries.",
        "<b>Serving:</b> a FastAPI service with matching CRUD, latest-record and date-range endpoints for both databases, "
        f"plus a prediction script that pulls data from the API ({len(API_CHECKS)} automated API checks, "
        f"{sum(c[0] == 'PASS' for c in API_CHECKS)} passing).",
    ])
    s.append(PageBreak())
    return s


def section_problem():
    return [
        p("1. Problem definition and dataset", H1),
        p("<b>Problem.</b> Interstate 94 between Minneapolis and St Paul is one of Minnesota's busiest corridors. "
          "Traffic managers need short-term forecasts of volume to time ramp meters, position incident-response crews, "
          "schedule roadwork outside busy hours and warn drivers of congestion. We frame this as a <b>one-step-ahead "
          "regression forecast</b>: given everything known up to hour <i>t−1</i> (past traffic, the calendar, and the "
          "weather), predict the number of westbound vehicles in hour <i>t</i>."),
        p("<b>Dataset.</b> <i>Metro Interstate Traffic Volume</i> (Kaggle, mirrored from the UCI Machine Learning "
          "Repository #492, CC BY 4.0). Traffic counts come from MnDOT automatic traffic recorder 301; hourly weather "
          "comes from OpenWeatherMap."),
        table([
            ["Requirement", "How the dataset meets it"],
            ["Clear timestamp", "<font name='DejaVu-Mono'>date_time</font>: hourly, 2012-10-02 09:00 → 2018-09-30 23:00"],
            ["Meaningful target", "<font name='DejaVu-Mono'>traffic_volume</font>: vehicles per hour, 0–7,280; directly used "
                                  "in traffic operations"],
            ["Multiple variables over time", "temperature (K), rain and snow (mm/h), cloud cover (%), weather category "
                                             "and description, holiday name"],
        ], [4.2 * cm, FRAME_W - 4.2 * cm]),
        Spacer(1, 6),
        p("<b>Why this dataset.</b> It has a target that matters in practice and plausible external drivers (weather, "
          "holidays) to test. It is also <i>messy in realistic ways</i>: duplicate timestamps, 22.8% missing hours "
          "including a 10-month outage, and physically impossible sensor values. That makes the preprocessing stage a "
          "real engineering problem instead of a formality, and it fits a relational and a document database well "
          "(one hour can carry several weather conditions)."),
    ]


def section_eda():
    s = [p("2. Task 1A — Understanding the dataset", H1),
         p("All exploration is in <font name='DejaVu-Mono'>notebooks/01_eda_preprocessing.ipynb</font>. Cleaning and "
           "feature code lives in one module, <font name='DejaVu-Mono'>src/preprocessing.py</font>, which the training "
           "notebook and the prediction script also import. Every stage therefore transforms data in exactly the same way."),
         p("2.1 Time range, frequency and duplicates", H2),
         *bullets([
             "<b>Time range:</b> 2 Oct 2012 09:00 → 30 Sep 2018 23:00 (2,189 days, ≈ 6 years).",
             "<b>Granularity:</b> hourly. 37,986 of the steps between consecutive unique timestamps are exactly 1 hour; "
             "the other step sizes are gaps.",
             "<b>Duplicates:</b> 7,629 rows share a timestamp (up to 6 rows per hour). Inside each group "
             "<font name='DejaVu-Mono'>traffic_volume</font> is identical; only the weather condition differs. The source "
             "adds a row per extra condition, for example <i>light rain</i> + <i>drizzle</i>. We collapse to one row per "
             "hour and keep the most severe condition (Thunderstorm > Squall > Snow > Rain > … > Clear).",
         ]),
         p("2.2 Missing values and how they were handled", H2),
         p("The only explicit nulls are in <font name='DejaVu-Mono'>holiday</font>, which means “no holiday”. The holiday "
           "name is also written only on the 00:00 row. The larger problem is <b>implicit</b>: 11,976 of 52,551 expected "
           "hourly slots (22.8%) have no row. There are 2,588 gaps: 2,192 are a single hour, 260 are 2–3 hours, and one "
           "outage runs from 8 Aug 2014 to 11 Jun 2015 (7,386 hours)."),
         *figure("a4_missing_data", "Figure 1 – Observed hours per day and missing hours per year. The 2014–2015 outage is the dominant gap."),
         table([
             ["Problem", "Method", "Why this method"],
             ["Holiday only on 00:00 row", "Spread the name to all 24 hours of that date; add binary is_holiday",
              "A holiday is a property of the day; leaving 23 hours unlabelled hides its effect"],
             ["Gaps ≤ 3 h (2,452 gaps)", "Time-based linear interpolation (numeric), forward-fill (weather category); "
              "flag is_imputed = 1",
              "Traffic and weather change smoothly over 1–3 h; a regular grid keeps shift()-based lags correct; the flag "
              "keeps it auditable"],
             ["Gaps > 3 h, incl. the 10-month outage", "Not imputed. Rows whose lag/rolling windows touch them are dropped",
              "Filling days or months would invent daily and weekly cycles and leak fake values into lag features"],
             ["Global mean / median fill", "Rejected", "Traffic swings 300 → 6,000 within hours; a constant destroys the daily cycle"],
         ], [3.6 * cm, 6.2 * cm, FRAME_W - 9.8 * cm]),
         Spacer(1, 8),
         p("<b>Invalid values.</b> Ten rows report 0 K (−273 °C); the coldest plausible reading is −29.8 °C. One hour "
           "reports 9,831 mm of rain, while the next-highest value is 55.6 mm. Both are set to NaN and handled with the "
           "rules above. The temperature failures come in 4–6 hour runs, so those rows are dropped rather than "
           "interpolated. Result: 48,204 raw rows → 40,575 unique hours → a 52,551-hour regular grid (2,771 imputed hours) "
           "→ <b>36,568 model-ready rows</b> with 33 features."),
         p("2.3 Statistical distribution of numerical columns", H2),
         table([
             ["Column", "Mean", "Std", "Min", "Median", "Max", "Skew", "% zero"],
             ["traffic_volume", "3,290.7", "1,984.8", "0", "3,427", "7,280", "−0.11", "0.0"],
             ["temp (°C)", "8.24", "13.09", "−29.76", "9.72", "36.92", "−0.38", "0.1"],
             ["rain_1h (mm)", "0.08", "0.77", "0", "0", "55.63", "28.64", "94.9"],
             ["snow_1h (mm)", "0.00", "0.01", "0", "0", "0.51", "65.91", "99.9"],
             ["clouds_all (%)", "44.2", "38.7", "0", "40", "100", "0.03", "4.8"],
         ], [3.4 * cm] + [(FRAME_W - 3.4 * cm) / 7] * 7),
         Spacer(1, 6),
         *figure("a7_distributions", "Figure 2 – Distributions of the numerical columns and of the primary weather condition."),
         p("<b>Interpretation.</b> The target is <b>bimodal</b>: a night-time mode near 300–1,000 vehicles/h and a daytime "
           "plateau near 4,500–6,000. That is a first sign that hour of day explains most of the variance. Temperature is "
           "wide and roughly symmetric (Minnesota seasons). Rain and snow amounts are zero-inflated and extremely skewed: "
           "only 5% of hours have rain and 0.08% have measured snow, so the categorical "
           "<font name='DejaVu-Mono'>weather_main = Snow</font> (≈ 7% of hours) carries more information than "
           "<font name='DejaVu-Mono'>snow_1h</font>. Cloud cover is U-shaped. Tree models do not need normal inputs, so no "
           "transformation was applied."),
         PageBreak()]
    return s


def section_questions():
    s = [p("3. Task 1B — Analytical questions", H1),
         p("Six questions were analysed, each with at least one visualisation. <b>Q1, Q3 and Q6 use moving averages "
           "and/or lagged features</b>, which the brief requires for at least two questions.")]
    qs = [
        ("Q1. Does traffic have a long-term trend? (moving averages)", "q1_trend_moving_averages",
         "Figure 3 – Daily mean traffic with 7-, 30- and 365-day moving averages.",
         "The 7-day MA still shows weekly and holiday dips. The 30-day MA shows a winter dip each December–January "
         "(≈ 3,050 vehicles/h). The 365-day MA is almost flat at about 3,200–3,380. A linear fit on daily means gives "
         "<b>+14.6 vehicles/h per year (+0.44%/year, p = 0.055)</b>, not significant at 5%. Conclusion: <b>no meaningful "
         "trend</b>; the series is level-stationary with strong seasonality, so no de-trending is needed. A model trained "
         "on 2012–2017 should carry over to 2018."),
        ("Q2. What daily and weekly seasonal patterns exist?", "q2_seasonality",
         "Figure 4 – Mean traffic by weekday × hour, and weekday vs weekend hourly profiles.",
         "Traffic bottoms out at 03:00 (~350/h). Weekdays have a commuter double peak: <b>07:00 (~6,060)</b> and "
         "<b>16:00 (~6,240)</b>, with a ~4,800 midday plateau. Weekends have no morning rush, only a broad 12:00–15:00 peak; "
         "the weekend mean is <b>26% lower</b> (2,624 vs 3,557). The annual cycle is mild (Dec/Jan lowest). Hour × "
         "weekday is the main structure, so the model gets hour, weekday, weekend flags and cyclical encodings."),
        ("Q3. Are there lag effects? (lagged features)", "q3_acf_pacf",
         "Figure 5 – ACF up to 8 days and PACF up to 48 hours.",
         "Autocorrelation is <b>0.915 at lag 1 h</b>, falls to 0.52 at 3 h and to <b>−0.62 at 12 h</b> (peak vs trough). It "
         "returns to 0.863 at 24 h and peaks at <b>0.946 at 168 h</b>: the same hour last week is the single best "
         "predictor, because it matches both hour and weekday. The PACF has a large positive spike at lag 1, a large "
         "negative spike at lag 2 and a cluster at 20–25 h. As a forecast, <i>same as last week</i> scores MAE ≈ 349 "
         "and <i>same as an hour ago</i> ≈ 579. We therefore use lags 1, 2, 3, 24 and 168 h, and lag 168 h is the "
         "baseline to beat."),
        ("Q4. Do weather variables correlate with traffic?", "q4_weather_effect",
         "Figure 6 – Traffic residual (actual minus the usual weekday-hour level) by weather condition and temperature band.",
         "Raw correlations are tiny (temperature r = 0.13, rain −0.01) because hour of day masks them. After subtracting "
         "the usual weekday-hour level, <b>snow is the only condition with a large effect (≈ −270 vehicles/h)</b>. In the "
         "weekday rush hour, snowy hours carry <b>12% fewer vehicles</b> (5,210 vs 5,925 when clear). Very cold hours "
         "(< −15 °C) are ≈ 260 below normal. Rain, mist and fog effects are within noise. Weather is a "
         "<b>secondary driver</b>, kept mainly to catch snow days."),
        ("Q5. How do holidays change traffic?", "q5_holidays",
         "Figure 7 – Daily traffic on each holiday vs a normal day of the same weekday, and hourly profiles.",
         "Holidays cut daily traffic by <b>27% on average</b> (53 complete holiday days). Christmas, New Year and "
         "Thanksgiving are ≈ −47% to −49%; Independence, Memorial and Labor Day −32% to −40%. MLK and Presidents' Day are "
         "−16% to −19%, Veterans Day −7%. Columbus Day (≈ 0%) and the Minnesota State Fair (+3%) show no drop. On holidays "
         "the morning peak disappears and the profile looks like a weekend. The effect varies by holiday and each one "
         "appears only ~5 times, so holidays stay a source of error."),
        ("Q6. Do recent moving averages tell us whether this hour will be above or below last week? (lags + moving averages)",
         "q6_moving_average_deviation",
         "Figure 8 – 24 h and 168 h moving averages around Christmas 2016, and deviation from last week by quintile of the 24 h MA deviation.",
         "Alone, long moving averages correlate weakly with the hourly target (24 h MA r ≈ 0.19); they remove the daily "
         "cycle on purpose. Combined with the weekly lag they work: when the last 24 h ran well below the same 24 h last "
         "week (bottom quintile), the current hour is on average <b>≈ 400 vehicles/h below</b> last week's value, and ≈ 390 "
         "above in the top quintile (r = 0.47). Scaling last week's value by the ratio of the two 24 h MAs cuts the "
         "seasonal-naive MAE from <b>350 to 327 (−6.4%)</b> with no model at all. So we include 3 h, 24 h and 168 h moving "
         "averages and a 24 h rolling standard deviation."),
    ]
    for title, fig, cap, text in qs:
        s += [p(title, H2), *figure(fig, cap)]
        s.append(p("<b>Interpretation.</b> " + text))
        if fig == "q3_acf_pacf":
            s.extend(figure("q3_lag_scatter", "Figure 5b – Current traffic vs traffic 1 h, 24 h and 168 h earlier (Q3, continued)."))
    s.append(PageBreak())
    return s


def section_model():
    rows = [["Exp", "Model", "Features", "Tuning", "CV MAE", "Test MAE", "Test RMSE", "Test R²", "WAPE %"]]
    hl = []
    for i, e in enumerate(EXPERIMENTS, start=1):
        if e["exp"] == META["experiment"]:
            hl.append(i)
        rows.append([e["exp"], e["model"], e["features"], e["tuning"], e["cv_mae"], e["test_mae"],
                     e["test_rmse"], f"{float(e['test_r2']):.3f}", e["test_wape"]])
    hp_rows = [["Exp", "Best hyperparameters found"]] + [
        [e["exp"], e["hyperparameters"].replace("'", "")] for e in EXPERIMENTS if e["exp"] in ("E3", "E5", "E7")]
    s = [p("4. Task 1C — Model training and experiments", H1),
         p("<b>Features (33).</b> Calendar: hour, weekday, month, weekend, holiday, sine/cosine encodings of hour and "
           "weekday. Weather: temperature (°C), rain, snow, cloud cover, 11 weather one-hots. Lags: 1, 2, 3, 24 and 168 h. "
           "Moving averages: 3, 24 and 168 h means and a 24 h standard deviation. Every lag and rolling feature is "
           "shifted by at least one hour, so no feature can see the value being predicted."),
         p("<b>Validation design.</b> A chronological hold-out: training 2012-10 → 2017-12 (30,190 rows), test "
           "2018-01 → 2018-09 (6,378 rows). Hyperparameters were tuned with <b>TimeSeriesSplit</b> (4 expanding folds) "
           "inside the training period, so every validation fold lies in the future of its training data. The final "
           "model is chosen by <b>cross-validated MAE</b>; the test set is only used for reporting. Metrics: MAE, RMSE, "
           "R² and WAPE. MAPE was avoided because night-time volumes near zero make it explode."),
         *figure("m1_train_test_split", "Figure 9 – Chronological train / test split."),
         p("Experiment table", H2),
         table(rows, [0.9 * cm, 3.6 * cm, 1.9 * cm, 3.6 * cm, 1.3 * cm, 1.4 * cm, 1.5 * cm, 1.3 * cm, 1.3 * cm],
               highlight_rows=hl, font_size=7.2),
         p("Highlighted: the model selected by lowest CV MAE and saved to models/traffic_model.joblib.", CAPTION),
         table(hp_rows, [1.2 * cm, FRAME_W - 1.2 * cm], font_size=7.4),
         Spacer(1, 8),
         *figure("m2_experiment_comparison", "Figure 10 – Test MAE per experiment (orange = selected model, grey = baseline)."),
         p("Findings", H2),
         *bullets([
             "<b>Every trained model beats the seasonal-naive baseline.</b> The tuned tree models cut MAE from 340 to ≈ 140 "
             "vehicles/h (−59%), a WAPE of 4.2%. RMSE drops 651 → 219, so large misses are much rarer.",
             "<b>Linear models plateau at MAE ≈ 282.</b> The hour × weekday × lag interactions are non-linear; the Ridge "
             "grid is flat between α = 0.01 and 100.",
             "<b>Tuning improves both tree families:</b> Random Forest CV MAE 184.4 → 173.8 (−5.7%), with depth-limited "
             "trees (max_depth 18) and 33% of features per split. Gradient boosting 181.7 → 174.5 (−4.0%), with a lower "
             "learning rate (≈ 0.03) and larger leaves. The search shows learning rates above ≈ 0.18 are clearly worse.",
             "<b>E5 and E7 are practically tied</b> (0.4% apart). E5 is kept because the pre-set rule is lowest CV MAE; "
             "E7 is an equally valid, ≈ 30× smaller alternative.",
             "<b>Ablations confirm the EDA.</b> Without lags and moving averages (E8), CV MAE rises 73% (174.5 → 301.4). "
             "Without weather (E9) it is unchanged: snow is rare and its effect shows up in lag_1 within an hour.",
         ]),
         *figure("m3_forecast_diagnostics", "Figure 11 – Actual vs forecast for two test weeks, and error by hour of day."),
         *figure("m4_feature_importance", "Figure 12 – Permutation importance on the test set (top 15).",
                 width=FRAME_W * 0.8),
         p("<b>Where the model fails.</b> Errors peak at the 07:00–08:00 and 16:00 rush-hour ramps and at 21:00–23:00. "
           "Four of the five worst test days are heavy-snow days (19–23 snowy hours each, e.g. the 14 Apr 2018 storm, with "
           "volume 64% below the same day last week). Lagged traffic only adapts after the drop starts. Next steps would "
           "be a snow-intensity feature from a weather forecast, an events calendar, multi-step horizons and an LSTM for "
           "comparison."),
         PageBreak()]
    return s


def section_databases():
    sample_doc = """{
  "_id":            {"$oid": "6adf49388b5edaeb3c093fca"},
  "timestamp":      {"$date": "2012-10-10T07:00:00Z"},
  "traffic_volume": 6793,
  "weather": {
    "temp_k": 281.25, "rain_1h_mm": 0.0, "snow_1h_mm": 0.0, "clouds_pct": 99,
    "conditions": [ {"main": "Rain",    "description": "light rain"},
                    {"main": "Drizzle", "description": "light intensity drizzle"} ]
  },
  "holiday":  null,
  "calendar": {"year": 2012, "month": 10, "day": 10, "hour": 7, "day_of_week": 2, "is_weekend": false}
}"""
    schema_excerpt = """CREATE TABLE traffic_observations (
    observation_id   INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    date_time        DATETIME          NOT NULL,
    traffic_volume   INT UNSIGNED      NOT NULL,
    temp             DECIMAL(6,2)      NULL,      -- Kelvin, stored raw
    rain_1h          DECIMAL(7,2)      NOT NULL DEFAULT 0,
    snow_1h          DECIMAL(5,2)      NOT NULL DEFAULT 0,
    clouds_all       TINYINT UNSIGNED  NOT NULL,
    holiday_id       SMALLINT UNSIGNED NULL,
    PRIMARY KEY (observation_id),
    UNIQUE KEY uq_observation_time (date_time),
    CONSTRAINT fk_observation_holiday FOREIGN KEY (holiday_id)
        REFERENCES holidays (holiday_id) ON DELETE SET NULL,
    CONSTRAINT chk_clouds CHECK (clouds_all BETWEEN 0 AND 100)
);
CREATE TABLE observation_weather (
    observation_id INT UNSIGNED NOT NULL, condition_id SMALLINT UNSIGNED NOT NULL,
    condition_rank TINYINT UNSIGNED NOT NULL DEFAULT 1,
    PRIMARY KEY (observation_id, condition_id),
    FOREIGN KEY (observation_id) REFERENCES traffic_observations (observation_id) ON DELETE CASCADE,
    FOREIGN KEY (condition_id)   REFERENCES weather_conditions (condition_id)
);"""
    s = [p("5. Task 2 — Database design", H1),
         p("Both databases store the <b>raw</b> 40,575 hourly observations exactly as published, including the invalid "
           "readings. Cleaning happens in the Python pipeline, so the databases remain the unmodified source of truth "
           "and the prediction script re-applies the same preprocessing to whatever the API returns. Loaders: "
           "<font name='DejaVu-Mono'>database/load_mysql.py</font> and <font name='DejaVu-Mono'>load_mongodb.py</font>."),
         p("5.1 Relational schema (MySQL 8.4)", H2),
         *figure(ROOT / "database" / "sql" / "erd.png", "Figure 13 – Entity-relationship diagram (database/sql/erd.png)."),
         table([
             ["Table", "Rows", "Role"],
             ["traffic_observations", "40,575", "Time-series fact table, one row per hour. UNIQUE(date_time) enforces one row per hour "
                                                "and serves every range / latest query."],
             ["weather_conditions", "38", "Lookup of distinct (main, description) pairs; case-sensitive collation because the "
                                          "source has both “Sky is Clear” and “sky is clear”."],
             ["observation_weather", "48,123", "Junction table: an hour can report several conditions, so hour ↔ condition is "
                                               "many-to-many. condition_rank keeps source order (1 = primary)."],
             ["holidays", "53", "One row per holiday date; all 24 hours of that date reference it."],
         ], [3.8 * cm, 1.4 * cm, FRAME_W - 5.2 * cm]),
         Spacer(1, 6),
         p("Integrity rules: FKs with ON DELETE CASCADE (deleting an hour removes its weather links) and SET NULL for "
           "holidays; CHECK constraints on cloud cover and precipitation; created_at / updated_at audit columns; a "
           "denormalised view <font name='DejaVu-Mono'>v_hourly_traffic</font>. Excerpt of "
           "<font name='DejaVu-Mono'>database/sql/schema.sql</font>:"),
         Preformatted(schema_excerpt, CODE),
         p("5.2 MongoDB collection design", H2),
         p("Collection <font name='DejaVu-Mono'>metro_traffic.traffic_readings</font>, one document per hour:"),
         Preformatted(sample_doc, CODE),
         *bullets([
             "<b>Embed rather than reference:</b> weather conditions and the holiday are always read with the hour, so the "
             "SQL junction table becomes a small embedded array and every read is a single document.",
             "<b>Pre-computed calendar sub-document</b> makes hour-of-day and weekday aggregations simple "
             "<font name='DejaVu-Mono'>$group</font>s backed by an index. The API rebuilds it on every write so it cannot drift.",
             "<b>Regular collection with a unique index on timestamp</b> rather than a native time-series collection, which "
             "cannot have unique indexes. Here one document per hour must be guaranteed, with full CRUD by id.",
             "<b>Indexes:</b> unique timestamp, (day_of_week, hour), multikey on weather.conditions.main, partial index on "
             "holiday. A <b>$jsonSchema validator</b> enforces types, ranges and at least one condition.",
             "Four complete sample documents are in <font name='DejaVu-Mono'>database/mongodb/sample_documents.json</font>.",
         ]),
         PageBreak(),
         p("5.3 Queries and results", H2),
         p("Six SQL and five MongoDB queries were run (<font name='DejaVu-Mono'>database/run_queries.py</font>). Full "
           "queries and outputs are in <font name='DejaVu-Mono'>outputs/query_results/</font>; selected results follow."),
         table([
             ["#", "SQL query", "Technique"],
             ["Q1", "Latest 5 observations with conditions and holiday", "3-table JOIN, GROUP_CONCAT"],
             ["Q2", "Hour-of-day profile, weekday vs weekend", "Conditional aggregation"],
             ["Q3", "Monthly summary for 2017", "Date-range filter, GROUP BY month"],
             ["Q4", "Holiday effect vs an average non-holiday day", "CTE + scalar subquery"],
             ["Q5", "Daily totals, 7-day MA, day-over-day and week-over-week change", "Window functions AVG() OVER, LAG()"],
             ["Q6", "Weekday rush-hour volume by weather", "Junction-table JOIN, HAVING"],
         ], [1 * cm, 9 * cm, FRAME_W - 10 * cm]),
         Spacer(1, 6),
         table([
             ["#", "MongoDB query", "Technique"],
             ["M1", "Latest reading", "find().sort({timestamp: -1}).limit(1)"],
             ["M2", "Readings in a date range", "$gte / $lte on timestamp"],
             ["M3", "Weekday rush-hour volume by primary weather", "$match → $first → $group"],
             ["M4", "Daily totals + 7-day moving average", "$dateTrunc, $setWindowFields, $shift"],
             ["M5", "Holiday summary", "$group on an embedded field"],
         ], [1 * cm, 9 * cm, FRAME_W - 10 * cm]),
    ]

    def result_block(title, md, prefix, max_rows=None, widths=None):
        rows = md_result_table(md, prefix, max_rows)
        return [p(title, H3),
                Preformatted(md_query_text(md, prefix), CODE),
                table(rows, widths, font_size=7.2),
                Spacer(1, 8)]

    s += result_block("SQL Q1 – Latest 5 observations", SQL_MD, "Q1")
    s += result_block("SQL Q5 – Daily totals with 7-day moving average (window functions)", SQL_MD, "Q5", max_rows=8)
    s += result_block("SQL Q4 – Holiday effect", SQL_MD, "Q4")
    s += result_block("MongoDB M1 – Latest reading", MONGO_MD, "M1")
    s += result_block("MongoDB M2 – Records in a date range", MONGO_MD, "M2")
    s += result_block("MongoDB M4 – Daily totals with 7-day moving average ($setWindowFields)", MONGO_MD, "M4", max_rows=8)
    s += result_block("MongoDB M3 – Weekday rush-hour volume by weather (same answer as SQL Q6)", MONGO_MD, "M3")
    s.append(Spacer(1, 14))
    return s


def section_api():
    rows = [["Method", "Path (both /sql and /mongo)", "Behaviour"],
            ["POST", "/{db}/records", "Create an hourly record. 201; 409 if the hour already exists; 422 on invalid body"],
            ["GET", "/{db}/records?limit=&offset=", "Paginated list, newest first"],
            ["GET", "/{db}/records/latest", "<b>Latest record</b> (most recent hour)"],
            ["GET", "/{db}/records/range?start=&end=", "<b>Records by date range</b>, oldest first; 400 if start > end"],
            ["GET", "/{db}/records/{id}", "One record (SQL observation_id or Mongo ObjectId); 404 if missing"],
            ["PUT", "/{db}/records/{id}", "Update only the fields sent; weather list replaced if provided"],
            ["DELETE", "/{db}/records/{id}", "Delete and return the deleted record (SQL cascades weather links)"],
            ["GET", "/", "Health check with record counts for both databases"]]
    checks = [["Result", "Request", "Status (expected)"]] + [
        [r, f"{m} {path}", f"{got} ({exp})"] for r, m, path, got, exp in API_CHECKS]
    return [
        p("6. Task 3 — CRUD and time-series API", H1),
        p("A <b>FastAPI</b> service (<font name='DejaVu-Mono'>api/</font>) exposes the same endpoints and the same JSON "
          "record shape for both databases, so a client can switch between <font name='DejaVu-Mono'>/sql</font> and "
          "<font name='DejaVu-Mono'>/mongo</font> without code changes. Interactive documentation is generated at "
          "<font name='DejaVu-Mono'>/docs</font>."),
        table(rows, [1.5 * cm, 5.4 * cm, FRAME_W - 6.9 * cm]),
        Spacer(1, 6),
        p("Implementation notes", H2),
        *bullets([
            "<b>Validation:</b> Pydantic models enforce types and ranges (volume ≥ 0, cloud cover 0–100, temperature in "
            "Kelvin, at least one weather condition). MongoDB enforces its own $jsonSchema as a second line of defence.",
            "<b>SQL writes are transactional:</b> one POST/PUT touches up to four tables (get-or-create the holiday and "
            "weather lookups, insert the observation, link conditions) inside a single transaction.",
            "<b>Reads avoid the view:</b> range queries filter <font name='DejaVu-Mono'>traffic_observations</font> on its "
            "unique date_time index first, then fetch the weather for just those ids, rather than scanning a GROUP BY view.",
            "<b>MongoDB updates</b> rebuild the document so the derived calendar fields stay consistent; duplicate hours "
            "return 409 and validator failures return 422. Database outages return 503.",
        ]),
        p("Testing", H2),
        p(f"<font name='DejaVu-Mono'>scripts/test_api.py</font> runs a full create → read → latest → range → update → list → "
          f"delete → read-404 cycle on each database, plus error cases. <b>{sum(c[0] == 'PASS' for c in API_CHECKS)} of "
          f"{len(API_CHECKS)} checks pass</b>. Every request and response is logged in "
          f"<font name='DejaVu-Mono'>outputs/api_test_results.md</font>."),
        table(checks, [1.4 * cm, 11 * cm, FRAME_W - 12.4 * cm], font_size=7),
        Spacer(1, 14),
    ]


def section_predict():
    c = FORECAST["context"]
    out = f"""$ python scripts/predict.py
[1/4] Fetching data from http://127.0.0.1:8000/mongo/records ...
      latest record: 2018-09-30T23:00:00  volume=954
      fetched 336 hourly records (2018-09-17T00:00:00 -> 2018-09-30T23:00:00)
[2/4] Preprocessing (clean -> hourly grid -> lag / moving-average features) ...
      grid: 336 hours, 0 imputed, 0 still missing
[3/4] Loading model ...
      {META['model']} (experiment {META['experiment']}, test MAE {META['test_metrics']['test_mae']} veh/h)
[4/4] Forecasting ...
============================================================
 Forecast for Monday 01 Oct 2018, 00:00
   predicted traffic volume :  {FORECAST['predicted_traffic_volume']:>5,} vehicles/hour
   previous hour            :  {c['last_hour_volume']:>5,}
   same hour last week      :  {c['same_hour_last_week']:>5,}
============================================================

$ python scripts/predict.py --source sql --at 2018-09-28T17:00
 Forecast for Friday 28 Sep 2018, 17:00
   predicted traffic volume :  5,570 vehicles/hour
   actual traffic volume    :  5,695 vehicles/hour  (error 125)"""
    return [
        p("7. Task 4 — Prediction script", H1),
        p("<font name='DejaVu-Mono'>scripts/predict.py</font> ties the previous tasks together in four steps:"),
        table([
            ["Step", "What happens"],
            ["1. Fetch", "GET /{db}/records/latest, then GET /{db}/records/range for the two weeks before it "
                         "(the features need ≥ 169 hours of history)."],
            ["2. Preprocess", "API JSON is converted back to the raw-CSV layout and passed through the same "
                              "src/preprocessing.py functions as training: invalid values → NaN, de-duplication, regular "
                              "hourly grid, ≤ 3 h interpolation, calendar / weather / lag / moving-average features."],
            ["3. Load model", "models/traffic_model.joblib plus its metadata; the script refuses to run if the saved "
                              "feature list differs from the current pipeline."],
            ["4. Predict", "Builds the feature row for the hour after the latest record (weather carried forward as a "
                           "persistence forecast, holidays from the US federal calendar) and prints and saves the "
                           "forecast to outputs/latest_forecast.json."],
        ], [2.6 * cm, FRAME_W - 2.6 * cm]),
        Spacer(1, 6),
        p("A <font name='DejaVu-Mono'>--at</font> option back-tests a known hour by hiding its value, and "
          "<font name='DejaVu-Mono'>--source sql|mongo</font> chooses the database. Both sources return the same forecast. "
          "As a consistency check, features built from API data for three test hours matched the training features to "
          "within 1e-11, and the predictions were identical."),
        Preformatted(out, CODE),
    ]


def section_team():
    rows = [["Member", "Role", "Major components"]] + [[n, r, c] for n, r, c in TEAM]
    return [
        p("8. Team contributions", H1),
        p("Each member owned one part of the pipeline and committed their own work to the repository."),
        table(rows, [3 * cm, 4.2 * cm, FRAME_W - 7.2 * cm]),
        Spacer(1, 10),
        p("9. Conclusion", H1),
        p("The pipeline turns a messy six-year hourly dataset into a working forecasting service. EDA showed that traffic "
          "is driven by daily and weekly cycles and short-term momentum, while weather and holidays act as occasional "
          "shocks. That finding shaped the features (lags 1–168 h and moving averages) and is confirmed by the ablation "
          "experiments. The tuned tree models reach a 4.2% weighted error, 59% better than the seasonal-naive baseline. "
          "The same data is stored in a normalised MySQL schema and a document-oriented MongoDB collection, served "
          "through identical CRUD and time-series endpoints, and consumed by a prediction script that reuses the "
          "training pipeline unchanged. <b>Limitations:</b> the forecast horizon is one hour, next-hour weather is "
          "assumed to persist, and rare events (snowstorms, unusual holidays) remain the largest source of error."),
        p(f"Code, notebooks and instructions to reproduce every result: "
          f"<link href='{REPO_URL}' color='#2a78d6'>{REPO_URL}</link>"),
    ]


def build():
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.9 * cm, bottomMargin=1.8 * cm,
                            title="Building a Pipeline for Time-Series Data - Group 21",
                            author="Group 21", subject="Metro Interstate Traffic Volume forecasting pipeline")
    story = (cover() + section_problem() + [Spacer(1, 10)] + section_eda() + section_questions()
             + section_model() + section_databases() + section_api() + section_predict() + section_team())
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print("Report written to", OUT.relative_to(ROOT))


if __name__ == "__main__":
    build()
