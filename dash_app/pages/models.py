import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html

import data
import figures as F
from ui import card, graph, kpi, message, page_title

dash.register_page(__name__, path="/models", name="Model Insights", title="Models · BoxBox", order=2, icon="🧠", section="lab")

layout = html.Div([
    html.Div(id="mo-head"),
    dbc.Row([
        dbc.Col(card("What Drives Degradation Here", "SHAP feature importance for this circuit.", graph("mo-shap", 360)), md=6),
        dbc.Col(card("Compound Selection Confidence", "Model probability per compound, by stint.", [
            html.Div([html.Span("Stint", className="bb-ctl-label"),
                      dbc.RadioItems(id="mo-stint", options=[1, 2, 3], value=1, inline=True, className="bb-radio")],
                     className="bb-controls"),
            graph("mo-comp", 300), html.Div(id="mo-comp-note")]), md=6),
    ], className="g-3 mb-3"),
    card("Undercut Viability", "Chance that pitting early to undercut a rival works. Change the scenario below.", [
        dbc.Row([
            dbc.Col([html.Label("Position before pit", className="bb-ctl-label"),
                     dcc.Slider(1, 20, 1, value=10, id="mo-pos", marks={1: "P1", 10: "P10", 20: "P20"},
                                tooltip={"placement": "bottom"})], md=4),
            dbc.Col([html.Label("Tyre life at pit (laps)", className="bb-ctl-label"),
                     dcc.Slider(1, 40, 1, value=15, id="mo-life", marks={1: "1", 20: "20", 40: "40"},
                                tooltip={"placement": "bottom"})], md=4),
            dbc.Col([html.Label("Compound being replaced", className="bb-ctl-label"),
                     dbc.Select(id="mo-off", options=[{"label": c.title(), "value": i} for i, c in enumerate(data.COMPOUNDS)],
                                value=1)], md=4),
        ], className="g-4 mb-3"),
        dbc.Row([dbc.Col(graph("mo-gauge", 300), md=5), dbc.Col(html.Div(id="mo-und-text"), md=7)], className="g-3 align-items-center"),
    ], className="mb-3"),
    card("Data Quality · Anomaly Detection", "DBSCAN anomalies left after cleaning vs. what manual cleaning removed.",
         dbc.Row(id="mo-db", className="g-3")),
], className="bb-fade")


@callback(Output("mo-head", "children"), Output("mo-shap", "figure"), Input("circuit-dd", "value"))
def shap(circuit):
    head = page_title(f"Model Insights · {circuit}", "What the models learned and how confident they are.")
    s = data.shap_values()
    s = s[s["CircuitName"] == circuit] if not s.empty else s
    return head, (F.shap_bars(s) if not s.empty else F.empty("No SHAP data for this circuit"))


@callback(Output("mo-comp", "figure"), Output("mo-comp-note", "children"),
          Input("circuit-dd", "value"), Input("mo-stint", "value"))
def comp(circuit, stint):
    try:
        classes, probs = data.compound_probabilities(circuit, stint)
        return F.compound_probs(classes, probs), None
    except Exception as e:
        return F.empty("Unavailable"), message(f"Compound selector prediction unavailable: {e}", "warn")


@callback(Output("mo-gauge", "figure"), Output("mo-und-text", "children"),
          Input("circuit-dd", "value"), Input("mo-pos", "value"), Input("mo-life", "value"), Input("mo-off", "value"))
def undercut(circuit, pos, life, off):
    try:
        allp = data.undercut_all(int(pos), int(life), int(off))
        p = float(allp[circuit])
        avg, rank = float(allp.mean()), int((allp > p).sum() + 1)
        diff = (p - avg) * 100
        text = html.Div([
            html.Div(f"Rank {rank} of {len(allp)} circuits for undercut viability", className="bb-big"),
            html.P(f"{abs(diff):.1f} points {'above' if diff >= 0 else 'below'} the season average ({avg:.0%}) "
                   f"for this exact scenario.", className="bb-card-sub"),
            message("Proxy target: success means the position was held or improved shortly after the stop, because "
                    "live rival-gap telemetry was not collected. Read the number as relative viability between "
                    "circuits, not as an absolute probability.", "info"),
        ])
        return F.gauge(p * 100), text
    except Exception as e:
        return F.empty("Unavailable"), message(f"Undercut prediction unavailable: {e}", "warn")


@callback(Output("mo-db", "children"), Input("circuit-dd", "value"))
def dbscan(circuit):
    d = data.dbscan()
    d = d[d["CircuitName"] == circuit] if not d.empty else d
    if d.empty:
        return dbc.Col(message("No anomaly data for this circuit", "info"))
    r = d.iloc[0]
    cards = [kpi("Total laps (cleaned)", f"{int(r['TotalLaps']):,}", accent="#B138DD"),
             kpi("Anomalies detected", f"{int(r['AnomaliesDetected']):,}", accent="#FFD500"),
             kpi("Anomaly rate", f"{r['AnomalyRate']:.2%}", accent="#E10600")]
    if "ManualCleaningRate" in r.index:
        removed = f"{int(r['RemovedByManualCleaning']):,} of {int(r['RawLapCount']):,} raw laps" \
            if {"RemovedByManualCleaning", "RawLapCount"} <= set(r.index) else "Phase 2"
        cards.append(kpi("Removed by manual cleaning", f"{r['ManualCleaningRate']:.1%}", removed, "#00D26A"))
    return cards