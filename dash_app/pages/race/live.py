import dash

from ui import coming_soon

dash.register_page(__name__, path="/live", name="Race Live", title="Race Live · BoxBox", order=1, icon="📡", section="race")

layout = coming_soon("Race Live", "Replays the latest session, or follows it live while it runs.", 10, [
    "Track map with every car moving on it",
    "Speed line chart over the race for the drivers you pick",
    "Tyre stints per driver, with Safety Car, VSC and red-flag laps shaded",
    "Lap chart of position changes",
])
