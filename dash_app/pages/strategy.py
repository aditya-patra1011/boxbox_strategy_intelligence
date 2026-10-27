import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, html

import data
import figures as F
from ui import card, graph, kpi, message, page_title, pills

dash.register_page(__name__, path="/strategy", name="Strategy", title="Strategy · BoxBox", order=0, icon="🏁", section="lab")

layout = html.Div([
    html.Div(id="st-head"),
    dbc.Row(id="st-kpis", className="g-3 mb-4"),
    card("Circuit Map", "Track layout with DRS zones from the race session", graph("st-map", 540)),
    html.H3("Race Strategy Plans", className="bb-section"),
    dbc.Row(id="st-plans", className="g-3"),
], className="bb-fade")

TITLES = {"A": "Plan A · Optimal", "B": "Plan B · Real-World", "C": "Plan C · Alternative"}
BLURBS = {"A": "Fastest predicted race time from the optimizer.",
          "B": "What teams really did: median real stint lengths.",
          "C": "Best different-stop-count alternative."}


@callback(Output("st-head", "children"), Output("st-kpis", "children"),
          Output("st-map", "figure"), Output("st-plans", "children"), Input("circuit-dd", "value"))
def update(circuit):
    row = data.circuit_row(circuit)
    plans = data.plan_abc()
    cp = plans[plans["CircuitName"] == circuit] if not plans.empty else plans
    head = page_title(circuit or "—", "Strategy intelligence: what to run, when to stop, and how risky it is.")

    best = cp[cp["PlanLabel"] == "A"]
    kpis = [
        kpi("Optimal stops", int(best.iloc[0]["NumStops"]) if not best.empty else "—", "Plan A"),
        kpi("Predicted race time", data.format_race_time(best.iloc[0]["PredictedTotalTime"]) if not best.empty else "—",
            "h:mm:ss", "#448AFF"),
        kpi("Pit loss", f"{row['AvgPitLoss']:.1f}s" if row is not None and "AvgPitLoss" in row else "—",
            "per stop", "#FFD500"),
        kpi("Safety car chance", f"{row['SafetyCarProbability']:.0%}" if row is not None else "—",
            "per race", "#FFB300"),
        kpi("Track temp", f"{row['AvgTrackTemp']:.0f}°C" if row is not None else "—", "average", "#00C853"),
    ]

    fig = data.circuit_map(circuit) if circuit else None
    if fig is None:
        fig = F.empty("Circuit map not available for this track")
    else:
        fig = F.style(fig, margin=dict(l=10, r=10, t=60, b=10))
        fig.update_layout(autosize=True, width=None, height=None,   # fit the card, whatever size Phase 8 saved
                          title=dict(x=0.02, y=0.97, yanchor="top", font=dict(size=22, color="#FFFFFF")))

    if cp.empty:
        cards = [dbc.Col(message("No strategy data available for this circuit", "warn"))]
    else:
        base = best.iloc[0]["PredictedTotalTime"] if not best.empty else None
        cards = []
        for label in ["A", "B", "C"]:
            r = cp[cp["PlanLabel"] == label]
            if r.empty:
                if label == "B":        # wet 2024 races: strategy cards cover dry tyres only
                    cards.append(dbc.Col(html.Div([
                        html.Div(html.Span(TITLES[label], className="bb-plan-title"), className="bb-plan-top"),
                        html.P("Strategy cards cover dry-tyre strategies only. The 2024 race here ran "
                               "partly on intermediates, so there's no dry real-world plan to compare.",
                               className="bb-card-sub"),
                    ], className="bb-card bb-plan"), md=4))
                continue
            r = r.iloc[0]
            delta = (r["PredictedTotalTime"] - base) if base is not None else None
            risk = str(r["RiskLevel"])
            cards.append(dbc.Col(html.Div([
                html.Div([html.Span(TITLES[label], className="bb-plan-title"),
                          html.Span(risk, className=f"bb-badge bb-risk-{risk.lower()}")], className="bb-plan-top"),
                html.P(BLURBS[label], className="bb-card-sub"),
                pills(r["strategy"]),
                html.Div(str(r["strategy"]), className="bb-plan-raw"),
                html.Div([html.Div([html.Div(f"{int(r['NumStops'])}", className="bb-big"), html.Div("stops")]),
                          html.Div([html.Div(f"{r['PredictedTotalTime']:.1f}s", className="bb-big"),
                                    html.Div("predicted" if not delta else f"+{delta:.1f}s vs Plan A")])],
                         className="bb-plan-stats"),
            ], className=f"bb-card bb-plan bb-plan-{risk.lower()}"), md=4))
    return head, kpis, fig, cards