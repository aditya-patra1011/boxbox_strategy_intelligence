import dash

from ui import coming_soon

dash.register_page(__name__, path="/standings", name="Standings", title="Standings · BoxBox", order=3, icon="🏆", section="race")

layout = coming_soon("Championship Standings", "Drivers' and Constructors' Championships for the current season.", 3, [
    "Driver and constructor tables",
    "Cumulative points line chart, round by round",
    "Toggle to championship position by round",
])
