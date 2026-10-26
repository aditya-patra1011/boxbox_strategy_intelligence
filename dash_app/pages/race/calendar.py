import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

import figures as F
import race_data as R
from ui import CONFIG, kpi, message, page_title

dash.register_page(__name__, path="/calendar", name="Calendar", title="Calendar · BoxBox", order=4, icon="🗓️", section="race")

STROKE = {"completed": "#8A8C94", "upcoming": "#E8E8E8", "live": "#FFFFFF"}


def short(name):
    return name.replace(" Grand Prix", " GP")


def day(t):
    return f"{t.day} {t:%b}"


def when(t):
    return f"{t:%a} {t.day} {t:%b} · {t:%H:%M} UTC"


def weekend_dates(race):
    ss = R.sessions(race)
    first, last = ss[0][1], ss[-1][1]
    return day(last) if first.date() == last.date() else f"{day(first)} – {day(last)}"


def layout(**_):
    season = R.current_season()
    if season is None:
        return html.Div([page_title("Season Calendar", "Every round of the season, past, live and upcoming."),
                         message("No Race Centre data yet. From the repo root run: python -m ingest --season 2026, "
                                 "then reload.", "warn")], className="bb-fade")
    at = R.now()
    cal = R.calendar(season, at)
    live, upcoming, done = (cal[cal["status"] == s] for s in ("live", "upcoming", "completed"))
    nxt = upcoming.iloc[0] if not upcoming.empty else None
    winners = done["winner"].dropna()

    if not live.empty:
        focus = kpi("Live now", short(live.iloc[0]["race_name"]), "race weekend in progress", F.RED)
    elif nxt is not None:
        days = (R.sessions(nxt)[0][1] - at).days
        focus = kpi("Next race", short(nxt["race_name"]),
                    f"{weekend_dates(nxt)} · {'starts today' if days < 1 else f'in {days} day' + ('s' if days > 1 else '')}", F.RED)
    else:
        focus = kpi("Next race", "Season over", None, F.RED)
    kpis = [
        kpi("Rounds completed", f"{len(done)} / {len(cal)}", f"{len(upcoming) + len(live)} to go"),
        focus,
        kpi("Different winners", f"{winners.nunique()}", f"from {len(winners)} races"),
        kpi("Sprint weekends", f"{int(cal['sprint_utc'].notna().sum())}", "with a Saturday sprint race"),
    ]

    sections = []
    for title, rows in (("Live Now", live), ("Upcoming Races", upcoming), ("Completed Races", done)):
        if rows.empty:
            continue
        sections += [html.H3(title, className="bb-section"),
                     html.Div([race_card(r, at, nxt is not None and r["round"] == nxt["round"]) for _, r in rows.iterrows()],
                              className="bb-cal-grid")]

    return html.Div([
        page_title(f"Season Calendar · {season}",
                   "Every round of the season. Open a card for the circuit, its history and the weekend schedule. "
                   "Times are UTC."),
        dbc.Row(kpis, className="g-3 mb-2"),
        *sections,
        dbc.Modal([dbc.ModalHeader(dbc.ModalTitle(id="cal-title")), dbc.ModalBody(id="cal-body")],
                  id="cal-modal", size="xl", centered=True, scrollable=True, className="bb-modal"),
        dcc.Store(id="cal-season", data=season),
    ], className="bb-fade")


def race_card(r, at, is_next):
    status = r["status"]
    badges = [html.Span(f"R{r['round']}", className="bb-chip-round")]
    if status == "live":
        badges.append(html.Span([html.Span(className="bb-live-dot"), "LIVE"], className="bb-badge-live"))
    elif is_next:
        badges.append(html.Span("NEXT", className="bb-badge-next"))
    if R.utc(r.get("sprint_utc")):
        badges.append(html.Span("SPRINT", className="bb-badge-sprint"))

    if status == "completed":
        foot = (html.Div([html.Span(className="bb-swatch", style={"background": F.TEAM_COLORS.get(r["winner_team_id"], "#9A9CA5")}),
                          html.Span(r["winner"], className="bb-cal-winner"),
                          html.Span(r["winner_team"], className="bb-cell-sub")], className="bb-cal-foot")
                if r["winner"] else html.Div("Result pending", className="bb-cal-foot bb-muted"))
    elif status == "upcoming":
        foot = html.Div(f"Race · {when(R.utc(r['race_utc']))}", className="bb-cal-foot bb-muted")
    else:
        s = R.session_now(r, at)
        if s and s[2]:
            foot = html.Div([html.Span(className="bb-live-dot"), f"{s[0]} on track now"], className="bb-cal-foot bb-live-text")
        elif s:
            foot = html.Div(f"Next: {s[0]} · {when(s[1])}", className="bb-cal-foot bb-muted")
        else:
            foot = html.Div("Race just finished", className="bb-cal-foot bb-muted")

    img = F.track_svg(R.outline_xy(r["circuit_id"]), STROKE[status])
    return html.Button([
        html.Div(badges, className="bb-cal-badges"),
        html.Img(src=img, alt=f"{r['circuit_name']} track outline", className="bb-cal-track") if img
        else html.Div("No outline", className="bb-cal-track bb-muted"),
        html.Div(short(r["race_name"]), className="bb-cal-name"),
        html.Div(f"{r['locality']}, {r['country']} · {weekend_dates(r)}", className="bb-cell-sub"),
        foot,
    ], id={"type": "cal-card", "round": int(r["round"])},
        className=f"bb-cal-card bb-cal-{status}" + (" bb-cal-next" if is_next else ""), n_clicks=0)


