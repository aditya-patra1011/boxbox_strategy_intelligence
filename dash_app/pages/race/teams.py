import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

import figures as F
import race_data as R
from ui import message, page_title

dash.register_page(__name__, path="/teams", name="Teams", title="Teams · BoxBox", order=5, icon="🏎️", section="race")


def colour(team_id):
    return F.TEAM_COLORS.get(team_id, "#9A9CA5")


def layout(**_):
    teams, stats = R.teams(), R.team_stats()
    season = R.current_season()
    if not teams or season is None:
        return html.Div([page_title("Teams", "Every team on the grid, their history and their drivers."),
                         message("Team content or race data is missing. From the repo root run: "
                                 "python -m ingest --season 2026 and python -m ingest.teams, then reload.", "warn")],
                        className="bb-fade")

    lineup = R.team_lineup(season)
    standings = R.latest_table(R.constructor_standings(season), "constructor_id").set_index("constructor_id")
    order = {k: i for i, k in enumerate(standings.index)}
    cards = [team_card(t, stats["teams"].get(t["id"], {}), lineup[lineup["constructor_id"] == t["id"]],
                       standings.loc[t["id"]] if t["id"] in standings.index else None)
             for t in sorted(teams, key=lambda t: order.get(t["id"], 99))]

    return html.Div([
        page_title(f"Teams · {season}",
                   f"In championship order. Titles count predecessor teams; titles to the end of "
                   f"{stats.get('titles_through_season', season - 1)}, wins including {season} so far. "
                   "Open a team for its drivers and history."),
        html.Div(cards, className="bb-team-grid"),
        dbc.Modal([dbc.ModalHeader(dbc.ModalTitle(id="tm-title")), dbc.ModalBody(id="tm-body")],
                  id="tm-modal", size="xl", centered=True, scrollable=True, className="bb-modal"),
        dcc.Store(id="tm-season", data=season),
    ], className="bb-fade")


def stat(value, label):
    return html.Div([html.Div(value, className="bb-team-stat-value"), html.Div(label, className="bb-team-stat-label")],
                    className="bb-team-stat")


def team_card(team, s, drivers, standing):
    pos = f"P{int(standing['position'])} · {standing['points']:.0f} pts" if standing is not None else ""
    return html.Button([
        html.Div([html.Div(team["name"], className="bb-team-name"), html.Span(pos, className="bb-team-pos")],
                 className="bb-team-head"),
        html.Div(team["base"], className="bb-cell-sub"),
        html.Div([stat(len(s.get("constructors_titles", [])), "Constructors'"),
                  stat(len(s.get("drivers_titles", [])), "Drivers'"),
                  stat(s.get("wins", 0), "Wins")], className="bb-team-stats"),
        html.Div([html.Div([html.Span(f"{int(d['number'])}", className="bb-team-num"),
                            html.Span(f"{d['given_name']} {d['family_name']}")], className="bb-team-driver")
                  for _, d in drivers.iterrows()], className="bb-team-drivers"),
    ], id={"type": "team-card", "team": team["id"]}, n_clicks=0, className="bb-team-card",
        style={"--team": colour(team["id"])})


@callback(Output("tm-modal", "is_open"), Output("tm-title", "children"), Output("tm-body", "children"),
          Input({"type": "team-card", "team": ALL}, "n_clicks"), State("tm-season", "data"),
          prevent_initial_call=True)
def open_team(clicks, season):
    if not ctx.triggered_id or not any(clicks):
        return no_update, no_update, no_update
    team = next(t for t in R.teams() if t["id"] == ctx.triggered_id["team"])
    return True, team["name"], details(team, season)


def driver_card(d, team_id):
    born = R.age(d["date_of_birth"]) if d["date_of_birth"] else None
    standing = (f"P{int(d['champ_position'])} in the championship · {d['champ_points']:.0f} pts"
                if pd.notna(d["champ_position"]) else "")
    wins = int(d["season_wins"]) if pd.notna(d["season_wins"]) else 0
    return html.Div([
        html.Div(f"{int(d['number'])}", className="bb-dc-number"),
        html.Div(R.initials(d["given_name"], d["family_name"]), className="bb-dc-initials"),
        html.Div([html.Div(d["given_name"], className="bb-dc-given"),
                  html.Div(d["family_name"], className="bb-dc-family")]),
        html.Div(f"{d['code']} · {d['nationality']}" + (f" · {born}" if born is not None else ""),
                 className="bb-cell-sub"),
        html.Div(standing, className="bb-dc-standing"),
        html.Div(f"{wins} win{'s' if wins != 1 else ''} this season" if wins else "", className="bb-cell-sub"),
    ], className="bb-driver-card", style={"--team": colour(team_id)})


def details(team, season):
    s = R.team_stats()["teams"].get(team["id"], {})
    lineup = R.team_lineup(season)
    drivers = lineup[lineup["constructor_id"] == team["id"]]

    def years(items):
        return ", ".join(str(t["season"]) for t in items) or "None yet"

    lineage, shown = [], set()
    for step in team["lineage"]:
        # A name can return (Renault, Sauber); its wins are summed per name, so show them on its first stint.
        wins = s.get("wins_by_name", {}).get(step["name"]) if step["name"] not in shown else None
        shown.add(step["name"])
        span = f"{step['from']}" if step["from"] == step["to"] else f"{step['from']}–{step['to'] or 'now'}"
        lineage.append(html.Span([html.B(step["name"]), f" {span}",
                                  html.Span(f" · {wins} win{'s' if wins != 1 else ''}", className="bb-muted") if wins else None],
                                 className="bb-lineage-step"))

    first, latest = s.get("first_win"), s.get("latest_win")
    facts = [
        ("Base", team["base"]),
        ("Constructors' titles", f"{len(s.get('constructors_titles', []))} · {years(s.get('constructors_titles', []))}"),
        ("Drivers' titles", f"{len(s.get('drivers_titles', []))} · " + (", ".join(
            f"{t['driver'].split()[-1]} {t['season']}" for t in s.get("drivers_titles", [])) or "None yet")),
        ("Race wins", f"{s.get('wins', 0)}"),
        ("First win", f"{first['race']} {first['season']} · {first['driver']}" + (f" (as {first['as']})" if first["as"] != team["name"] else "")
         if first else "Still waiting"),
        ("Latest win", f"{latest['race']} {latest['season']} · {latest['driver']}" if latest else "Still waiting"),
    ]

    timeline = html.Div([html.Div([
        html.Div(str(e["year"]), className="bb-tl-year"),
        html.Div([html.Div(e["title"], className="bb-tl-title"), html.Div(e["text"], className="bb-tl-text")],
                 className="bb-tl-body"),
    ], className="bb-tl-item") for e in team["timeline"]], className="bb-timeline", style={"--team": colour(team["id"])})

    return [
        html.Div([driver_card(d, team["id"]) for _, d in drivers.iterrows()], className="bb-driver-cards"),
        dbc.Row([
            dbc.Col([html.H5("The team", className="bb-card-title"),
                     html.Div([html.Div([html.Div(k, className="bb-kpi-label"), html.Div(v, className="bb-fact-text")],
                                        className="bb-fact") for k, v in facts], className="bb-facts"),
                     html.H5("Lineage", className="bb-card-title mt-4"),
                     html.Div(lineage, className="bb-lineage"),
                     html.Div(team.get("lineage_note"), className="bb-cell-sub mt-2") if team.get("lineage_note") else None],
                    lg=5),
            dbc.Col([html.H5("Iconic moments", className="bb-card-title"), timeline], lg=7),
        ], className="g-4 mt-2"),
    ]
