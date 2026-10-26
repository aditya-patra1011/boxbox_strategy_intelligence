from urllib.parse import urlencode

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, callback, dcc, html, no_update

import figures as F
import race_data as R
from ui import CONFIG, card, message, page_title

dash.register_page(__name__, path="/", name="Home", title="Race Centre · BoxBox", order=0, icon="🏠", section="race")

TYRE_CLASS = {"SOFT": "bb-soft", "MEDIUM": "bb-medium", "HARD": "bb-hard", "INTERMEDIATE": "bb-inter", "WET": "bb-wet"}


def short(name):
    return name.replace(" Grand Prix", " GP")


def layout(circuit=None, **_):
    # Old shared links pointed Strategy at "/?circuit=X"; send them to its new home.
    if circuit:
        return dcc.Location(id="legacy-redirect", href="/strategy?" + urlencode({"circuit": circuit}), refresh=True)

    season = R.current_season()
    if season is None:
        return html.Div([page_title("Race Centre", "The current race weekend, the latest results and the season so far."),
                         message("No Race Centre data yet. From the repo root run: python -m ingest --season 2026, "
                                 "then reload.", "warn")], className="bb-fade")
    at = R.now()
    cal = R.calendar(season, at)
    done = cal[cal["status"] == "completed"]
    focus = cal[cal["status"] == "live"]
    focus = focus if not focus.empty else cal[cal["status"] == "upcoming"]

    options = [{"label": f"R{r['round']} · {short(r['race_name'])}", "value": int(r["round"])}
               for _, r in done.iloc[::-1].iterrows()]
    return html.Div([
        page_title("Race Centre", f"{season} season · the race weekend, the latest results and the season so far."),
        hero(focus.iloc[0], at) if not focus.empty else message(f"The {season} season is over."),
        card("Race results", "Gap to the winner, interval to the car ahead, places gained from the grid and the tyre "
             "each driver finished on.", [
            html.Div([html.Span("Race", className="bb-ctl-label"),
                      dcc.Dropdown(id="home-race", options=options, value=options[0]["value"] if options else None,
                                   clearable=False, className="bb-dd bb-dd-race")], className="bb-controls"),
            html.Div(id="home-table"),
        ], className="mt-4"),
        card("Season at a glance", "Every driver's finish at every round, in championship order. Brighter red is a better "
             "result. Click a race to see its full results above.",
             dcc.Graph(id="home-grid", figure=season_grid_figure(season), config={**CONFIG, "displayModeBar": False})),
        dcc.Store(id="home-season", data=season),
    ], className="bb-fade")


def hero(race, at):
    live = race["status"] == "live"
    sessions = R.sessions(race)
    upcoming = [(n, s, e) for n, s, e in sessions if e >= at]
    lab = R.STRATEGY_CIRCUIT.get(race["circuit_id"])
    facts = R.circuits()
    f = facts.set_index("circuit_id").loc[race["circuit_id"]] if not facts.empty and race["circuit_id"] in set(facts["circuit_id"]) else None

    if live:
        now_on = R.session_now(race, at)
        status = (f"{now_on[0]} on track now" if now_on and now_on[2] else
                  f"Next: {now_on[0]} in {R.countdown(now_on[1] - at)}" if now_on else "Race just finished")
    else:
        status = f"{upcoming[0][0]} starts in {R.countdown(upcoming[0][1] - at)}" if upcoming else ""

    schedule = [html.Div([html.Span(n, className="bb-hero-session"),
                          html.Span(f"{s:%a} {s.day} {s:%b} · {s:%H:%M} UTC", className="bb-muted")],
                         className="bb-hero-row" + (" bb-hero-row-next" if upcoming and n == upcoming[0][0] else "")
                         + (" bb-hero-row-done" if e < at else ""))
                for n, s, e in sessions]

    buttons = [dcc.Link("View strategy plans for this race →", href="/strategy?" + urlencode({"circuit": lab}),
                        className="bb-btn bb-link-btn")] if lab else \
        [html.Div("No Strategy Lab model for this circuit yet (models use 2024 data).", className="bb-cell-sub")]
    buttons.append(dcc.Link("Season calendar", href="/calendar", className="bb-btn-ghost"))

    return html.Div([
        html.Div([
            html.Div([html.Span([html.Span(className="bb-live-dot"), "LIVE NOW"] if live else "NEXT RACE",
                                className="bb-badge-live" if live else "bb-badge-next"),
                      html.Span(f"Round {race['round']}", className="bb-chip-round")], className="bb-cal-badges"),
            html.H2(race["race_name"], className="bb-hero-title"),
            html.Div(f"{race['circuit_name']} · {race['locality']}, {race['country']}", className="bb-subtitle"),
            html.Div(status, className="bb-hero-status" + (" bb-live-text" if live else "")),
            html.Div(schedule, className="bb-hero-schedule"),
            html.Div(buttons, className="bb-hero-buttons"),
        ], className="bb-hero-text"),
        html.Div([
            html.Img(src=F.track_svg(R.outline_xy(race["circuit_id"]), "#E8E8E8", width=420, height=260, line=4),
                     alt=f"{race['circuit_name']} track outline", className="bb-hero-track"),
            html.Div(f"{f['racing_line_km']:.2f} km racing line · {f['race_laps']} laps · first Grand Prix {f['first_gp']}"
                     if f is not None else "", className="bb-cell-sub"),
        ], className="bb-hero-map"),
    ], className="bb-hero" + (" bb-hero-live" if live else ""))


