# BoxBox - F1 Race Centre & Strategy Intelligence

_"Because some pit walls need help"_

**BoxBox** is what your pit wall radios say when it's time to pit. The term became something of a meme thanks to Ferrari's chaotic strategy calls over the years. This project is a data-driven attempt to make that call the right one, every time.

![BoxBox Race Live - replay of the 2026 United States Grand Prix](docs/race_centre/race-live.png)

_BoxBox is an unofficial fan and educational project. It is not affiliated with, endorsed by, or connected to Formula 1, the FIA, or any team. It uses no official F1 logos, photos or track graphics: track maps are drawn from the cars' own position data, and drivers are shown as number cards._

---

## What It Is

One website with two sections, switched from the top bar:

- **Race Centre**: the current season as it happens. A race weekend hub, a replay of the latest race with every car moving on track, race analysis, both championships, the calendar, and every team's history. It runs on **free data only** (Jolpica and OpenF1) and updates itself after each race.
- **Strategy Lab**: the original BoxBox. Tyre degradation models, survival analysis and a strategy optimizer built on the full 2024 season, answering a race strategist's questions: which tyres, in what order, when to pit, and how risky the plan is.

The two link to each other. Race Centre's next-race card opens that circuit's strategy plans in Strategy Lab, and every Race Centre circuit card does the same where a model exists.

**What it does:**

- Replays the latest race lap by lap, with Safety Car, VSC and red-flag periods detected from race control messages
- Measures real tyre degradation from every clean lap and compares it with the BoxBox model
- Tracks both championships round by round, including who can still mathematically win
- Predicts tyre degradation per circuit and compound with cross-validated ML models (2024 data)
- Estimates tyre "survival probability" with survival analysis (Kaplan-Meier, Cox)
- Generates three strategy options (Plan A/B/C) per circuit from every valid 1-, 2- and 3-stop strategy, each with a risk score

The original **Streamlit** dashboard (`dashboard/`) is still included and working.

---

## The Pipeline - 9 Phases

| Phase                              | What It Does                                                                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 1 - Data Collection                | Pulls the complete 2024 F1 season via FastF1: lap timing, pit stops, race results, weather, circuit telemetry                     |
| 2 - Cleaning & Feature Engineering | Removes pit/safety-car/outlier laps; engineers 10 features (fuel-corrected pace, stint progress, compound age ratio, etc.)        |
| 3 - Degradation Modeling           | Trains Polynomial, Ridge, and Random Forest per circuit/compound; cross-validated RMSE picks the winner                           |
| 4 - Survival Analysis              | Kaplan-Meier survival curves + Cox Proportional Hazards models, borrowed from medical/reliability statistics                      |
| 5 - Strategy Optimization          | Simulates every realistic 1-, 2- and 3-stop strategy per circuit; outputs Plan A/B/C with risk scores                             |
| 6 - ML Models                      | Six purpose-built models: Stint Length, Compound Selector, Strategy, Pit Window, Circuit Clustering (K-Means), Undercut Viability |
| 7 - Anomaly Detection              | DBSCAN independently validates Phase 2's manual data cleaning                                                                     |
| 8 - Circuit Map Builder            | Builds broadcast-style circuit maps from real GPS telemetry: braking zones, DRS zones, turn markers, speed trap                   |
| 9 - Dashboard                      | Interactive dashboard tying everything together: Plotly Dash (main) and Streamlit (original)                                      |

---

## Race Centre (2026 season, free data)

