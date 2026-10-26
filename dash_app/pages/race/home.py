from urllib.parse import urlencode

import dash
from dash import dcc

from ui import coming_soon

dash.register_page(__name__, path="/", name="Home", title="Race Centre · BoxBox", order=0, icon="🏠", section="race")


def layout(circuit=None, **_):
    # Old shared links pointed Strategy at "/?circuit=X"; send them to its new home.
    if circuit:
        return dcc.Location(id="legacy-redirect", href="/strategy?" + urlencode({"circuit": circuit}), refresh=True)
    return coming_soon("Race Centre", "The current race weekend, the latest results and the season so far.", 9, [
        "Current or next race, with a link to its strategy plans in Strategy Lab",
        "Latest race result: gaps, final tyre and the fastest-lap driver",
        "Season results heatmap: every driver's finishing position at every round",
    ])