def season_grid_figure(season):
    pos, labels = R.season_grid(season)
    drivers = R.query("SELECT driver_id, code FROM drivers")
    names = dict(zip(drivers["driver_id"], drivers["code"])) if not drivers.empty else {}
    race_names = {int(r["round"]): short(r["race_name"]) for _, r in R.races(season).iterrows()}
    return F.season_heatmap(pos, labels, names, race_names)


@callback(Output("home-race", "value"), Input("home-grid", "clickData"), State("home-race", "options"),
          prevent_initial_call=True)
def pick_from_grid(click, options):
    if not click:
        return no_update
    rnd = click["points"][0]["x"]
    return rnd if any(o["value"] == rnd for o in options) else no_update


@callback(Output("home-table", "children"), Input("home-race", "value"), State("home-season", "data"))
def show_race(rnd, season):
    if rnd is None:
        return message("No completed races yet this season.")
    t = R.race_table(R.results(season), rnd, R.final_tyres(season))
    return results_table(t)


def results_table(t):
    head = ["Pos", "+/-", "Driver", "Gap", "Interval", "Tyre", "Pts"]
    rows = []
    for _, r in t.iterrows():
        gained = r["gained"]
        change = (html.Td(f"▲{int(gained)}", className="bb-up") if gained and gained > 0 else
                  html.Td(f"▼{-int(gained)}", className="bb-down") if gained and gained < 0 else
                  html.Td("–", className="bb-flat"))
        driver = html.Div([
            html.Span(className="bb-swatch", style={"background": F.TEAM_COLORS.get(r["constructor_id"], "#9A9CA5")}),
            html.Div([html.Div([f"{r['given_name']} {r['family_name']} ", html.Span(r["code"], className="bb-muted"),
                                html.Span("FASTEST LAP", className="bb-chip-fastest",
                                          title=f"Fastest lap: {r['fastest_lap_time']} on lap {int(r['fastest_lap_lap'])}")
                                if r["fastest_lap"] else None]),
                      html.Div(r["team"], className="bb-cell-sub")]),
        ], className="bb-cell-name")
        tyre = (html.Span(r["final_tyre"].title(), className=f"bb-pill {TYRE_CLASS.get(r['final_tyre'], '')}")
                if isinstance(r["final_tyre"], str) else html.Span("–", className="bb-muted"))
        rows.append(html.Tr([html.Td(r["position_text"] if r["position_text"].isdigit() else "–", className="bb-pos"),
                             change, html.Td(driver),
                             html.Td(r["gap"], className="bb-pts" if r["position"] == 1 else None),
                             html.Td(r["interval"], className="bb-muted"), html.Td(tyre),
                             html.Td(f"{r['points']:.0f}" if r["points"] else "", className="bb-muted")]))
    return html.Div(html.Table([html.Thead(html.Tr([html.Th(h) for h in head])), html.Tbody(rows)],
                               className="bb-table"), className="bb-table-wrap")
