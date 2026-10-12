import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html

import data
import figures as F
from ui import card, graph, kpi, message, page_title

dash.register_page(__name__, path="/tyres", name="Tyre Analysis", title="Tyres · BoxBox", order=1, icon="🛞")

layout = html.Div([
    html.Div(id="ty-head"),
    html.Div([html.Span("Compounds", className="bb-ctl-label"),
              dbc.Checklist(id="ty-comp", options=[{"label": c.title(), "value": c} for c in data.COMPOUNDS],
                            value=data.COMPOUNDS, inline=True, switch=True, className="bb-switches")],
             className="bb-controls"),
    dbc.Row(id="ty-kpis", className="g-3 mb-4"),
    card("Tyre Degradation Curves", "Lap time vs tyre age. Dots are real laps, lines are the fitted degradation rate.",
         graph("ty-deg", 460)),
    card("Tyre Survival Probability", "Probability the tyre is still competitive at a given age, with confidence bands.",
         [graph("ty-surv", 460), html.Div(id="ty-surv-note")]),
    dbc.Row([
        dbc.Col(card("Real-World Stint Lengths", "How long drivers actually ran each compound (diamond = mean).",
                     graph("ty-stint", 400)), md=6),
        dbc.Col(card("Compound Pace", "Average lap time per compound at this circuit.", graph("ty-pace", 400)), md=6),
    ], className="g-3"),
], className="bb-fade")


@callback(Output("ty-head", "children"), Output("ty-kpis", "children"), Output("ty-deg", "figure"),
          Output("ty-surv", "figure"), Output("ty-surv-note", "children"), Output("ty-stint", "figure"),
          Output("ty-pace", "figure"), Input("circuit-dd", "value"), Input("ty-comp", "value"))
def update(circuit, compounds):
    compounds = [c for c in data.COMPOUNDS if c in (compounds or [])]
    laps = data.circuit_laps(circuit)
    deg_all = data.degradation()
    deg = deg_all[deg_all["CircuitName"] == circuit] if not deg_all.empty else deg_all
    surv_all = data.survival()
    surv = surv_all[surv_all["CircuitName"] == circuit] if not surv_all.empty else surv_all

    head = page_title(f"Tyre Analysis · {circuit}", "How each compound wears, how long it lasts, and what teams did.")

    kpis = []
    for c in data.COMPOUNDS:
        p = deg[deg["Compound"] == c] if not deg.empty else deg
        kpis.append(kpi(f"{c.title()} degradation", f"{p.iloc[0]['DegradationRate']:+.3f} s/lap" if not p.empty else "—",
                        "lower is better", F.COMPOUND_COLORS[c]))

    if laps.empty or not compounds:
        e = F.empty("No lap data for this selection")
        return head, kpis, e, e, None, e, e

    sfig, shown = F.survival_curves(surv, compounds)
    missing = sorted(set(compounds) - set(shown))
    note = message("Not enough stint data for a reliable survival curve: " + ", ".join(missing), "warn") if missing else None
    return (head, kpis, F.degradation_curves(laps, deg, compounds), sfig, note,
            F.stint_boxes(laps, compounds), F.pace_bars(laps, compounds))