Six pages, built on [Jolpica](https://github.com/jolpica/jolpica-f1) (calendar, results, standings, history) and [OpenF1](https://openf1.org)'s free historical data (laps, stints, race control, positions, car telemetry).

### Home

The live or next race: track outline, weekend schedule with a countdown, and a **"View strategy plans for this race"** link into Strategy Lab. Below it is any race's classification: gap to the winner, interval to the car ahead ("+1 Lap" for lapped cars), places gained, final tyre and a **FASTEST LAP** tag. Last comes a season heatmap of every driver's finish at every round; click a race to load its results.

![Race Centre home](docs/race_centre/home.png)

### Race Live

A replay of the latest race. Press play (1×, 5×, 20× or 60×) or drag to any lap, and every car moves round the track in team colour. Alongside: the running order (gap, tyre and its age, pit stops), a **speed ticker** of the last 60 seconds for the drivers you pick, every driver's tyre stints, and a lap chart. Safety Car, VSC and red-flag laps are shaded and counted ("Virtual Safety Car · laps 51-53 (3 laps)"). `/live?lap=30` opens the replay at lap 30.

The clock and the cars run in the browser ([`assets/replay.js`](dash_app/assets/replay.js)), filling in between the stored 2-per-second samples, and the server sends car data in 2-minute blocks.

### Race Analysis

Tyre degradation measured from every clean lap of the latest race. It uses the same cleaning and fuel correction as Phase 2, and takes the slope within each stint so driver pace differences can't fake a trend. That measurement is compared with the BoxBox model's 2024 rate for the circuit. The page also has pace through the race, race pace (median clean lap) and speed-trap rankings, plus a card explaining the method.

![Race Analysis](docs/race_centre/race-analysis.png)

### Standings

Driver and constructor tables after the latest round (places gained, wins, gap to the leader), points or championship position round by round, and **who can still mathematically win**, from the race and sprint points left.

![Championship standings](docs/race_centre/standings.png)

### Calendar

A card for every round with its track outline. Finished races show the winner, the live weekend gets a red **LIVE** badge, and the next race is tagged **NEXT**. Open a card for the circuit: first Formula 1 Grand Prix, races held, measured lap length, race distance, the weekend schedule, the podium and the fastest lap.

![Season calendar](docs/race_centre/calendar.png)

### Teams

Every team in championship order with Constructors' and Drivers' titles and race wins, **counting predecessor teams** (Tyrrell → BAR → Honda → Brawn → Mercedes, Jordan → … → Aston Martin). Open a team for its two drivers (number-and-initials cards), titles by year, wins under each name, and a timeline of iconic moments. The lineage and timelines are hand-written in [`content/teams.json`](content/teams.json). The counts are computed from Jolpica into `content/team_stats.json`.

![Teams](docs/race_centre/teams.png)

### How "live" works on free data

OpenF1's free tier has **no data while a session is running**: live timing is a paid tier. The whole session becomes free **30 minutes after it ends**. So Race Centre updates itself the moment the data is free:

- **The watcher** (`python -m ingest.watch`) follows the calendar. From about 30 minutes after a race could finish, it tries each minute to store the race. It checks Jolpica every 15 minutes for the official results and standings, and refreshes the season every 12 hours otherwise.
- **During a race weekend** the pages show a **LIVE** banner saying what's on track and roughly when the race data will appear. Until then they show the previous race.
- **When a newer race is stored**, open pages notice within a minute and offer to load it.

---

## Strategy Lab (2024 models)

Pick any of the 23 circuits from the sidebar and every page updates. The selected circuit is stored in the URL (e.g. `?circuit=Monaco`), so any view can be shared as a link.

### Strategy

Circuit map with key stats, plus strategy cards showing stop count, compound sequence, predicted race time and a colour-coded risk badge (Low / Medium / High). **Plan A** is the optimizer's fastest strategy and **Plan B** what teams really did (the most common strategy among 2024 finishers, shown where the race was dry). **Plan C** is the fastest strategy with a different number of stops (often a three-stop where a one-stop can't fit the tyre life seen in 2024).

![Strategy page](docs/dash_app/strategy.png)

### Tyre Analysis

Degradation curves per compound, Kaplan-Meier survival curves, stint-length distributions and compound pace comparison. When a compound has too few stints, the survival curve is replaced with a note instead of a misleading line.

![Tyre Analysis page](docs/dash_app/tyre-analysis.png)

### Model Insights

SHAP feature importance, compound-selector probabilities by stint, an interactive **undercut viability gauge** (position, tyre life and compound sliders, ranked against all 23 circuits), and DBSCAN data-quality metrics showing flagged laps vs. manual cleaning.

![Model Insights page](docs/dash_app/model-insights.png)

### Season Overview

Season-wide strategy landscape (1-stop vs. 2-stop), K-Means circuit clusters and compound usage. **Click a bar or a dot to jump straight to that circuit.**

![Season Overview page](docs/dash_app/season-overview.png)

### Pipeline

