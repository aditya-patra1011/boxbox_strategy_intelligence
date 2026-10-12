"""
Every chart in the dashboard. Same figures as the Streamlit version,
Plus highlight support
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

RED = "#E10600"
COMPOUND_COLORS = {"SOFT": "#FF3B3B", "MEDIUM": "#FFD500", "HARD": "#E0E0E0",
                   "Soft": "#FF3B3B", "Medium": "#FFD500", "Hard": "#E0E0E0"}
CLUSTER_COLORS = ["#E10600", "#FFD500", "#00D26A", "#2D9CFF", "#B138DD", "#FF8A00"]
GRID = "#242730"

def hex_to_rgba(h, alpha=0.2):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}, {alpha})"

def style(fig, margin=None, **layout):
    fig.update_layout(
        plot_bgcolor="#0E1014", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Barlow, sans-serif", size=13, color="#C9CBD2"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=margin or dict(l=10, r=10, t=20, b=10),
        hoverlabel=dict(bgcolor="#1B1C21", bordercolor=RED, font=dict(family="Barlow", color="#FFFFFF")),
        transition=dict(duration=350, easing="cubic-in-out"),
        **layout,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig

def empty(msg="No data available"):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(size=15, color="#888888"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return style(fig)

# TYRE ANALYSIS
def degradation_curves(laps, deg, compounds):
    fig = go.Figure()
    for c in compounds:
        d = laps[laps["Compound"] == c]
        if d.empty:
            continue
        fig.add_trace(go.Scatter(x=d["TyreLife"], y=["LapTimeSeconds"], mode="markers",
                                marker=dict(color=COMPOUND_COLORS[c], size=4, opacity=0.3),
                                name=f"{c} (laps)", showlegend=False, hoverinfo="skip"))
        p = deg[deg["Compound"] == c]
        if not p.empty:
            r = p.iloc[0]
            xs = [0, d["TyreLife"].max()]
            ys = [r["AvgLapTime"] - r["DegradationRate"] * r["AvgTyreLife"] + r["DegradationRate"] * x for x in xs]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=COMPOUND_COLORS[c], width=3),
                                    name=f"{c} ({r['DegradationRate']:+.3f}s/lap)"))
    fig.update_xaxes(title="Tire Age (laps)")
    fig.update_yaxes(title="Lap Time (s)")
    return style(fig)

def survival_curves(surv, compounds):
    fig, shown = go.Figure(), []
    for c in compounds:
        d = surv[surv["Compound"] == c].sort_values("TyreAge")
        if d.empty:
            continue
        shown.append(c)
        fig.add_trace(go.Scatter(x=d["TyreAge"], y=d["CI_Upper"], mode="lines", line=dict(width=0),
                                showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=d["TyreAge"], y=d["CI_Lower"], mode="lines", line=dict(width=0),
                                fill="tonexty", fillcolor=hex_to_rgba(COMPOUND_COLORS[c]),
                                showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=d["TyreAge"], y=d["SurvivalProbability"], mode="lines",
                                line=dict(color=COMPOUND_COLORS[c], width=3, shape="hv"), name=c))
    fig.update_xaxes(title="Tire Age (laps)")
    fig.update_yaxes(title="Survival Probability", range=[0, 1.05])
    return style(fig, hovermode="x unified"), shown

def stint_boxes(laps, compounds):
    s = laps.groupby(["Driver", "Stint", "Compound"])["TyreLife"].max().reset_index(name="StintLength")
    fig = go.Figure()
    for c in compounds:
        d = s[s["Compound"] == c]
        if not d.empty:
            fig.add_trace(go.Box(y=d["StintLength"], name=c, marker_color=COMPOUND_COLORS[c], boxmean=True))
    fig.update_yaxes(title="Stint Length (laps)")
    return style(fig, showlegend=False)

def pace_bars(laps, compounds):
    p = laps[laps["Compound"].isin(compounds)].groupby("Compound")["LapTimeSeconds"].mean().reset_index()
    p = p.set_index("Compound").reindex([c for c in compounds if c in set(p["Compound"])]).reset_index()
    fig = go.Figure(go.Bar(x=p["Compound"], y=p["LapTimeSeconds"],
                        marker_color=[COMPOUND_COLORS[c] for c in p["Compound"]],
                        text=p["LapTimeSeconds"].round(2), textposition="outside", cliponaxis=False))
    if not p.empty:
        fig.update_yaxes(range=[p["LapTimeSeconds"].min() - 0.5, p["LapTimeSeconds"].max() + 0.5])
    fig.update_yaxes(title="Avg Lap Time (s)")
    return style(fig)

# MODEL INSIGHTS 
def shap_bars(shap):
    d = shap.sort_values("MeanAbsSHAP", ascending=True)
    fig = go.Figure(go.Bar(x=d["MeanAbsSHAP"], y=d["Feature"], orientation="h", marker_color=RED))
    fig.update_xaxes(title="Mean |SHAP value|")
    return style(fig)

def compound_probs(classes, probs):
    fig = go.Figure(go.Bar(x=classes, y=probs, marker_color=[COMPOUND_COLORS.get(c, "#888888") for c in classes],
                        text=[f"{p:.0%}" for p in probs], textposition="outside", cliponaxis=False))
    fig.update_yaxes(title="Probability", range=[0, 1.12])
    return style(fig)

def gauge(pct):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=pct,
        number={"suffix": "%", "font": {"color": "#FFFFFF", "size": 40}},
        gauge={"axis": {"range": [0, 100], "tickcolor": "#CCCCCC"}, "bar": {"color": RED},
               "bgcolor": "#1B1C21", "borderwidth": 1, "bordercolor": GRID,
               "steps": [{"range": [0, 33], "color": "#2A1518"}, {"range": [33, 66], "color": "#2A2415"},
                         {"range": [66, 100], "color": "#152A1A"}]}))
    return style(fig, margin=dict(l=30, r=50, t=30, b=10))

# SEASON
def landscape(optimal, selected=None):
    d = optimal.sort_values("PredictedTotalTime")
    line_c = ["#FFFFFF" if c == selected else "rgba(0,0,0,0)" for c in d["CircuitName"]]
    fig = go.Figure(go.Bar(
        x=d["CircuitName"], y=d["PredictedTotalTime"],
        marker=dict(color=d["NumStops"], colorscale=[[0, "#00D26A"], [1, RED]],
                    line=dict(color=line_c, width=2),
                    colorbar=dict(title="Stops", tickvals=sorted(d["NumStops"].unique()),
                                  tickfont=dict(color="#CCCCCC"))),
        text=d["NumStops"].astype(str) + "-stop", textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{y:,.1f}s<extra></extra>"))
    fig.update_xaxes(title="", tickangle=-45)
    fig.update_yaxes(title="Predicted Race Time (s)")
    return style(fig, margin=dict(l=10, r=10, t=20, b=100))

def cluster_scatter(df, selected=None):
    d = df.copy()
    d["ClusterLabel"] = d["Cluster"].astype(str)
    size = "AvgStintLength" if "AvgStintLength" in d else None
    if size:
        d[size] = d[size].fillna(d[size].median())
    fig = px.scatter(d, x="AvgTrackTemp", y="SafetyCarProbability", color="ClusterLabel", size=size,
                     hover_name="CircuitName", custom_data=["CircuitName"],
                     category_orders={"ClusterLabel": sorted(d["ClusterLabel"].unique())},
                     color_discrete_sequence=CLUSTER_COLORS,
                     labels={"AvgTrackTemp": "Avg Track Temp (°C)", "SafetyCarProbability": "Safety Car Probability",
                             "ClusterLabel": "Cluster"})
    sel = d[d["CircuitName"] == selected]
    if not sel.empty:
        fig.add_trace(go.Scatter(x=sel["AvgTrackTemp"], y=sel["SafetyCarProbability"], mode="markers",
                                 marker=dict(symbol="circle-open", size=34, color="#FFFFFF",
                                             line=dict(width=2)),
                                 hoverinfo="skip", showlegend=False))
    return style(fig)

def compound_usage(counts):
    fig = go.Figure(go.Bar(x=counts["Compound"], y=counts["Count"],
                        marker_color=[COMPOUND_COLORS[c] for c in counts["Compound"]],
                        text=counts["Count"], textposition="outside", cliponaxis=False))
    fig.update_yaxes(title="Total Laps")
    return style(fig)