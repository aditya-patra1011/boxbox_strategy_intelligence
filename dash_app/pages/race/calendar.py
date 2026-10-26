import dash

from ui import coming_soon

dash.register_page(__name__, path="/calendar", name="Calendar", title="Calendar · BoxBox", order=4, icon="🗓️", section="race")

layout = coming_soon("Season Calendar", "Every round of the season, past, live and upcoming.", 5, [
    "A card for every race with its track map",
    "Race winner under every completed race",
    "LIVE tag on the current race and an Upcoming Races section",
    "Track details when you open a card",
])