All phases at a glance, with live file-presence checks (green/red) for every expected output, plus a **Data Explorer** to browse any processed or output CSV, filter by circuit and download it.

![Pipeline page](docs/dash_app/pipeline.png)

> All 23 circuits are available in the dashboard. **Brazil has no data**: the 2024 São Paulo GP was a fully wet race, and this project focuses on the dry compounds (SOFT, MEDIUM, HARD).

---

## The Original Streamlit Dashboard

The first version of the dashboard, still included in `dashboard/`. It has four pages.

<details>
<summary><b>Show Streamlit screenshots</b></summary>

![BoxBox Streamlit Dashboard - Circuit Intelligence](docs/streamlit/dashboard_page1.jpg)

### Page 1 - Circuit Intelligence

_"All the screenshots shown of analysis are for Abu Dhabi circuit"_

![Circuit Map with DRS and Braking Zones](docs/streamlit/circuit_map.png)

Interactive circuit map (smoothed track outline, solid red braking zones, dashed green DRS zones offset outside the track, auto-detected numbered turns, speed trap and start/finish markers) alongside Plan A/B/C strategy cards, each showing stop count, compound sequence, predicted race time, and a colour-coded risk badge (Low/Medium/High).

![Strategy Cards - Plan A B C](docs/streamlit/strategy_cards.png)

### Page 2 - Tyre Analysis

![Tyre Degradation Curves](outputs/tire_degradation_curve.png)

Degradation curves: predicted lap time vs. tyre age, per compound, with regression slopes.

![Tyre Survival Probability](outputs/survival_probability.png)

Kaplan-Meier survival curves with confidence bands. Here Medium and Hard tyres completely overlap each other, and Soft tyre probability was not acquired because of insufficient data.

![Stint Length Distribution](outputs/real_world_stint_length_distributor.png)

Real-world stint length distribution (box plots).

![Compound Pace Comparison](outputs/compound_pace_comparison.png)

### Page 3 - Model Insights

![SHAP Feature Importance](outputs/SHAP_interpretation.png)

SHAP feature importance: what actually drives degradation at each circuit.

![Compound Selection Confidence](outputs/Compound_selection_stints.png)

Compound Selector confidence, with interactive stint-number slider.

![Undercut Viability & DBSCAN data-quality metrics](outputs/undercut_anomaly.png)

Undercut Viability gauge and DBSCAN anomaly detection.

(These graphs are different for all 23 races and can be accessed via the dashboard. Only the metrics and graphs for Abu Dhabi are shown here.)

### Page 4 - Season Overview

![Season Strategy Landscape](outputs/strategy_landscape.png)

Full season strategy landscape (1-stop vs. 2-stop by circuit).

![Circuit Clusters](outputs/circuit_clusters.png)

K-Means circuit cluster scatter plot.

![Compound Usage Across the Season](outputs/compound_usage_across_season.png)

Season-wide compound usage frequency.

</details>

---

## Key Findings

**Model selection isn't one-size-fits-all.** Random Forest won 33 of 58 circuit/compound degradation models, Ridge Regression won 13 and Polynomial 12. Tyre degradation is often non-linear but genuinely linear at some circuits. Letting cross-validated RMSE choose the model per circuit beat assuming one formula everywhere.

**A target-leakage bug in the degradation model, found and fixed.** Phase 3 originally predicted `LapTimeSeconds` with `FuelCorrectedLapTime` as an input, but that input is the lap time itself plus 0.054 s × lap number, so the answer leaked into the features. The "degradation rate" then measured the fuel term, not tyre wear: 21 of 57 rates were negative (tyres getting *faster* with age) and Softs came out as the slowest-wearing compound. The model now predicts each lap's fuel-corrected time relative to its own stint (so driver pace differences can't fake a trend), drops `StintProgress` (it needed the stint's final length), cross-validates by whole stints, and measures the rate as a slope across the tyre ages actually seen. Negative rates fell to 8 of 58, all near zero or from thin data (Canada's chaotic race, a 3-stint Hungary Soft group), and the median rate now orders correctly: Soft +0.061, Medium +0.051, Hard +0.041 s/lap. SHAP now ranks `TyreLife` as the main driver instead of the leaked lap time. The bug surfaced when Race Analysis compared 2026 measured degradation against the model.

