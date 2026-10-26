from functools import lru_cache

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import ClientsideFunction, Input, Output, Patch, State, callback, clientside_callback, dcc, html

import figures as F
import race_data as R
from ui import CONFIG, card, message, page_title

dash.register_page(__name__, path="/live", name="Race Live", title="Race Live · BoxBox", order=1, icon="📡", section="race")

CHUNK = 120                 # seconds of replay per block of car samples sent to the browser
RATES = [1, 5, 20, 60]
TYRE_CLASS = {"SOFT": "bb-soft", "MEDIUM": "bb-medium", "HARD": "bb-hard", "INTERMEDIATE": "bb-inter", "WET": "bb-wet"}


def session_frames(key):
    """A session's tables, cached until the session is ingested again."""
    stamp = R.query("SELECT ingested_utc FROM sessions WHERE session_key = ?", (key,))
    return _frames(key, stamp["ingested_utc"].iloc[0] if not stamp.empty else None)


@lru_cache(maxsize=2)
def _frames(key, ingested):
    f = {t: R.session_table(t, key) for t in ("laps", "stints", "pits", "race_control", "positions", "intervals",
                                               "session_drivers")}
    start = R.query("SELECT date_start FROM sessions WHERE session_key = ?", (key,))["date_start"].iloc[0]
    for t in ("positions", "intervals"):                      # replay seconds, worked out once
        f[t] = f[t].assign(t=R.seconds_since(start, f[t]["date"]))
    f["stint_index"] = R.stint_index(f["stints"])
    f["pit_laps"] = f["pits"].groupby("driver_number")["lap_number"].apply(list).to_dict() if not f["pits"].empty else {}
    return f


def driver_meta(session, drivers):
    """{driver_number: {code, colour, team}} using our team colours (via that round's results)."""
    res = R.results(session["season"]) if session["season"] else pd.DataFrame()
    team = {}
    if not res.empty:
        r = res[res["round"] == session["round"]]
        team = dict(zip(r["number"].astype(int), r["constructor_id"]))
    return {int(d["driver_number"]): {"code": d["code"], "team": d["team_name"],
                                      "colour": F.TEAM_COLORS.get(team.get(int(d["driver_number"])),
                                                                  f"#{d['team_colour']}" if d["team_colour"] else "#9A9CA5")}
            for _, d in drivers.iterrows()}


