import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, html, no_update

import data
import figures as F
from ui import card, graph, kpi, message, page_title

dash.register_page(__name__, path="/season", name="Season Overview", title="Season · BoxBox", order=3, icon="📅", section="lab")

layout = html.Div([
    page_title("Season Overview · 2024", "All circuits at a glance. Click any bar or dot to jump the dashboard to that circuit."),
    dbc.Row(id="se-kpis", className="g-3 mb-4"),
    card("Strategy Landscape", "Optimal stop count and predicted race time per circuit. The white outline is your selected circuit.",
         graph("se-land", 500)),
    card("Circuit Clusters", "K-Means groups by degradation, pit loss and safety-car risk. Bubble size = average stint length.",
         graph("se-clus", 500)),
    card("Compound Usage", "How often each compound was used across every 2024 race.", graph("se-comp", 400)),
], className="bb-fade")


@callback(Output("se-kpis", "children"), Output("se-land", "figure"), Output("se-clus", "figure"),
          Output("se-comp", "figure"), Input("circuit-dd", "value"))
def update(circuit):
    opt, fs, cl, cc = data.optimal(), data.feature_store(), data.clusters(), data.compound_counts()
    kp = []
    if not opt.empty:
        one = (opt["NumStops"] == 1).mean()
        kp += [kpi("Circuits", len(opt), "in the model", "#448AFF"),
               kpi("One-stop optimal", f"{one:.0%}", "of circuits"),
               kpi("Fastest circuit", opt.sort_values("PredictedTotalTime").iloc[0]["CircuitName"], "shortest race", "#00C853")]
    if not fs.empty and "AvgPitLoss" in fs:
        kp.append(kpi("Avg pit loss", f"{fs['AvgPitLoss'].mean():.1f}s", "season", "#FFD500"))
    if not cc.empty:
        kp.append(kpi("Most used", cc.sort_values("Count").iloc[-1]["Compound"].title(), "compound", "#FF3B3B"))
    land = F.landscape(opt, circuit) if not opt.empty else F.empty()
    clus = F.cluster_scatter(cl.merge(fs, on="CircuitName", how="left"), circuit) if not cl.empty else F.empty()
    comp = F.compound_usage(cc) if not cc.empty else F.empty()
    return kp, land, clus, comp


@callback(Output("circuit-dd", "value", allow_duplicate=True), Input("se-land", "clickData"), prevent_initial_call=True)
def pick_from_bar(click):
    return click["points"][0]["x"] if click else no_update


@callback(Output("circuit-dd", "value", allow_duplicate=True), Input("se-clus", "clickData"), prevent_initial_call=True)
def pick_from_dot(click):
    try:
        return click["points"][0]["customdata"][0]
    except Exception:
        return no_update