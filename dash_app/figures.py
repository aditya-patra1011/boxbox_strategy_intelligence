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

# RACE CENTRE · STANDINGS
# Approximate team colours (plain hex values, no logos). Colour is never the only cue:
# highlighted lines are also labelled at their end, and the table sits beside the chart.
TEAM_COLORS = {"mercedes": "#27F4D2", "ferrari": "#E8002D", "mclaren": "#FF8000", "red_bull": "#3671C6",
               "rb": "#6692FF", "alpine": "#FF87BC", "haas": "#B6BABD", "audi": "#52E252",
               "williams": "#64C4FF", "aston_martin": "#229971", "cadillac": "#C9B037"}
MUTED = "#3A3D46"
LABEL_INK = "#C9CBD2"


def _spread(values, gap):
    """Nudge sorted label positions apart so end labels never sit on top of each other."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = list(values)
    for a, b in zip(order, order[1:]):
        out[b] = max(out[b], out[a] + gap)
    return out


def standings_lines(df, key, label, highlight, metric="points", race_names=None):
    """Points (or championship position) after every round. Highlighted entries get their
    team colour and an end label; everyone else is a thin grey line for context."""
    if df.empty:
        return empty("No standings yet. Run: python -m ingest")
    race_names = race_names or {}
    fig = go.Figure()
    rest = [k for k in df[key].unique() if k not in highlight]
    teams_drawn, ends = set(), []
    for k in rest + [h for h in highlight if h in set(df[key])]:
        d = df[df[key] == k].sort_values("round")
        on = k in highlight
        team = d["constructor_id"].iloc[-1]
        dash = "dash" if on and team in teams_drawn else "solid"     # second highlighted teammate
        if on:
            teams_drawn.add(team)
        name = d[label].iloc[-1]
        fig.add_trace(go.Scatter(
            x=d["round"], y=d[metric], mode="lines", name=name, showlegend=on,
            line=dict(color=TEAM_COLORS.get(team, "#9A9CA5") if on else MUTED, width=2.5 if on else 1, dash=dash),
            customdata=list(zip(d["round"].map(race_names).fillna(""), d["position_text"], d["points"])),
            hovertemplate="<b>%{fullData.name}</b><br>R%{x} · %{customdata[0]}"
                          "<br>%{customdata[2]:.0f} pts · P%{customdata[1]}<extra></extra>"))
        if on:
            ends.append((name, d["round"].iloc[-1], d[metric].iloc[-1]))

    span = (df[metric].max() - df[metric].min()) or 1
    reverse = metric == "position"
    ys = _spread([-y if reverse else y for _, _, y in ends], span * 0.04)
    for (name, x, _), y in zip(ends, ys):
        fig.add_annotation(x=x, y=-y if reverse else y, text=name, showarrow=False, xanchor="left", xshift=8,
                           font=dict(size=12, color=LABEL_INK))

    rounds = sorted(df["round"].unique())
    fig.update_xaxes(title="Round", tickvals=rounds, ticktext=[f"R{r}" for r in rounds], range=[0.7, rounds[-1] + 0.9])
    top = df[metric].max()
    if reverse:
        fig.update_yaxes(title="Championship position", range=[top + 0.7, 0.3], tickvals=[1, 5, 10, 15, 20])
    else:
        fig.update_yaxes(title="Points", range=[-top * 0.03, top * 1.06])
    style(fig, margin=dict(l=10, r=10, t=40, b=10), hovermode="closest")
    # No animated transition: with one, switching points <-> position keeps the old y-axis and
    # Plotly replays queued figures. The traces change shape completely, so there's nothing to animate.
    fig.layout.transition = None
    return fig.update_layout(legend=dict(orientation="h", y=1.08, x=0))


# RACE CENTRE · CIRCUITS
def track_outline(xy, color="#E8E8E8", width=4, height=None):
    """A circuit drawn from our own telemetry outline: no axes, equal scale, nothing else."""
    if not xy:
        return empty("No track outline yet. Run: python -m ingest.circuits")
    x, y = xy
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=width),
                               hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[x[0]], y=[y[0]], mode="markers", hoverinfo="skip",
                             marker=dict(color=RED, size=9, line=dict(color="#0E1014", width=2))))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    style(fig, margin=dict(l=4, r=4, t=4, b=4), showlegend=False)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    fig.layout.transition = None
    if height:
        fig.update_layout(height=height)
    return fig
