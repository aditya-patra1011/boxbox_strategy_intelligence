import dash

from ui import coming_soon

dash.register_page(__name__, path="/analysis", name="Race Analysis", title="Race Analysis · BoxBox", order=2, icon="📈", section="race")

layout = coming_soon("Race Analysis", "How the tyres and the pace really behaved in the latest race.", 11, [
    "Actual tyre degradation against the BoxBox model prediction",
    "Pace evolution across the race",
])
