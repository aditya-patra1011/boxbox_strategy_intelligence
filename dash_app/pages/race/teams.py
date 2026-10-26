import dash

from ui import coming_soon

dash.register_page(__name__, path="/teams", name="Teams", title="Teams · BoxBox", order=5, icon="🏎️", section="race")

layout = coming_soon("Teams", "Every team on the grid, their history and their drivers.", 7, [
    "Constructors' and Drivers' titles, including predecessor teams",
    "Current drivers with their racing numbers",
    "Team history as a vertical timeline of iconic moments",
])
