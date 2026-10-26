# BoxBox - F1 Strategy Intelligence Dashboard

_"Because some pit walls need help"_

**BoxBox** is what your pit wall radios say when it's time to pit. The term became something of a meme thanks to Ferrari's chaotic strategy calls over the years. This project is a data-driven attempt to make that call the right one, every time.

![BoxBox Dashboard - Strategy](docs/dash_app/strategy.png)

_BoxBox is an unofficial fan and educational project. It is not affiliated with, endorsed by, or connected to Formula 1, the FIA, or any team._

---

## What It Is

A full-stack F1 Strategy Intelligence tool built entirely on real 2024 Formula 1 season data. It combines tyre degradation modelling, survival analysis, machine learning, and an interactive dashboard to answer the questions a real race strategist asks: which tyres, in what order, when to pit, and how risky is the plan.

The project ships with **two dashboards** built on the same data and models:

- **Plotly Dash dashboard (main, `dash_app/`)**: a 5-page multi-page app with a sidebar circuit selector, shareable URLs and click-to-select charts.
- **Streamlit dashboard (original, `dashboard/`)**: the first version, a 4-page app, still included and working.

**Live Capabilities:**

- Predicts tyre degradation per circuit and compound using validated ML models
- Estimates tyre "survival probability" using medical-grade survival analysis techniques
- Generates three ranked strategy options (A/B/C) per circuit, each with a calculated risk score
- Visualises everything through a dark-themed, interactive dashboard with real circuit maps, DRS/braking zones and turn-by-turn markers

---

## The Pipeline - 9 Phases

| Phase                              | What It Does                                                                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 1 - Data Collection                | Pulls the complete 2024 F1 season via FastF1: lap timing, pit stops, race results, weather, circuit telemetry                     |
| 2 - Cleaning & Feature Engineering | Removes pit/safety-car/outlier laps; engineers 10 features (fuel-corrected pace, stint progress, compound age ratio, etc.)        |
| 3 - Degradation Modeling           | Trains Polynomial, Ridge, and Random Forest per circuit/compound; cross-validated RMSE picks the winner                           |
| 4 - Survival Analysis              | Kaplan-Meier survival curves + Cox Proportional Hazards models, borrowed from medical/reliability statistics                      |
| 5 - Strategy Optimization          | Simulates every realistic 1-stop/2-stop strategy per circuit; outputs Plan A/B/C with risk scores                                 |
| 6 - ML Models                      | Six purpose-built models: Stint Length, Compound Selector, Strategy, Pit Window, Circuit Clustering (K-Means), Undercut Viability |
| 7 - Anomaly Detection              | DBSCAN independently validates Phase 2's manual data cleaning                                                                     |
| 8 - Circuit Map Builder            | Builds broadcast-style circuit maps from real GPS telemetry: braking zones, DRS zones, turn markers, speed trap                   |
| 9 - Dashboard                      | Interactive dashboard tying everything together: Plotly Dash (main) and Streamlit (original)                                      |

---

## The Dashboard (Plotly Dash)

Pick any of the 23 circuits from the sidebar and every page updates. The selected circuit is stored in the URL (e.g. `?circuit=Monaco`), so any view can be shared as a link.

### Strategy

Circuit map with key stats, plus Plan A/B/C cards showing stop count, compound sequence, predicted race time and a colour-coded risk badge (Low / Medium / High).

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

**A target-leakage bug in the degradation model, found and fixed.** Phase 3 originally predicted `LapTimeSeconds` with `FuelCorrectedLapTime` as an input, but that input is the lap time itself plus 0.054 s × lap number, so the answer leaked into the features. The "degradation rate" then measured the fuel term, not tyre wear: 21 of 57 rates were negative (tyres getting *faster* with age) and Softs came out as the slowest-wearing compound. The model now predicts each lap's fuel-corrected time relative to its own stint (so driver pace differences can't fake a trend), drops `StintProgress` (it needed the stint's final length), cross-validates by whole stints, and measures the rate as a slope across the tyre ages actually seen. Negative rates fell to 8 of 58, all near zero or from thin data (Canada's chaotic race, a 3-stint Hungary Soft group), and the median rate now orders correctly: Soft +0.061, Medium +0.051, Hard +0.041 s/lap. SHAP now ranks `TyreLife` as the main driver instead of the leaked lap time. Plan A changed at 16 of 23 circuits, mostly towards starting on the softer tyre (e.g. Bahrain Soft → Hard → Hard). The bug surfaced when Race Analysis compared 2026 measured degradation against the model.

**Canada 2024 was a genuine data outlier, and two independent methods agree on it.** 80% of Canada's raw laps were removed during manual cleaning due to heavy Safety Car/VSC disruption. Phase 7's DBSCAN anomaly detection, a completely separate unsupervised method, independently flagged Canada as one of the messiest races of the season, cross-validating the manual cleaning decision.

**Cox hazard models revealed real, statistically significant, circuit-specific risk drivers.** Emilia Romagna and the Netherlands show fuel-corrected pace as the dominant tyre-failure risk factor (hazard ratio ≈ 2.1-2.2, p < 0.01); Austria's dominant factor is track temperature instead.

**Risk scores across circuits show genuine, validated variation.** After fixing two upstream bugs (a Safety Car Probability calculation that was silently returning zero for every circuit, and a Cox model that was failing to fit due to a column-name mismatch), Plan A risk scores span a real range from 0.4 (Monaco, lowest risk) to 30.8 (Great Britain, highest risk), with a spread of Low/Medium/High classifications (13 / 6 / 4) across the season rather than one flat bucket.