def layout(**_):
    session = R.latest_session()
    if not session:
        return html.Div([page_title("Race Live", "Replays the latest session, or follows it live while it runs."),
                         message("No session stored yet. From the repo root run: python -m ingest.session, then reload.",
                                 "warn")], className="bb-fade")
    key = session["session_key"]
    f = session_frames(key)
    starts = R.lap_starts(f["laps"], session["date_start"])
    total = int(session["total_laps"] or max(starts, default=0))
    last_lap = f["laps"][f["laps"]["lap_number"] == total]
    t_end = (max(R.seconds_since(session["date_start"], last_lap["date_start"]) + last_lap["lap_duration"].fillna(0))
             if not last_lap.empty else max(starts.values()))
    meta_drivers = driver_meta(session, f["session_drivers"])
    by_lap = R.positions_by_lap(f["laps"], f["positions"])
    order = by_lap[by_lap["lap_number"] == by_lap["lap_number"].max()]["driver_number"].tolist() if not by_lap.empty else []
    order += [n for n in meta_drivers if n not in order]
    top3 = order[:3]
    codes = {n: m["code"] for n, m in meta_drivers.items()}
    periods = R.neutralisations(f["race_control"])
    race = R.races(session["season"]).set_index("round").loc[session["round"]] if session["round"] else None
    title = race["race_name"] if race is not None else session["session_name"]

    meta = {"t_start": starts.get(1, 0) - 5, "t_end": round(t_end + 20, 1), "chunk": CHUNK, "total_laps": total,
            "lap_starts": starts, "drivers": meta_drivers}

    return html.Div([
        page_title(f"Race Live · {title} {session['season'] or ''}".strip(),
                   "A replay of the latest race, from OpenF1's free data (it appears about 30 minutes after the "
                   "chequered flag). Press play, pick a speed, or drag to any lap."),
        html.Div(neutral_chips(periods), className="bb-neutral-chips"),
        html.Div([
            html.Button("▶ Play", id="rl-play", n_clicks=0, className="bb-btn"),
            dbc.RadioItems(id="rl-rate", value=20, inline=True, className="bb-radio",
                           options=[{"label": f"{r}×", "value": r} for r in RATES]),
            html.Div(id="rl-label", className="bb-replay-label"),
            html.Div(dcc.Slider(1, total, 1, value=1, id="rl-lap", updatemode="mouseup",
                                marks={l: str(l) for l in range(0, total + 1, 10) if l} | {1: "1", total: str(total)},
                                tooltip={"placement": "bottom"}), className="bb-replay-slider"),
        ], className="bb-replay-bar"),
        dbc.Row([
            dbc.Col(card("Track", "Every car at the replay time, in team colour. Drivers picked below are drawn larger.",
                         dcc.Graph(id="rl-track", figure=F.track_live(R.outline_xy(session["circuit_id"])),
                                   config={**CONFIG, "displayModeBar": False}, style={"height": "520px"})), lg=7),
            dbc.Col(card("Running order", "Position and gap to the leader at the start of the current lap.",
                         html.Div(id="rl-board")), lg=5),
        ], className="g-3"),
        card("Speed", "The last 60 seconds for the drivers you pick, like a live ticker. Dotted lines mark the leader "
             "starting each lap.", [
            html.Div([html.Span("Drivers", className="bb-ctl-label"),
                      dcc.Dropdown(id="rl-drivers", multi=True, value=top3, className="bb-dd",
                                   options=[{"label": f"{codes[n]} · {meta_drivers[n]['team']}", "value": n} for n in order])],
                     className="bb-controls"),
            dcc.Graph(id="rl-speed", figure=F.speed_ticker(), config={**CONFIG, "displayModeBar": False}),
        ]),
        card("Tyre stints", "Every driver's tyres through the race, in finishing order. Shaded laps were run under a "
             "Safety Car (SC), Virtual Safety Car (VSC) or red flag.",
             dcc.Graph(id="rl-stints", figure=F.stint_chart(f["stints"], order, codes, periods, total),
                       config={**CONFIG, "displayModeBar": False})),
        card("Lap chart", "Position at the end of every lap. The drivers picked above are in team colour.",
             dcc.Graph(id="rl-lapchart", figure=F.lap_chart(by_lap, codes, {n: m["colour"] for n, m in meta_drivers.items()},
                                                            top3, periods, total),
                       config={**CONFIG, "displayModeBar": False})),
        dcc.Interval(id="rl-tick", interval=250, disabled=True),
        dcc.Store(id="rl-meta", data=meta),
        dcc.Store(id="rl-session", data={"key": key, "circuit": session["circuit_id"], "start": session["date_start"],
                                         "season": session["season"], "round": session["round"]}),
        dcc.Store(id="rl-clock", data={"t": meta["t_start"], "playing": False}),
        dcc.Store(id="rl-need", data=None),
        dcc.Store(id="rl-chunk", data=None),
    ], className="bb-fade")


def neutral_chips(periods):
    if periods.empty:
        return [html.Span("No Safety Car, VSC or red flag in this race", className="bb-cell-sub")]
    chips = []
    for p in periods.itertuples():
        laps = f"lap {p.start_lap}" if p.start_lap == p.end_lap else f"laps {p.start_lap}–{p.end_lap}"
        length = f"{p.laps} lap{'s' if p.laps != 1 else ''}"
        if p.kind == "RED":
            length += f", {p.minutes:.0f} min stopped"
        chips.append(html.Span([html.B(p.name), f" · {laps} ({length})"], className=f"bb-neutral bb-neutral-{p.kind.lower()}"))
    return chips


