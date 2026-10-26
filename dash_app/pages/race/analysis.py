from functools import lru_cache

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

import data
import figures as F
import live_status
import race_data as R
from ui import CONFIG, card, kpi, message, page_title

dash.register_page(__name__, path="/analysis", name="Race Analysis", title="Race Analysis · BoxBox", order=2, icon="📈", section="race")


@lru_cache(maxsize=2)
def analysis(key, ingested):
    """Everything the page needs for one stored session, cached until it is ingested again."""
    f = {t: R.session_table(t, key) for t in ("laps", "stints", "pits", "race_control", "session_drivers")}
    periods = R.neutralisations(f["race_control"])
    clean = R.clean_race_laps(f["laps"], f["stints"], f["pits"], periods)
    return f, periods, clean, R.degradation(clean), R.stint_relative(clean), R.race_pace(clean)


def model_rates(circuit_id):
    """The 2024 BoxBox model's degradation rate per compound at this circuit, if it has one."""
    lab = R.STRATEGY_CIRCUIT.get(circuit_id)
    deg = data.degradation()
    if not lab or deg is None or deg.empty:
        return lab, {}
    rows = deg[deg["CircuitName"] == lab]
    return lab, dict(zip(rows["Compound"], rows["DegradationRate"]))


def fmt_lap(s):
    return f"{int(s // 60)}:{s % 60:06.3f}"


