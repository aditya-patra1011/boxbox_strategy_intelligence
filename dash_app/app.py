from urllib.parse import parse_qs, urlencode

import dash
import dash_bootstrap_components as dbc
from dash import (ALL, Dash, Input, Output, State, callback, ctx, dcc, html,
                no_update, page_container, page_registry)

import data

FONT = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"

app = Dash(__name__, use_pages=True, suppress_callback_exceptions=True,
        external_stylesheets=[dbc.themes.CYBORG, FONT],
        title="BoxBox · F1 Race Centre & Strategy", update_title=None,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])
server = app.server  # gunicorn entry point: gunicorn app:server

CIRCUITS = data.circuits()

# Two sections share one app. Every page registers with section="race" or section="lab".
SECTIONS = {"race": ("Race Centre", "/"), "lab": ("Strategy Lab", "/strategy")}
TAGLINES = {"race": "F1 Race Centre", "lab": "F1 Strategy Intelligence"}


def section_pages(section):
    pages = [p for p in page_registry.values() if p.get("section") == section]
    return sorted(pages, key=lambda p: p.get("order", 99))


def section_of(pathname):
    for p in page_registry.values():
        if p["path"] == pathname:
            return p.get("section", "lab")
    return "race"


def nav_links(section):
    return [dcc.Link([html.Span(p.get("icon", "•"), className="bb-nav-ico"), html.Span(p["name"])],
                    id={"type": "nav", "path": p["path"]}, href=p["path"], className="bb-nav")
            for p in section_pages(section)]


def topbar():
    tabs = [dcc.Link(name, id={"type": "section", "key": key}, href=path, className="bb-section-tab")
            for key, (name, path) in SECTIONS.items()]
    return html.Header(html.Nav(tabs, className="bb-section-tabs"), className="bb-topbar")


def sidebar():
    return html.Aside([
        html.Div([html.Div("BOX", className="bb-logo-a"), html.Div("BOX", className="bb-logo-b")],
                className="bb-logo"),
        html.Div(id="bb-tagline", className="bb-tag"),
        html.Div([
            html.Div("CIRCUIT", className="bb-side-label"),
            dcc.Dropdown(id="circuit-dd", options=CIRCUITS, value=CIRCUITS[0] if CIRCUITS else None,
                        clearable=False, searchable=True, className="bb-dd"),
        ], id="lab-circuit"),
        html.Div("NAVIGATE", className="bb-side-label"),
        html.Nav(nav_links("race"), id="nav-race", className="bb-navlist"),
        html.Nav(nav_links("lab"), id="nav-lab", className="bb-navlist"),
        html.Div([
            html.Div("TYRE COMPOUNDS", className="bb-side-label"),
            html.Div([html.Span("Soft", className="bb-pill bb-soft"), html.Span("Medium", className="bb-pill bb-medium"),
                    html.Span("Hard", className="bb-pill bb-hard")], className="bb-pills"),
        ], id="lab-tyres"),
        html.Div("Unofficial project. Not affiliated with Formula 1, the FIA or any team. "
                "Strategy Lab models use 2024 season data.", className="bb-disclaimer"),
    ], className="bb-sidebar")


def serve_layout():
    return html.Div([dcc.Location(id="url", refresh=False), sidebar(),
                    html.Main([topbar(), page_container], className="bb-main")], className="bb-shell")


app.layout = serve_layout


# ── shareable URL <-> circuit selector (ONE callback, so Dash sees no dependency cycle) ──
@callback(Output("circuit-dd", "value"), Output("url", "search"),
          Input("url", "search"), Input("circuit-dd", "value"))
def sync_circuit(search, value):
    if ctx.triggered_id == "circuit-dd":          # user picked a circuit -> update the URL
        new = "?" + urlencode({"circuit": value}) if value else ""
        return no_update, (no_update if new == (search or "") else new)
    q = parse_qs((search or "").lstrip("?")).get("circuit", [None])[0]   # page load / link opened
    return (q if q in CIRCUITS and q != value else no_update), no_update


# Strategy Lab links carry the selected circuit; Race Centre links stay clean.
@callback(Output({"type": "nav", "path": ALL}, "href"),
        Output({"type": "nav", "path": ALL}, "className"),
        Input("circuit-dd", "value"), Input("url", "pathname"))
def nav_state(circuit, pathname):
    paths = [o["id"]["path"] for o in ctx.outputs_list[0]]
    qs = "?" + urlencode({"circuit": circuit}) if circuit else ""
    return ([p + qs if section_of(p) == "lab" else p for p in paths],
            ["bb-nav bb-nav-active" if p == pathname else "bb-nav" for p in paths])


@callback(Output({"type": "section", "key": ALL}, "href"),
        Output({"type": "section", "key": ALL}, "className"),
        Output("nav-race", "style"), Output("nav-lab", "style"),
        Output("lab-circuit", "style"), Output("lab-tyres", "style"),
        Output("bb-tagline", "children"),
        Input("circuit-dd", "value"), Input("url", "pathname"))
def section_state(circuit, pathname):
    current = section_of(pathname)
    keys = [o["id"]["key"] for o in ctx.outputs_list[0]]
    qs = "?" + urlencode({"circuit": circuit}) if circuit else ""
    hrefs = [SECTIONS[k][1] + (qs if k == "lab" else "") for k in keys]
    classes = ["bb-section-tab bb-section-tab-active" if k == current else "bb-section-tab" for k in keys]
    show, hide = {}, {"display": "none"}
    in_lab = current == "lab"
    return (hrefs, classes, hide if in_lab else show, show if in_lab else hide,
            show if in_lab else hide, show if in_lab else hide, TAGLINES[current])


if __name__ == "__main__":
    app.run(debug=True, port=8050)