clientside_callback(
    ClientsideFunction("replay", "clock"),
    Output("rl-clock", "data"), Output("rl-play", "children"), Output("rl-tick", "disabled"),
    Output("rl-lap", "value"), Output("rl-need", "data"), Output("rl-label", "children"),
    Input("rl-tick", "n_intervals"), Input("rl-play", "n_clicks"), Input("rl-rate", "value"), Input("rl-lap", "value"),
    State("rl-clock", "data"), State("rl-meta", "data"), State("rl-need", "data"),
)

clientside_callback(
    ClientsideFunction("replay", "draw"),
    Output("rl-track", "figure"), Output("rl-speed", "figure"),
    Input("rl-clock", "data"), Input("rl-chunk", "data"), Input("rl-drivers", "value"),
    State("rl-meta", "data"), State("rl-track", "figure"), State("rl-speed", "figure"),
)


@callback(Output("rl-chunk", "data"), Input("rl-need", "data"), State("rl-session", "data"))
def load_chunk(need, s):
    """Car samples covering 60 s of history before, and 2 minutes after, the current block."""
    if need is None or not s:
        return dash.no_update
    return R.replay_chunk(s["key"], s["circuit"], need * CHUNK - CHUNK, need * CHUNK + CHUNK + 30)


@callback(Output("rl-board", "children"), Output("rl-stints", "figure"), Output("rl-lapchart", "figure"),
          Input("rl-lap", "value"), State("rl-session", "data"), State("rl-meta", "data"))
def on_lap(lap, s, meta):
    lap = lap or 1
    f = session_frames(s["key"])
    t = meta["lap_starts"].get(str(lap), meta["t_start"])
    board = R.board_at(t + 1, s["start"], f["positions"], f["intervals"], f["session_drivers"])
    rows = []
    for r in board.to_dict("records"):
        n = int(r["driver_number"])
        info = meta["drivers"].get(str(n), {})
        compound, age = R.tyre_on_lap(f["stint_index"], n, lap)
        stops = sum(1 for l in f["pit_laps"].get(n, []) if l < lap)
        rows.append(html.Tr([
            html.Td(int(r["position"]), className="bb-pos"),
            html.Td(html.Div([html.Span(className="bb-swatch", style={"background": info.get("colour", "#9A9CA5")}),
                              html.Div([html.Div(r["code"]), html.Div(info.get("team", ""), className="bb-cell-sub")])],
                             className="bb-cell-name")),
            html.Td(r["gap"], className="bb-pts" if r["position"] == 1 else "bb-muted"),
            html.Td([html.Span(compound.title()[0], className=f"bb-pill bb-pill-sm {TYRE_CLASS.get(compound, '')}",
                               title=compound.title()), html.Span(f" {age} laps", className="bb-muted")]
                    if compound else ""),
            html.Td(stops or "", className="bb-muted"),
        ]))
    table = html.Div(html.Table([html.Thead(html.Tr([html.Th(h) for h in ["Pos", "Driver", "Gap", "Tyre", "Stops"]])),
                                 html.Tbody(rows)], className="bb-table"), className="bb-table-wrap bb-board")
    stints, lapchart = Patch(), Patch()
    stints["layout"]["shapes"][0]["x0"] = stints["layout"]["shapes"][0]["x1"] = lap - 0.5
    lapchart["layout"]["shapes"][0]["x0"] = lapchart["layout"]["shapes"][0]["x1"] = lap
    return table, stints, lapchart


@callback(Output("rl-lapchart", "figure", allow_duplicate=True), Input("rl-drivers", "value"),
          State("rl-session", "data"), State("rl-meta", "data"), State("rl-lap", "value"), prevent_initial_call=True)
def highlight_lapchart(chosen, s, meta, lap):
    f = session_frames(s["key"])
    drivers = {int(k): v for k, v in meta["drivers"].items()}
    return F.lap_chart(R.positions_by_lap(f["laps"], f["positions"]), {n: d["code"] for n, d in drivers.items()},
                       {n: d["colour"] for n, d in drivers.items()}, chosen or [], R.neutralisations(f["race_control"]),
                       meta["total_laps"], lap or 1)
