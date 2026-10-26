import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dash_table, dcc, html

import data
from ui import card, message, page_title

dash.register_page(__name__, path="/pipeline", name="Pipeline", title="Pipeline · BoxBox", order=4, icon="🧪", section="lab")

PHASES = [
    ("1", "Data Collection", "FastF1 / Jolpica laps, stints, weather and results for every 2024 race.", []),
    ("2", "Engineering & Cleaning", "Fuel-corrected lap times, outlier removal, tyre-age features.", ["engineered_laps.csv", "feature_store.csv"]),
    ("3", "Degradation Modeling", "Gradient boosting with GroupKFold, SHAP explanations, degradation rate per compound.", ["degradation_profiles.csv", "shap_values.csv"]),
    ("4", "Survival Analysis", "Kaplan-Meier tyre survival curves with confidence bands, Cox hazard ratios.", ["survival_curves.csv"]),
    ("5", "Strategy Optimizer", "Searches stop counts and compound orders to produce Plan A, B and C with risk levels.", ["optimal_strategies.csv", "plan_abc.csv"]),
    ("6", "ML Models", "Compound selector, undercut classifier, circuit clusters, with dummy baselines.", ["circuit_clusters.csv"]),
    ("7", "Anomaly Detection", "DBSCAN flags odd laps that survive cleaning; compared with manual cleaning.", ["dbscan_anomaly_summary.csv", "dbscan_vs_manual_comparison.csv"]),
    ("8", "Circuit Maps", "Track maps built from telemetry with DRS zones from the race session.", ["circuit_maps/*.json"]),
]


def _present(name):
    if "*" in name:
        return any(data.BASE.glob(name))
    return (data.PROCESSED / name).exists() or (data.OUTPUTS / name).exists()


def phase_card(n, title, desc, files):
    chips = [html.Span(f, className="bb-chip " + ("bb-chip-ok" if _present(f) else "bb-chip-miss")) for f in files]
    return dbc.Col(html.Div([html.Div(n, className="bb-phase-n"), html.H5(title, className="bb-card-title"),
                             html.P(desc, className="bb-card-sub"), html.Div(chips)],
                            className="bb-card bb-phase"), md=6, xl=3)


TABLES = data.list_tables()

layout = html.Div([
    page_title("Pipeline · Eight Phases", "Everything the project does, from raw laps to strategy, and every table it produced."),
    dbc.Row([phase_card(*p) for p in PHASES], className="g-3 mb-4"),
    card("Data Explorer", "Browse, sort, filter and download any output table.", [
        dbc.Row([
            dbc.Col(dcc.Dropdown(id="pl-table", options=list(TABLES), value=next(iter(TABLES), None),
                                 clearable=False, className="bb-dd"), md=6),
            dbc.Col(dbc.Switch(id="pl-filter", label="Only the selected circuit", value=False), md=4),
            dbc.Col(html.Button("Download CSV", id="pl-dl-btn", className="bb-btn"), md=2),
        ], className="g-3 mb-3 align-items-center"),
        html.Div(id="pl-info", className="bb-card-sub"),
        html.Div(id="pl-table-out"),
        dcc.Download(id="pl-download"),
    ]),
], className="bb-fade")


def _df(key, circuit, only):
    df = data.read_table(key)
    if only and "CircuitName" in df:
        df = df[df["CircuitName"] == circuit]
    return df


@callback(Output("pl-table-out", "children"), Output("pl-info", "children"),
          Input("pl-table", "value"), Input("pl-filter", "value"), Input("circuit-dd", "value"))
def show(key, only, circuit):
    if key not in TABLES:
        return message("No tables found. Check BOXBOX_BASE.", "warn"), ""
    df = _df(key, circuit, only)
    tbl = dash_table.DataTable(
        data=df.head(5000).round(4).to_dict("records"), columns=[{"name": c, "id": c} for c in df.columns],
        page_size=12, sort_action="native", filter_action="native", style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#1B1C21", "color": "#FFFFFF", "fontWeight": "700",
                      "border": "1px solid #2A2B30"},
        style_cell={"backgroundColor": "#121316", "color": "#DDDDDD", "border": "1px solid #232428",
                    "fontFamily": "Inter", "fontSize": "13px", "padding": "8px", "minWidth": "90px"},
        style_data_conditional=[{"if": {"state": "active"}, "backgroundColor": "#2A1518", "border": "1px solid #E8002D"}],
    )
    note = f"{len(df):,} rows × {len(df.columns)} columns" + (" (first 5,000 shown)" if len(df) > 5000 else "")
    return tbl, note


@callback(Output("pl-download", "data"), Input("pl-dl-btn", "n_clicks"), State("pl-table", "value"),
          State("pl-filter", "value"), State("circuit-dd", "value"), prevent_initial_call=True)
def download(_, key, only, circuit):
    if key not in TABLES:
        return dash.no_update
    return dcc.send_data_frame(_df(key, circuit, only).to_csv, key.split("/")[-1], index=False)