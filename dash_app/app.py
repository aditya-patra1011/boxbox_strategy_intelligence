from urllib.parse import parse_qs, urlencode

import dash
import dash_bootstrap_components as dbc
from dash import (ALL, Dash, Input, Output, State, callback, ctx, dcc, html,
                no_update, page_container, page_registry)

import data

FONT = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"

app = Dash(__name__, use_pages=True, suppress_callback_exceptions=True,
        external_stylesheets=[dbc.themes.CYBORG, FONT],
        title="BoxBox · F1 Strategy Intelligence", update_title=None,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])
server = app.server  # gunicorn entry point: gunicorn app:server

CIRCUITS = data.circuits()


def sidebar():
    pages = sorted(page_registry.values(), key=lambda p: p.get("order", 99))
    links = [dcc.Link([html.Span(p.get("icon", "•"), className="bb-nav-ico"), html.Span(p["name"])],
                    id={"type": "nav", "path": p["path"]}, href=p["path"], className="bb-nav")
            for p in pages]
    return html.Aside([
        html.Div([html.Div("BOX", className="bb-logo-a"), html.Div("BOX", className="bb-logo-b")],
                className="bb-logo"),
        html.Div("F1 Strategy Intelligence", className="bb-tag"),
        html.Div("CIRCUIT", className="bb-side-label"),
        dcc.Dropdown(id="circuit-dd", options=CIRCUITS, value=CIRCUITS[0] if CIRCUITS else None,
                    clearable=False, searchable=True, className="bb-dd"),
        html.Div("NAVIGATE", className="bb-side-label"),
        html.Nav(links, className="bb-navlist"),
        html.Div("TYRE COMPOUNDS", className="bb-side-label"),
        html.Div([html.Span("Soft", className="bb-pill bb-soft"), html.Span("Medium", className="bb-pill bb-medium"),
                html.Span("Hard", className="bb-pill bb-hard")], className="bb-pills"),
        html.Div("Unofficial project. Not affiliated with Formula 1, the FIA or any team. 2024 season data.",
                className="bb-disclaimer"),
    ], className="bb-sidebar")


def serve_layout():
    return html.Div([dcc.Location(id="url", refresh=False), sidebar(),
                    html.Main(page_container, className="bb-main")], className="bb-shell")


app.layout = serve_layout


# ── shareable URL <-> circuit selector ────────────────────────────
# ── shareable URL <-> circuit selector (ONE callback, so Dash sees no dependency cycle) ──
@callback(Output("circuit-dd", "value"), Output("url", "search"),
          Input("url", "search"), Input("circuit-dd", "value"))
def sync_circuit(search, value):
    if ctx.triggered_id == "circuit-dd":          # user picked a circuit -> update the URL
        new = "?" + urlencode({"circuit": value}) if value else ""
        return no_update, (no_update if new == (search or "") else new)
    q = parse_qs((search or "").lstrip("?")).get("circuit", [None])[0]   # page load / link opened
    return (q if q in CIRCUITS and q != value else no_update), no_update


@callback(Output({"type": "nav", "path": ALL}, "href"),
        Output({"type": "nav", "path": ALL}, "className"),
        Input("circuit-dd", "value"), Input("url", "pathname"))
def nav_state(circuit, pathname):
    paths = [o["id"]["path"] for o in ctx.outputs_list[0]]
    qs = "?" + urlencode({"circuit": circuit}) if circuit else ""
    return ([p + qs for p in paths],
            ["bb-nav bb-nav-active" if p == pathname else "bb-nav" for p in paths])


if __name__ == "__main__":
    app.run(debug=True, port=8050)