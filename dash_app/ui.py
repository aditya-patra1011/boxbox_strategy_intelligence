"""
Small resuable UI building blocks.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html

import data

CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

def graph(id, height=420):
    return dcc.Loading(dcc.Graph(id=id, config=CONFIG, style={"height": f"{height}px"}),
                    type="dot", color="#E8002D")

def card(title, subtitle=None, body=None, className=""):
    kids = [html.H5(title, className="bb-card-title")]
    if subtitle:
        kids.append(html.P(subtitle, className="bb-card-sub"))
    kids.extend(body if isinstance(body, (list, tuple)) else [body])
    return html.Div(kids, className=f"bb-card {className}".strip())

def card(title, subtitle=None, body=None, className=""):
    kids = [html.H5(title, className="bb-card-title")]
    if subtitle:
        kids.append(html.P(subtitle, className="bb-card-sub"))
    kids.extend(body if isinstance(body, (list, tuple)) else [body])
    return html.Div(kids, className=f"bb-card {className}".strip())

def kpi(label, value, sub=None, accent="#E8002D"):
    return dbc.Col(html.Div([
        html.Div(label, className="bb-kpi-label"),
        html.Div(value, className="bb-kpi-value"),
        html.Div(sub, className="bb-kpi-sub") if sub else None,
    ], className="bb-kpi", style={"--accent": accent}), xs=6, md=True)

def page_title(title, subtitle):
    return html.Div([html.H1(title, className="bb-title"), html.P(subtitle, className="bb-subtitle")],
                    className="bb-page-head")

def pills(text):
    comps = data.parse_compounds(text)
    out = []
    for i, c in enumerate(comps):
        if i:
            out.append(html.Span("›", className="bb-arrow"))
        out.append(html.Span(c.title(), className=f"bb-pill bb-{c.lower()}"))
    return html.Div(out, className="bb-pills")

def message(text, kind="info"):
    return html.Div(text, className=f"bb-msg bb-msg-{kind}")

def coming_soon(title, subtitle, pr, features):
    """Placeholder body for a Race Centre page that a later PR fills in."""
    return html.Div([
        page_title(title, subtitle),
        card("What this page will show", f"Arrives in PR {pr} of the Race Centre plan.",
             html.Ul([html.Li(f) for f in features], className="bb-soon-list")),
    ], className="bb-fade")
