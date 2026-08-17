import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

BASE = r'C:\Users\adity\Desktop\BoxBox'

st.set_page_config(page_title="Tire Analysis — BoxBox", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: radial-gradient(ellipse at top left, #14161A 0%, #0A0A0C 55%, #050506 100%);
        color: #E8E8E8;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #17181C 0%, #0F1013 100%);
        border-right: 1px solid #232428;
    }

    section[data-testid="stSidebar"] > div:first-child {
        border-bottom: 1px solid #2A2B30;
        padding-bottom: 10px;
        margin-bottom: 10px;
    }

    h1 {
        font-weight: 800;
        letter-spacing: -0.5px;
    }

    h2, h3 {
        font-weight: 700;
        letter-spacing: -0.3px;
        position: relative;
        padding-left: 14px;
    }

    h2::before, h3::before {
        content: "";
        position: absolute;
        left: 0;
        top: 6px;
        bottom: 6px;
        width: 4px;
        background: linear-gradient(180deg, #E8002D, #FF4D6D);
        border-radius: 2px;
    }

    hr {
        border: none;
        border-top: 1px solid #232428;
        margin: 28px 0;
    }

    .strategy-card {
        background: linear-gradient(145deg, #1B1C21 0%, #151619 100%);
        border-radius: 14px;
        padding: 22px;
        border: 1px solid #26272C;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.45);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        margin-bottom: 10px;
    }

    .strategy-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.6);
    }

    .risk-low { border-top: 4px solid #00C853; }
    .risk-medium { border-top: 4px solid #FFB300; }
    .risk-high { border-top: 4px solid #E8002D; }

    .compound-soft { color: #FF3B3B; font-weight: 700; }
    .compound-medium { color: #FFD500; font-weight: 700; }
    .compound-hard { color: #E0E0E0; font-weight: 700; }

    /* Selectbox / inputs */
    div[data-baseweb="select"] > div {
        background-color: #1B1C21 !important;
        border-color: #2A2B30 !important;
        border-radius: 8px !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #E8002D, #B8001F);
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }

    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0A0A0C; }
    ::-webkit-scrollbar-thumb { background: #2A2B30; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

COMPOUND_COLORS = {'SOFT': '#FF3B3B', 'MEDIUM': '#FFD500', 'HARD': '#E0E0E0'}

def hex_to_rgba(hex_color, alpha=0.2):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'


@st.cache_data
def load_engineered_laps():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'engineered_laps.csv'))

@st.cache_data
def load_survival_curves():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'survival_curves.csv'))

@st.cache_data
def load_degradation_profiles():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'degradation_profiles.csv'))


circuit = st.session_state.get('circuit', None)

if circuit is None:
    st.warning("Select a circuit from the main page first.")
    st.stop()

st.title(f"📊 Tire Analysis — {circuit}")

laps = load_engineered_laps()
circuit_laps = laps[laps['CircuitName'] == circuit]

survival = load_survival_curves()
degradation = load_degradation_profiles()
circuit_degradation = degradation[degradation['CircuitName'] == circuit]


# ── DEGRADATION CURVES ────────────────────────────────────────
st.subheader("Tire Degradation Curves")
st.caption("Predicted lap time as tire age increases, per compound.")

fig1 = go.Figure()
for compound in ['SOFT', 'MEDIUM', 'HARD']:
    comp_data = circuit_laps[circuit_laps['Compound'] == compound]
    if comp_data.empty:
        continue
    fig1.add_trace(go.Scatter(
        x=comp_data['TyreLife'], y=comp_data['LapTimeSeconds'],
        mode='markers', marker=dict(color=COMPOUND_COLORS[compound], size=4, opacity=0.3),
        name=f'{compound} (laps)', showlegend=False
    ))

    profile = circuit_degradation[circuit_degradation['Compound'] == compound]
    if not profile.empty:
        deg_rate = profile.iloc[0]['DegradationRate']
        avg_time = profile.iloc[0]['AvgLapTime']
        avg_tyre_life = profile.iloc[0]['AvgTyreLife']
        x_line = [0, comp_data['TyreLife'].max() if not comp_data.empty else 40]
        y_line = [avg_time - deg_rate * avg_tyre_life + deg_rate * x for x in x_line]
        fig1.add_trace(go.Scatter(
            x=x_line, y=y_line, mode='lines',
            line=dict(color=COMPOUND_COLORS[compound], width=3),
            name=f'{compound} ({deg_rate:+.3f}s/lap)'
        ))

fig1.update_layout(
    plot_bgcolor='#0D0D0D', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#CCCCCC'),
    xaxis=dict(title='Tire Age (laps)', gridcolor='#2A2A2A'),
    yaxis=dict(title='Lap Time (s)', gridcolor='#2A2A2A'),
    legend=dict(bgcolor='rgba(0,0,0,0)'), height=450
)
st.plotly_chart(fig1, use_container_width=True)

st.divider()


# ── KAPLAN-MEIER SURVIVAL CURVES ──────────────────────────────
st.subheader("Tire Survival Probability")
st.caption("Probability the tire is still competitive at a given age, with confidence bands.")

fig2 = go.Figure()
compounds_shown = []
for compound in ['SOFT', 'MEDIUM', 'HARD']:
    curve_data = survival[
        (survival['CircuitName'] == circuit) & (survival['Compound'] == compound)
    ].sort_values('TyreAge')

    if curve_data.empty:
        continue

    compounds_shown.append(compound)

for compound in ['SOFT', 'MEDIUM', 'HARD']:
    curve_data = survival[
        (survival['CircuitName'] == circuit) & (survival['Compound'] == compound)
    ].sort_values('TyreAge')

    if curve_data.empty:
        continue

    fig2.add_trace(go.Scatter(
        x=curve_data['TyreAge'], y=curve_data['CI_Upper'],
        mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    fig2.add_trace(go.Scatter(
        x=curve_data['TyreAge'], y=curve_data['CI_Lower'],
        mode='lines', line=dict(width=0), fill='tonexty',
        fillcolor=hex_to_rgba(COMPOUND_COLORS[compound], alpha=0.2),
        showlegend=False, hoverinfo='skip'
    ))
    fig2.add_trace(go.Scatter(
        x=curve_data['TyreAge'], y=curve_data['SurvivalProbability'],
        mode='lines', line=dict(color=COMPOUND_COLORS[compound], width=3, shape='hv'),
        name=compound
    ))

missing = set(['SOFT', 'MEDIUM', 'HARD']) - set(compounds_shown)
if missing:
    st.caption(f"⚠️ Insufficient stint data to compute a reliable survival curve for: {', '.join(sorted(missing))}")

fig2.update_layout(
    plot_bgcolor='#0D0D0D', paper_bgcolor='#0D0D0D', font=dict(color='#CCCCCC'),
    xaxis=dict(title='Tire Age (laps)', gridcolor='#2A2A2A'),
    yaxis=dict(title='Survival Probability', gridcolor='#2A2A2A', range=[0, 1.05]),
    legend=dict(bgcolor='rgba(0,0,0,0)'), height=450
)
st.plotly_chart(fig2, use_container_width=True)

st.divider()


# ── STINT LENGTH DISTRIBUTION ─────────────────────────────────
st.subheader("Real-World Stint Length Distribution")
st.caption("How long drivers actually ran on each compound at this circuit in 2024.")

stint_lengths = circuit_laps.groupby(
    ['Driver', 'Stint', 'Compound']
)['TyreLife'].max().reset_index()
stint_lengths.columns = ['Driver', 'Stint', 'Compound', 'StintLength']

fig3 = go.Figure()
for compound in ['SOFT', 'MEDIUM', 'HARD']:
    comp_stints = stint_lengths[stint_lengths['Compound'] == compound]
    if comp_stints.empty:
        continue
    fig3.add_trace(go.Box(
        y=comp_stints['StintLength'], name=compound,
        marker_color=COMPOUND_COLORS[compound]
    ))

fig3.update_layout(
    plot_bgcolor='#0D0D0D', paper_bgcolor='#0D0D0D', font=dict(color='#CCCCCC'),
    yaxis=dict(title='Stint Length (laps)', gridcolor='#2A2A2A'),
    showlegend=False, height=400
)
st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── COMPOUND PACE COMPARISON ───────────────────────────────────
st.subheader("Compound Pace Comparison")
st.caption("Average lap time per compound at this circuit.")

pace_data = circuit_laps.groupby('Compound')['LapTimeSeconds'].mean().reset_index()
pace_data = pace_data[pace_data['Compound'].isin(['SOFT', 'MEDIUM', 'HARD'])]

fig4 = go.Figure(go.Bar(
    x=pace_data['Compound'], y=pace_data['LapTimeSeconds'],
    marker_color=[COMPOUND_COLORS[c] for c in pace_data['Compound']],
    text=pace_data['LapTimeSeconds'].round(2),
    textposition='outside'
))

y_min = pace_data['LapTimeSeconds'].min() - 0.5
y_max = pace_data['LapTimeSeconds'].max() + 0.5

fig4.update_layout(
    plot_bgcolor='#0D0D0D', paper_bgcolor='#0D0D0D', font=dict(color='#CCCCCC'),
    yaxis=dict(title='Avg Lap Time (s)', gridcolor='#2A2A2A', range=[y_min, y_max]),
    xaxis=dict(title=''), height=400
)
st.plotly_chart(fig4, use_container_width=True)
#C:\Users\adity\Desktop\BoxBox\dashboard
#python -m streamlit run app.py