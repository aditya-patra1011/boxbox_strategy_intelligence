"""
Live-weekend banner and "new data is in" check, shared by the Race Centre pages.

Free data can't show a session while it runs, so during a race weekend the pages say so and
keep showing the latest stored race. A light check every minute notices when the watcher
(python -m ingest.watch) stores a newer race and offers to load it.
"""

from dash import MATCH, Input, Output, State, callback, dcc, html

import race_data as R

CHECK_EVERY_MS = 60_000


def banner(season, showing=None):
    """The live-weekend notice, or None outside a race weekend."""
    s = R.live_status(season)
    if not s:
        return None
    now = R.now()
    if s["running"]:
        lead = f"{s['session']} is on track now."
    elif s["session"]:
        lead = f"Next up: {s['session']}."
    else:
        lead = "The race has just finished."
    when = s["race_data_at"]
    if now < when:
        arrival = (f"The race replay, timing and analysis appear about 30 minutes after the chequered flag "
                   f"(around {when:%a} {when.day} {when:%b}, {when:%H:%M} UTC), when OpenF1's data becomes free.")
    else:
        arrival = "The race data should be free about now; it appears here as soon as the watcher stores it."
    return html.Div([
        html.Span([html.Span(className="bb-live-dot"), "LIVE"], className="bb-badge-live"),
        html.Div([html.B(f"{s['race']} weekend. "), lead, " ", arrival,
                  f" Until then this page shows {showing}." if showing else ""], className="bb-live-banner-text"),
    ], className="bb-live-banner")


def watch(page, session_key):
    """Components that check once a minute whether a newer race has been stored."""
    return [dcc.Interval(id={"type": "nd-tick", "page": page}, interval=CHECK_EVERY_MS),
            dcc.Store(id={"type": "nd-key", "page": page}, data=session_key),
            html.Div(id={"type": "nd-msg", "page": page})]


@callback(Output({"type": "nd-msg", "page": MATCH}, "children"),
          Input({"type": "nd-tick", "page": MATCH}, "n_intervals"),
          State({"type": "nd-key", "page": MATCH}, "data"), State("url", "pathname"),
          prevent_initial_call=True)
def check_for_new_data(_, shown_key, path):
    latest = R.latest_session()
    if not latest or latest["session_key"] == shown_key:
        return None
    name = R.races(latest["season"]).set_index("round")["race_name"].get(latest["round"], "A new race") \
        if latest["season"] and latest["round"] else "A new race"
    return html.Div([html.B(f"{name} data is in. "),
                     html.A("Load it", href=path or "/", className="bb-btn bb-link-btn bb-btn-sm")],
                    className="bb-msg bb-new-data")