def layout(**_):
    session = R.latest_session()
    if not session:
        return html.Div([page_title("Race Analysis", "How the tyres and the pace really behaved in the latest race."),
                         message("No session stored yet. From the repo root run: python -m ingest.session, then reload.",
                                 "warn")], className="bb-fade")
    key = session["session_key"]
    f, periods, clean, rates, rel, pace = analysis(key, session["ingested_utc"])
    drivers = R.session_driver_meta(session, f["session_drivers"], F.TEAM_COLORS)
    codes = {n: d["code"] for n, d in drivers.items()}
    lab, model = model_rates(session["circuit_id"])
    race = R.races(session["season"]).set_index("round").loc[session["round"]] if session["round"] else None
    title = race["race_name"] if race is not None else session["session_name"]
    finish = R.positions_by_lap(f["laps"], R.session_table("positions", key))
    top3 = finish[finish["lap_number"] == finish["lap_number"].max()]["driver_number"].head(3).tolist()
    traps = f["laps"].groupby("driver_number")["st_speed"].max().dropna().sort_values(ascending=False)
    worst = rates.loc[rates["rate"].idxmax()] if not rates.empty else None

    kpis = [
        kpi("Clean laps used", f"{len(clean)}", f"of {f['laps']['lap_duration'].notna().sum()} timed laps"),
        kpi("Best race pace", codes.get(pace["driver_number"].iloc[0], "") if not pace.empty else "–",
            f"median {fmt_lap(pace['pace'].iloc[0])} fuel-corrected" if not pace.empty else None, F.RED),
        kpi("Hardest-hit compound", worst["compound"].title() if worst is not None else "–",
            f"{worst['rate']:+.3f} s per lap of age" if worst is not None else None,
            F.COMPOUND_COLORS.get(worst["compound"], F.RED) if worst is not None else F.RED),
        kpi("Top speed trap", f"{traps.iloc[0]:.0f} km/h" if not traps.empty else "–",
            ", ".join(codes.get(n, str(n)) for n in traps[traps == traps.iloc[0]].index) if not traps.empty else None),
    ]

    if not lab:
        model_note = message("No BoxBox model for this circuit yet (models use 2024 data), so only the measured rates show.")
    else:
        negative = [c.title() for c, v in model.items() if v < 0]
        model_note = message(
            "The hollow markers are the BoxBox model's rates for this circuit, trained on 2024 data under the previous "
            "rules, so treat them as a reference only."
            + (f" Its {' and '.join(negative)} rate{'s are' if len(negative) > 1 else ' is'} negative (tyres getting "
               "faster with age), which isn't physically plausible: the way Phase 3 measures the rate is being reviewed."
               if negative else ""), "warn")

    return html.Div([
        page_title(f"Race Analysis · {title} {session['season'] or ''}".strip(),
                   "How the tyres and the pace really behaved, measured from every clean lap of the latest race."),
        live_status.banner(session["season"], showing=f"the {title} analysis"),
        *live_status.watch("analysis", key),
        dbc.Row(kpis, className="g-3 mb-4"),
        dbc.Row([
            dbc.Col(card("Tyre degradation", "Each dot is a clean lap, against its own stint's average (fuel-corrected). "
                         "Lines are each compound's trend within a stint.",
                         dcc.Graph(figure=F.degradation_scatter(rel, rates), config={**CONFIG, "displayModeBar": False},
                                   style={"height": "420px"})), lg=7),
            dbc.Col(card("Measured vs the BoxBox model", "Seconds lost per lap of tyre age. Further right is faster wear.", [
                dcc.Graph(figure=F.degradation_compare(rates, model), config={**CONFIG, "displayModeBar": False}),
                html.Div([html.Div(f"{r.compound.title()}: {r.stints} stints, {r.laps} laps", className="bb-cell-sub")
                          for r in rates.itertuples()], className="mb-2"),
                model_note,
            ]), lg=5),
        ], className="g-3"),
        card("How it was measured", None, html.Ul([
            html.Li("Dropped: lap 1, pit in and out laps, every lap under a Safety Car, VSC or red flag, wet compounds, "
                    "and laps more than 2 standard deviations above the mean. The same cleaning Phase 2 used for 2024."),
            html.Li(f"Fuel correction: {R.FUEL_PER_LAP} s added per lap completed, as in Phase 2 (0.03 s/kg × 1.8 kg/lap)."),
            html.Li("Rate: the slope of lap time against tyre age within each stint (stints of 5+ clean laps), pooled per "
                    "compound, so differences between drivers don't create a false trend."),
        ], className="bb-soon-list")),
        card("Pace through the race", "Lap times for the drivers you pick. Shaded laps were run under a Safety Car, VSC or "
             "red flag; spikes are pit stops.", [
            html.Div([html.Span("Drivers", className="bb-ctl-label"),
                      dcc.Dropdown(id="ra-drivers", multi=True, value=top3, className="bb-dd",
                                   options=[{"label": f"{d['code']} · {d['team']}", "value": n} for n, d in drivers.items()])],
                     className="bb-controls"),
            dcc.Graph(id="ra-pace", config={**CONFIG, "displayModeBar": False}, style={"height": "420px"}),
        ]),
        dbc.Row([
            dbc.Col(card("Race pace", "Median clean, fuel-corrected lap per driver, as a gap to the best.",
                         dcc.Graph(figure=F.gap_bars(pace["pace"].tolist(), [codes.get(n, str(n)) for n in pace["driver_number"]],
                                                     "Gap to the best median lap (s)"),
                                   config={**CONFIG, "displayModeBar": False})), lg=6),
            dbc.Col(card("Speed trap", "Each driver's highest speed-trap reading in the race.",
                         dcc.Graph(figure=F.gap_bars(traps.tolist(), [codes.get(n, str(n)) for n in traps.index],
                                                     "Slower than the top speed (km/h)", fmt="{:+.0f} km/h"),
                                   config={**CONFIG, "displayModeBar": False})), lg=6),
        ], className="g-3"),
        dcc.Store(id="ra-session", data={"key": key, "ingested": session["ingested_utc"], "total": int(session["total_laps"] or 0)}),
    ], className="bb-fade")


@callback(Output("ra-pace", "figure"), Input("ra-drivers", "value"), State("ra-session", "data"))
def pace_chart(chosen, s):
    f, periods, *_ = analysis(s["key"], s["ingested"])
    session = R.latest_session()
    drivers = R.session_driver_meta(session, f["session_drivers"], F.TEAM_COLORS)
    return F.pace_evolution(f["laps"], chosen or [], {n: d["code"] for n, d in drivers.items()},
                            {n: d["colour"] for n, d in drivers.items()}, periods, s["total"])
