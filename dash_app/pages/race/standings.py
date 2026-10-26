from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html

import figures as F
import race_data as R
from ui import card, graph, kpi, message, page_title

dash.register_page(__name__, path="/standings", name="Standings", title="Standings · BoxBox", order=3, icon="🏆", section="race")

TOP_N = 5
# kind -> (standings loader, id column, short label column)
KINDS = {"drivers": (R.driver_standings, "driver_id", "code"),
         "constructors": (R.constructor_standings, "constructor_id", "team")}


def short(race_name):
    return race_name.replace(" Grand Prix", " GP")


def layout(**_):
    season = R.current_season()
    if season is None:
        return html.Div([
            page_title("Championship Standings", "Drivers' and Constructors' Championships for the current season."),
            message("No Race Centre data yet. From the repo root run: python -m ingest --season 2026, then reload.", "warn"),
        ], className="bb-fade")

    races, done = R.races(season), R.completed_rounds(season)
    if not done:
        return html.Div([page_title(f"Championship Standings · {season}", "The season hasn't started yet."),
                         message("Standings appear after the first race.")], className="bb-fade")
    last = races[races["round"] == done[-1]].iloc[0]
    updated = datetime.fromisoformat(R.last_updated()).strftime("%d %b %Y, %H:%M UTC")

    drivers = R.latest_table(R.driver_standings(season), "driver_id")
    teams = R.latest_table(R.constructor_standings(season), "constructor_id")
    left = R.points_left(races, done, "drivers")
    fight = R.contenders(drivers, left)
    future = races[races["round"] > done[-1]]

    def leader(table, name, other):
        top, second = table.iloc[0], table.iloc[1]
        return name(top), f"{top['points']:.0f} pts · +{top['points'] - second['points']:.0f} over {other(second)}"

    d_name, d_sub = leader(drivers, lambda r: r["family_name"], lambda r: r["family_name"])
    t_name, t_sub = leader(teams, lambda r: r["team"], lambda r: r["team"])
    kpis = [
        kpi("Drivers' leader", d_name, d_sub, F.TEAM_COLORS.get(drivers.iloc[0]["constructor_id"], F.RED)),
        kpi("Constructors' leader", t_name, t_sub, F.TEAM_COLORS.get(teams.iloc[0]["constructor_id"], F.RED)),
        kpi("Still in the title fight", f"{len(fight)} driver{'s' if len(fight) != 1 else ''}" if len(fight) > 1
            else "Decided", f"{left} points left for one driver"),
        kpi("Season progress", f"{len(done)} / {len(races)}",
            f"rounds done · {int(future['sprint_utc'].notna().sum())} sprints left"),
    ]

    return html.Div([
        page_title(f"Championship Standings · {season}",
                   f"After round {done[-1]} of {len(races)}, the {last['race_name']}. Data updated {updated}."),
        dbc.Row(kpis, className="g-3 mb-4"),
        html.Div([
            html.Div([html.Span("Championship", className="bb-ctl-label"),
                      dbc.RadioItems(id="sd-kind", value="drivers", inline=True, className="bb-radio",
                                     options=[{"label": "Drivers", "value": "drivers"},
                                              {"label": "Constructors", "value": "constructors"}])]),
            html.Div([html.Span("Chart", className="bb-ctl-label"),
                      dbc.RadioItems(id="sd-metric", value="points", inline=True, className="bb-radio",
                                     options=[{"label": "Points", "value": "points"},
                                              {"label": "Position", "value": "position"}])]),
            html.Div([html.Span("Highlight", className="bb-ctl-label"),
                      dcc.Dropdown(id="sd-highlight", multi=True, className="bb-dd", placeholder="Pick up to 6")],
                     className="bb-ctl-grow"),
        ], className="bb-controls"),
        dbc.Row([
            dbc.Col(card("Standings", f"After round {done[-1]}. Arrows show places gained or lost since round {done[-1] - 1}.",
                         html.Div(id="sd-table")), lg=5),
            dbc.Col(card("Season so far", "Highlighted entries in team colour; everyone else in grey for context.",
                         graph("sd-chart", 540)), lg=7),
        ], className="g-3"),
        dcc.Store(id="sd-season", data=season),
    ], className="bb-fade")


@callback(Output("sd-highlight", "options"), Output("sd-highlight", "value"),
          Input("sd-kind", "value"), Input("sd-season", "data"))
def highlight_options(kind, season):
    load, key, label = KINDS[kind]
    table = R.latest_table(load(season), key)
    names = table["team"] if kind == "constructors" else table["family_name"]
    options = [{"label": n, "value": k} for k, n in zip(table[key], names)]
    return options, table[key].head(TOP_N).tolist()


@callback(Output("sd-table", "children"), Output("sd-chart", "figure"),
          Input("sd-kind", "value"), Input("sd-metric", "value"), Input("sd-highlight", "value"),
          Input("sd-season", "data"))
def update(kind, metric, highlight, season):
    load, key, label = KINDS[kind]
    standings = load(season)
    highlight = (highlight or [])[:6]
    table = R.latest_table(standings, key)
    order = [k for k in table[key] if k in highlight]          # draw/label in championship order
    names = {r["round"]: short(r["race_name"]) for _, r in R.races(season).iterrows()}
    fig = F.standings_lines(standings, key, label, order, metric, names)
    return standings_table(table, kind, key, set(highlight)), fig


def change_cell(n):
    if n > 0:
        return html.Td(f"▲{n}", className="bb-up", title=f"Gained {n}")
    if n < 0:
        return html.Td(f"▼{-n}", className="bb-down", title=f"Lost {-n}")
    return html.Td("–", className="bb-flat")


def standings_table(table, kind, key, highlight):
    swatch = lambda team: html.Span(className="bb-swatch", style={"background": F.TEAM_COLORS.get(team, "#9A9CA5")})
    if kind == "drivers":
        head = ["Pos", "", "Driver", "Wins", "Pts", "Gap"]
        rows = [html.Td(html.Div([swatch(r["constructor_id"]), html.Div([
                    html.Div([r["family_name"], " ", html.Span(r["code"], className="bb-muted")],
                             title=f"{r['given_name']} {r['family_name']}"),
                    html.Div(r["team"], className="bb-cell-sub")])], className="bb-cell-name"))
                for _, r in table.iterrows()]
    else:
        head = ["Pos", "", "Team", "Wins", "Pts", "Gap"]
        rows = [html.Td(html.Div([swatch(r["constructor_id"]), r["team"]], className="bb-cell-name"))
                for _, r in table.iterrows()]

    body = []
    for name, (_, r) in zip(rows, table.iterrows()):
        body.append(html.Tr([html.Td(r["position_text"], className="bb-pos"), change_cell(r["change"]), name,
                             html.Td(f"{r['wins']:.0f}"), html.Td(f"{r['points']:.0f}", className="bb-pts"),
                             html.Td("–" if r["gap"] == 0 else f"-{r['gap']:.0f}", className="bb-muted")],
                            className="bb-row-on" if r[key] in highlight else None))
    thead = html.Thead(html.Tr([html.Th(h) for h in head]))
    return html.Div(html.Table([thead, html.Tbody(body)], className="bb-table"), className="bb-table-wrap")