**Canada 2024 was a genuine data outlier, and two independent methods agree on it.** 80% of Canada's raw laps were removed during manual cleaning due to heavy Safety Car/VSC disruption. Phase 7's DBSCAN anomaly detection, a completely separate unsupervised method, independently flagged Canada as one of the messiest races of the season, cross-validating the manual cleaning decision.

**Raw average lap times made Hard tyres look faster than they are.** Phase 5 originally took each compound's pace from its raw average lap time. But Hards are mostly run late in a race on a light car, and Mediums early on a heavy one. At Australia the raw averages had Hard 0.84 s a lap faster than Medium; fuel-corrected, Medium is 0.31 s faster. The optimizer believed Hard was the quick tyre and used the shortest stint the rules allowed on anything else, so plans opened with a 5-lap stint. Pace now comes from the fuel-corrected average, and each circuit has its own minimum stint (the 10th percentile of the opening stints teams really ran there in 2024, at least 5 laps). Short stints fell from 14 of 60 plans to 9 of 69, and in Plan A from 5 circuits to 2. Predicted race times stay within a median +0.5% of the real 2024 winners'.

**The last 5-lap opening stints came from flat tyre wear, not good strategy.** At Canada and Monaco a 5-lap and a 10-lap opening stint are within a second of each other, and the model had no reason to avoid stopping on lap 5. Two changes fix that. First, a stop on laps 1-5 now costs what it really cost in 2024: across 557 green-flag stops (in-lap to three laps after, against the driver's own pace either side), early stops lost 4.5 s more than later ones, as the car rejoins a still-bunched field. That comes from only 9 early stops, so it's a rough figure. Second, plans within 1 s of each other count as a tie at the model's accuracy, and the tie goes to the plan with the longer shortest stint. Monaco's Plan A is now Soft 10 → Hard 68, and no plan opens with a stint of 5 laps or fewer.

**Plan B had been copying Plan C at six circuits.** Plan B is meant to be what teams really did, but it was built from the cleaned laps, which drop whole stints (wet running, red-flag and safety-car laps). At Canada, Great Britain, Japan, Monaco and Qatar no driver's stints added up to their stop count, and Italy's real Hard stint ran past the tyre-life ceiling. Each time Plan B quietly fell back to Plan C. It now comes from the raw laps of drivers who finished, with 1-2 lap stints (lap-1 red-flag tyre changes, stint-numbering glitches) folded into the next stint. It skips the tyre-life ceiling, because teams really did run those stints. Canada and Great Britain were partly wet, and the strategy cards cover dry-tyre strategies only, so they now show a note in place of Plan B instead of a copy.

**Cox hazard models revealed real, statistically significant, circuit-specific risk drivers.** Emilia Romagna and the Netherlands show fuel-corrected pace as the dominant tyre-failure risk factor (hazard ratio ≈ 2.1-2.2, p < 0.01); Austria's dominant factor is track temperature instead.

**Risk scores across circuits show genuine, validated variation.** After fixing two upstream bugs (a Safety Car Probability calculation that was silently returning zero for every circuit, and a Cox model that was failing to fit due to a column-name mismatch), Plan A risk scores span a real range from 0.2 (Singapore, lowest risk) to 28.0 (Saudi Arabia, highest risk). Risk levels are cut at the thirds of every plan's score (Low ≤ 4.2, Medium ≤ 10.7), which puts Plan A at 5 Low, 7 Medium and 11 High across the season rather than one flat bucket.

**Model accuracy is context-dependent, and that's disclosed rather than hidden.** The Compound Selector, Strategy Outcome and Undercut classifiers land in the 68-77% accuracy range, meaningfully lower than what's achievable on a deterministic physics problem, because F1 strategy also involves human decisions, competitor behaviour and genuine randomness (teammates, rivals' errors, safety car timing) rather than fixed physical laws. This is treated as the problem's inherent noise ceiling, not a modelling flaw.

**The 2024 São Paulo Grand Prix (Brazil) is intentionally excluded.** The race was run entirely under wet-weather conditions, with zero laps on dry compounds (SOFT/MEDIUM/HARD), placing it outside this project's dry-tyre degradation and strategy scope.

---

## Known Limitations

- **Undercut Viability Classifier uses a documented proxy.** True rival-vs-rival gap telemetry wasn't collected in Phase 1, so the model instead uses whether track position held or improved shortly after a pit stop as a stand-in signal. In the Dash app the result is shown as a _relative rank_ across all 23 circuits rather than an absolute probability. This is a real limitation, not full undercut modelling.
- **Compound Selector and Undercut demo predictions use representative inputs** (e.g. a chosen stint number, a mid-field grid position) rather than live race state, since this is a strategy reference tool, not a live-race feed.
- **DBSCAN flagged residual data-quality anomalies** (~1.5% of cleaned laps), most heavily in Japan, Australia, Spain, Azerbaijan and Great Britain. Worth awareness if extending this analysis further.
- **Strategy Lab is trained on 2024 data only.** The 2026 regulation change introduces domain shift, so the models would need retraining on 2025/2026 data to be used for current races. Race Analysis shows the gap: measured 2026 wear at Austin is +0.05-0.08 s/lap, while the model's 2024 rates there are about +0.01.
- **The early-stop cost rests on 9 stops.** Only 9 green-flag stops in 2024 came on laps 1-5, so the +4.5 s figure is rough, and it's one value for every circuit. Great Britain's minimum stint (19 laps, from a wet-to-dry race) leaves no valid strategy, so it falls back to 5.
- **Strategy cards are dry-tyre only, by design.** Canada and Great Britain 2024 were run partly on intermediates, so there's no dry real-world strategy to show as Plan B, and the app shows a note there instead. Wet-weather strategy is planned as a later stage.
- **No timing during a session.** OpenF1's free tier makes a session available 30 minutes after it ends, so Race Centre replays races rather than showing them live. Jolpica's official results usually follow within a few hours.
- **Measured lap lengths are the racing line.** Calendar lap lengths are measured from the pole lap's car positions. They read about 1-2% under the official centreline length (median −1.4% across 22 published lengths), and they're labelled that way.
- **Haas 2018 in Jolpica.** Jolpica ranks Haas 6th in 2018 because it combines Force India's points from before and after its mid-season rescue. The Teams timeline uses the official 5th.
- **The phase scripts use a fixed path.** `phases/*.py` set `BASE = r'C:\Users\adity\Desktop\BoxBox'`; change it if the repo lives elsewhere.

---

## Tech Stack

- **Data Collection:** FastF1 (2024 season, Strategy Lab), [Jolpica F1 API](https://github.com/jolpica/jolpica-f1) and [OpenF1](https://openf1.org) free historical data (2026 season, Race Centre). FastF1 can't load 2026 timing without an F1 account, so Race Centre doesn't use it.
- **Storage:** SQLite for Race Centre data (`data/race_centre/`, gitignored); committed JSON for circuit outlines and team content (`content/`)
- **Data Science:** pandas, numpy, scikit-learn, SHAP, lifelines (survival analysis), joblib
- **Visualisation:** Plotly; a little browser-side JavaScript for the race replay
- **Dashboards:** Plotly Dash + dash-bootstrap-components (main), Streamlit (original)
- **Testing:** pytest (86 tests on saved API responses; no network needed)
- **Serving:** gunicorn
- **Models:** Polynomial/Ridge Regression, Random Forest Regression, Kaplan-Meier, Cox Proportional Hazards, Gradient Boosting (classification & regression), K-Means, DBSCAN, Logistic Regression

---

## Project Structure

```
boxbox/
├── docs/
│   ├── race_centre/           (Race Centre screenshots)
│   ├── dash_app/              (Strategy Lab screenshots)
│   └── streamlit/             (original Streamlit screenshots)
│
├── ingest/                    (Race Centre data: free APIs -> local SQLite store)
│   ├── jolpica.py             (Jolpica client: calendar, results, standings)
│   ├── openf1.py              (OpenF1 client, kept under the free 30 requests/minute)
│   ├── season.py, __main__.py (python -m ingest --season 2026)
│   ├── session.py             (python -m ingest.session: one race in full, or --season-stints)
│   ├── circuits.py            (python -m ingest.circuits: track outlines + circuit facts)
│   ├── teams.py               (python -m ingest.teams: titles and wins through team lineage)
│   ├── watch.py               (python -m ingest.watch: keeps everything up to date)
│   └── store.py               (SQLite schema)
│
├── content/                   (committed Race Centre content)
│   ├── circuits/              (one track outline per circuit, from OpenF1 car positions)
│   ├── circuits.json          (first GP, races held, racing-line length, laps)
│   ├── teams.json             (hand-written: lineage, bases, colours, timelines)
│   └── team_stats.json        (computed: titles and wins per team)
│
├── tests/                     (pytest; saved API responses in tests/fixtures)
│
├── outputs/                   (chart images used by the Streamlit section)
├── cache/                     (FastF1 cache - gitignored)
├── data/                      (raw/processed/outputs and race_centre/ store - gitignored, regenerated)
├── models/                    (trained .pkl models - gitignored, regenerated by Phase 3/4/6/7)
├── circuit_maps/              (Plotly JSON per circuit - gitignored, regenerated by Phase 8)
│
├── notebooks/
│   ├── phase1_collection.ipynb
│   ├── phase2_engineering.ipynb
│   ├── phase3_degradation.ipynb
│   ├── phase4_survival.ipynb
│   ├── phase5_optimizer.ipynb
│   ├── phase6_ml_models.ipynb
│   ├── phase7_anomaly_detection.ipynb
│   └── phase8_circuit_maps.ipynb
│
├── dash_app/                  (main dashboard - Plotly Dash)
│   ├── app.py                 (entry point, section switcher, sidebar, URL sync; server = app.server)
│   ├── data.py                (Strategy Lab data/model access)
│   ├── race_data.py           (Race Centre data access, read-only)
│   ├── live_status.py         (live-weekend banner, "new data is in" check)
│   ├── figures.py             (all Plotly figures)
│   ├── ui.py                  (reusable UI components)
│   ├── requirements.txt
│   ├── assets/style.css
│   ├── assets/replay.js       (Race Live replay clock and drawing, in the browser)
│   └── pages/
│       ├── race/              (Race Centre: home, live, analysis, standings, calendar, teams)
│       ├── strategy.py        (Strategy Lab)
│       ├── tyres.py
│       ├── models.py
│       ├── season.py
│       └── pipeline.py
│
├── dashboard/                 (original dashboard - Streamlit)
│   ├── app.py                 (Page 1 - Circuit Intelligence, entry point)
│   └── pages/
│       ├── 02_tire_analysis.py
│       ├── 03_model_insights.py
│       └── 04_season_overview.py
│
├── phases/
│   ├── phase1_collection.py
│   ├── phase2_engineering.py
│   ├── phase3_degradation.py
│   ├── phase4_survival.py
│   ├── phase5_optimizer.py
│   ├── phase6_ml_models.py
│   ├── phase7_anomaly_detection.py
│   └── phase8_circuit_maps.py
├── requirements.txt
├── requirements-dev.txt       (pytest)
├── .gitignore
└── README.md
```

---

## How to Run

All commands below are run from the repo root unless they say `cd dash_app`. **Use the same Python environment for every command:** `No module named 'dash'` means a command ran in a different one. The examples use `python`; on the author's machine that is the project environment, `.\.conda\python.exe`.

### 1. Set up (once)

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt -r dash_app/requirements.txt -r requirements-dev.txt
```

On macOS or Linux, activate with `source .venv/bin/activate`.

### 2. Get the Race Centre data (once, then the watcher keeps it fresh)

| Command | What it stores | Time |
| --- | --- | --- |
| `python -m ingest --season 2026` | Calendar, results, drivers, both championships after every round | ~30 s |
| `python -m ingest.session` | The latest finished race in full: laps, stints, race control, positions, gaps, car telemetry | ~5 min |
| `python -m ingest.session --season-stints 2026` | Just the tyre stints of every finished race (for the final-tyre column) | ~1 min |

Circuit outlines and team content are committed in `content/`. They only need rebuilding with `python -m ingest.circuits --season 2026` and `python -m ingest.teams` when the calendar or the titles change.

### 3. Start the dashboard

```bash
cd dash_app
```

```bash
python app.py
```

Open **http://127.0.0.1:8050**. Race Centre opens first, and the top-right switch goes to Strategy Lab. Press **Ctrl+C** to stop.

### 4. Keep it up to date (a second terminal)

```bash
python -m ingest.watch
```

It prints one line a minute, usually "nothing due". During a race weekend it stores the race about 30 minutes after the chequered flag, then the official results once Jolpica has them. `python -m ingest.watch --once` runs a single pass, for Windows Task Scheduler or cron.

### 5. Run the tests

```bash
python -m pytest tests
```

The suite runs on saved API responses, so it needs no network.

### Strategy Lab data (Phases 1-8)

`data/`, `models/` and `circuit_maps/` are gitignored because they're large and fully reproducible. Run the phases in order, Phase 1 to Phase 8, either as scripts:

```bash
python phases/phase1_collection.py
```

and then `phase2_engineering.py` through `phase8_circuit_maps.py`, or as the notebooks in `notebooks/` (open each and run all cells). **The scripts and the notebooks match** for every phase. Running Phase 5 both ways gives byte-identical strategies, and Phase 3 gives identical degradation profiles, SHAP values and metrics. If you change one, change the other.

### Settings (environment variables)

| Variable | Default | Use |
| --- | --- | --- |
| `BOXBOX_BASE` | the repo folder | Where `data/`, `models/`, `circuit_maps/` and `content/` live |
| `BOXBOX_STORE` | `data/race_centre/boxbox.sqlite` | The Race Centre store, for both the app and the ingest |
| `BOXBOX_NOW` | the real clock | Pins the clock (ISO time), e.g. `2026-10-31T21:30:00Z` to see a live race weekend |

In PowerShell, for example: `$env:BOXBOX_NOW = "2026-10-31T21:30:00Z"`, then start the app.

For production-style serving from `dash_app/`:

```bash
gunicorn app:server
```

Run the watcher next to it.

### Troubleshooting

- **`No module named 'dash'`**: the command ran in a Python without the packages. Activate the environment from step 1, or call its Python directly.
- **Don't use `streamlit run` on `dash_app/app.py`**: it's a Dash app (`python app.py`). Streamlit is only for the original dashboard below.
- **"No Race Centre data yet" on a page**: run the step 2 commands.
- **"Address already in use"**: another copy of the app is running on port 8050; close it or press Ctrl+C in its window.

### The original Streamlit dashboard

```bash
python -m streamlit run dashboard/app.py
```

---

## Data Coverage Note

The 2024 São Paulo Grand Prix is excluded from this analysis, since the race was run under wet-weather conditions with no dry-compound laps recorded. All other 23 circuits from the 2024 calendar are covered.

## Roadmap

- [x] Race Centre: 2026 season pages, race replay, race analysis and a watcher that updates on free data
- [x] Fix target leakage in the Phase 3 degradation model
- [ ] Public deployment of the Dash app (app + watcher)
- [x] Phase 3 notebook in line with the fixed script
- [x] Bring the `phases/` scripts for Phases 1, 2 and 4-8 up to date with their newer notebooks, and re-run Phase 5
- [ ] Retrain Strategy Lab on 2025/2026 data (Race Centre already stores 2026 races)
- [x] Plan C at every circuit (three-stop search) and fewer 5-lap opening stints (fuel-corrected compound pace, per-circuit minimum stint)
- [x] Price very early stops with a measured cost, break near-ties toward longer stints, and build Plan B from the real races (no more silent copies of Plan C)
- [ ] Later stage: wet-weather strategy (intermediate and wet tyres), including Plan B for wet races
- [ ] Dedicated charts for extra Phase 3-6 outputs (model metrics, hazard ratios, model comparison)

## Acknowledgments

- Data: [FastF1](https://github.com/theOehrly/Fast-F1) (2024 season), [Jolpica F1 API](https://github.com/jolpica/jolpica-f1) and [OpenF1](https://openf1.org) (2026 season, free historical data)
- Built as part of a personal ML portfolio project
- F1, Formula 1 and related marks are trademarks of their respective owners

## Author

**Aditya**
GitHub: [@aditya-patra1011](https://github.com/aditya-patra1011)
Portfolio: [portfolioaditya-pearl.vercel.app](https://portfolioaditya-pearl.vercel.app)

## LICENSE

This project is licensed under the terms of the LICENSE file included in this repository.