**Model accuracy is context-dependent, and that's disclosed rather than hidden.** The Compound Selector, Strategy Outcome and Undercut classifiers land in the 68-77% accuracy range, meaningfully lower than what's achievable on a deterministic physics problem, because F1 strategy also involves human decisions, competitor behaviour and genuine randomness (teammates, rivals' errors, safety car timing) rather than fixed physical laws. This is treated as the problem's inherent noise ceiling, not a modelling flaw.

**The 2024 São Paulo Grand Prix (Brazil) is intentionally excluded.** The race was run entirely under wet-weather conditions, with zero laps on dry compounds (SOFT/MEDIUM/HARD), placing it outside this project's dry-tyre degradation and strategy scope.

---

## Known Limitations

- **Undercut Viability Classifier uses a documented proxy.** True rival-vs-rival gap telemetry wasn't collected in Phase 1, so the model instead uses whether track position held or improved shortly after a pit stop as a stand-in signal. In the Dash app the result is shown as a _relative rank_ across all 23 circuits rather than an absolute probability. This is a real limitation, not full undercut modelling.
- **Compound Selector and Undercut demo predictions use representative inputs** (e.g. a chosen stint number, a mid-field grid position) rather than live race state, since this is a strategy reference tool, not a live-race feed.
- **DBSCAN flagged residual data-quality anomalies** (~1.5% of cleaned laps), most heavily in Japan, Australia, Spain, Azerbaijan and Great Britain. Worth awareness if extending this analysis further.
- **Trained on 2024 data only.** The 2026 regulation change introduces domain shift, so the models would need retraining on 2025/2026 data to be used for current races.

---

## Tech Stack

- **Data Collection:** FastF1 (free; Jolpica-F1 and OpenF1 considered for future work)
- **Data Science:** pandas, numpy, scikit-learn, SHAP, lifelines (survival analysis), joblib
- **Visualisation:** Plotly
- **Dashboards:** Plotly Dash + dash-bootstrap-components (main), Streamlit (original)
- **Serving:** gunicorn
- **Models:** Polynomial/Ridge Regression, Random Forest Regression, Kaplan-Meier, Cox Proportional Hazards, Gradient Boosting (classification & regression), K-Means, DBSCAN, Logistic Regression

---

## Project Structure

```
boxbox/
├── docs/
│   └── dash_app/
│       ├── strategy.png            (Dash)
│       ├── tyre-analysis.png       (Dash)
│       ├── model-insights.png      (Dash)
│       ├── season-overview.png     (Dash)
│       ├── pipeline.png            (Dash)
│   └── streamlit/
│       ├── dashboard_page1.jpg     (Streamlit)
│       ├── circuit_map.png         (Streamlit)
│       └── strategy_cards.png      (Streamlit)
│
├── outputs/                   (chart images used by the Streamlit section)
├── cache/                     (FastF1 cache - gitignored)
├── data/                      (raw/processed/outputs - gitignored, regenerated by running phases)
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
│   ├── app.py                 (entry point, sidebar, URL sync; server = app.server)
│   ├── data.py                (data/model access layer)
│   ├── figures.py             (all Plotly figures)
│   ├── ui.py                  (reusable UI components)
│   ├── requirements.txt
│   ├── assets/style.css
│   └── pages/
│       ├── strategy.py
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
├── .gitignore
└── README.md
```

---

## How to Run

```bash
# 1. Install dependencies (project-wide, for the notebooks and Streamlit)
pip install -r requirements.txt

# 2. Phases 1-8 are Jupyter notebooks - open each one in order and run all top to bottom:
notebooks/phase1_collection.ipynb
notebooks/phase2_engineering.ipynb
notebooks/phase3_degradation.ipynb
notebooks/phase4_survival.ipynb
notebooks/phase5_optimizer.ipynb
notebooks/phase6_ml_models.ipynb
notebooks/phase7_anomaly_detection.ipynb
notebooks/phase8_circuit_maps.ipynb
```

### 3a. Launch the Dash dashboard (main)

```bash
cd dash_app
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:8050**.

By default the app looks for `data/`, `models/` and `circuit_maps/` in the parent folder of `dash_app`. To point it somewhere else, set the `BOXBOX_BASE` environment variable:

```bash
# PowerShell
$env:BOXBOX_BASE = "C:\path\to\BoxBox"
```

For production-style serving:

```bash
gunicorn app:server
```

### 3b. Launch the Streamlit dashboard (original)

```bash
python -m streamlit run dashboard/app.py
```

**Note:** `data/`, `models/` and `circuit_maps/` are gitignored since they're large and fully reproducible. Clone the repo, run the notebooks in order, and everything regenerates locally.

---

## Data Coverage Note

The 2024 São Paulo Grand Prix is excluded from this analysis, since the race was run under wet-weather conditions with no dry-compound laps recorded. All other 23 circuits from the 2024 calendar are covered.

## Roadmap

- [ ] Public deployment of the Dash app
- [ ] Dedicated charts for extra Phase 3-6 outputs (model metrics, hazard ratios, model comparison)
- [ ] Retrain on 2025/2026 data

## Acknowledgments

- Data: acquired using the FastF1 library
- Built as part of a personal ML portfolio project
- F1, Formula 1 and related marks are trademarks of their respective owners

## Author

**Aditya**
GitHub: [@aditya-patra1011](https://github.com/aditya-patra1011)
Portfolio: [portfolioaditya-pearl.vercel.app](https://portfolioaditya-pearl.vercel.app)

## LICENSE

This project is licensed under the terms of the LICENSE file included in this repository.