@callback(Output("cal-modal", "is_open"), Output("cal-title", "children"), Output("cal-body", "children"),
          Input({"type": "cal-card", "round": ALL}, "n_clicks"), State("cal-season", "data"),
          prevent_initial_call=True)
def open_details(clicks, season):
    if not ctx.triggered_id or not any(clicks):
        return no_update, no_update, no_update
    rnd = ctx.triggered_id["round"]
    at = R.now()
    race = R.calendar(season, at).set_index("round").loc[rnd].to_dict()
    race["round"] = rnd
    return True, f"Round {rnd} · {race['race_name']}", details(race, season, at)


def fact(label, value, note=None):
    return html.Div([html.Div(label, className="bb-kpi-label"), html.Div(value, className="bb-fact-value"),
                     html.Div(note, className="bb-cell-sub") if note else None], className="bb-fact")


def details(race, season, at):
    facts = R.circuits()
    f = facts.set_index("circuit_id").loc[race["circuit_id"]] if not facts.empty and race["circuit_id"] in set(facts["circuit_id"]) else None
    fig = F.track_outline(R.outline_xy(race["circuit_id"]), height=380)

    info = [fact("Circuit", race["circuit_name"], f"{race['locality']}, {race['country']}")]
    if f is not None:
        info += [
            fact("First Formula 1 Grand Prix", f"{f['first_gp']}",
                 "New for this season" if f["first_gp"] == season else f"{season - f['first_gp']} years ago"),
            fact("Grands Prix held here", f"{f['gp_count']}", "World Championship races, to date"),
            fact("Lap length (racing line)", f"{f['racing_line_km']:.2f} km",
                 f"Measured from the {f['outline_year']} pole lap; about 1–2% under the official length"),
            fact("Race distance", f"{f['race_laps']} laps", f"At the {f['race_laps_season']} race"),
        ]

    lab = R.STRATEGY_CIRCUIT.get(race["circuit_id"])
    strategy = (dcc.Link("View strategy plans in Strategy Lab →", href=f"/strategy?circuit={lab}", className="bb-btn bb-link-btn")
                if lab else html.Div("No Strategy Lab model for this circuit yet (models use 2024 data).", className="bb-cell-sub"))

    schedule = []
    for name, start, end in R.sessions(race):
        state = "Done" if at > end else ("Live" if at >= start else "")
        schedule.append(html.Tr([html.Td(name), html.Td(when(start), className="bb-muted"),
                                 html.Td(state, className="bb-live-text" if state == "Live" else "bb-muted")]))

    blocks = [dbc.Row([
        dbc.Col(dcc.Graph(figure=fig, config={**CONFIG, "displayModeBar": False}, style={"height": "380px"}), lg=7),
        dbc.Col([html.Div(info, className="bb-facts"), html.Div(strategy, className="mt-3")], lg=5),
    ], className="g-3")]

    if race["status"] == "completed":
        pod = R.podium(season, race["round"])
        res = R.results(season)
        fl = res[(res["round"] == race["round"]) & (res["fastest_lap_rank"] == 1)]
        rows = [html.Tr([html.Td(f"P{int(p['position'])}", className="bb-pos"),
                         html.Td(html.Div([html.Span(className="bb-swatch", style={"background": F.TEAM_COLORS.get(p["constructor_id"], "#9A9CA5")}),
                                           html.Div([html.Div(f"{p['given_name']} {p['family_name']}"),
                                                     html.Div(p["team"], className="bb-cell-sub")])], className="bb-cell-name")),
                         html.Td(p["time_text"] or p["status"], className="bb-muted")]) for _, p in pod.iterrows()]
        blocks += [html.H5("Podium", className="bb-card-title mt-4"),
                   html.Table(html.Tbody(rows), className="bb-table"),
                   html.Div(f"Fastest lap: {fl.iloc[0]['given_name']} {fl.iloc[0]['family_name']} · "
                            f"{fl.iloc[0]['fastest_lap_time']} on lap {int(fl.iloc[0]['fastest_lap_lap'])}",
                            className="bb-cell-sub mt-2") if not fl.empty else None]

    blocks += [html.H5("Weekend schedule", className="bb-card-title mt-4"),
               html.Table(html.Tbody(schedule), className="bb-table")]
    return blocks
