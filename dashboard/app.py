import streamlit as st
import pandas as pd
import plotly.io as pio
import os
import json 

BASE = r'C:\Users\adity\Desktop\BoxBox'

st.set_page_config(
    page_title="BOXBOX - F1 Strategy Intelligence",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800
    &display=swap');

    html, body, [class*="css"]{
        font-family: 'Inter', sans-serif;
    }

    .stApp{
        background: radial-gradient(ellipse at top left, #14161A 0%, #0A0A0C 55%, #050506
        100%);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #17181C 0%, #0F1013 100%);
        border-right: 1px solid #232428;
    }

    section[data-testid="stSdiebar"] > div:first-child {
        border-bottom: 1px solid #2A2B30;
        padding-bottom: 10px;
        margin-bottom: 10px;
    }

    h1 {
        font-weight: 800;
        letter-spacing: -0.5px;
    }

    h2 {
        font-weight: 700;
        letter-spacing: -0.3px;
        position: relative;
        padding-left: 14px;
    }

    h2::before, h3::before {
        content = "";
        position = absolute;
        left = 0;
        top: 6px;
        bottom: 6px;
        width: 4px;
        background: linear-gradient(180deg, #E8002D, #FF4D6D);
        border-radius: 2px;
    }

    hr {
        border: None;
        border-top: 1px solid #232428;
        margin: 28px 0;
    }

    .strategy-card {
        background: linear-gradient(145deg, #1B1C21 0%, #151619 100%);
        border-radius: 14px;
        padding: 22px;
        border: 1px solid #26272C;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.45);
        transistion: transform 0.15s ease, box-shadow 0.15s ease;
        margin-bottom: 10px;
    }

    .strategy-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.6);
    }

    .risk-low { border-top: 4px solid #00C853;}
    .risk-medium { border-top: 4px solid #FFB300;}
    .risk-high { border-top: 4px solid #E8002D;}

    .compound-soft { color: #FF3B3B; font-weight: 700;}
    .compound-medium { color: #FFD500; font-weight: 700;}
    .compound-hard { color: #E0E0E0; font-weight: 700;}

    /* Selectbox / inputs */
    div[data-baseweb="select"] > div {
        background-color: #1B1C21 !important;
        background-color: #2A2B30 !important;
        background-radius: 8px !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #E8002D, #B8001F);
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }

    :: -webkit-scrollbar { width: 8px; }
    :: -webkit-scrollbar-track { background: #0A0A0C; }
    :: -webkit-scrollbar-thumb { background: #2A2B30; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_plan_abc():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'plan_abc.csv'))

@st.cache_data
def load_feature_store():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'feature_store.csv'))

@st.cache_data
def load_degradation_profiles():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'degradation_profiles.csv'))

@st.cache_data
def load_survival_curves():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'survival_curves.csv'))

@st.cache_data
def load_shap_values():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'shap_values.csv'))

@st.cache_data
def load_circuit_clusters():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'circuit_clusters.csv'))

@st.cache_data
def dbscan_summary():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'dbscan_anomaly_summary.csv'))

def load_circuit_map(circuit_name):
    safe_name = circuit_name.lower().replace(' ', '_')
    path = os.path.join(BASE, 'circuit_maps', f'{safe_name}.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return pio.from_json(f.read())
    return None

feature_store = load_feature_store()
circuits = sorted(feature_store['CircuitName'].unique())

with st.sidebar:
    st.image(os.path.join(BASE, "assets", "logo.png"), width=70)
    st.markdown("## BOXBOX")
    st.caption("F1 Strategy Itelligence - 2024 season")
    st.divider()

    selected_circuit = st.selectbox("Select Circuit", circuits, key='circuit_selector')

    st.divider()
    st.markdown("**Tire Compound Legend**")
    #Soft tyre image
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image(os.path.join(BASE, "assets", "compound_icons", "soft.png"), width=28)
    with col2:
        st.markdown("Soft")
    #Medium tyre image
    col1, col2 = st.columns([1, 4])
    with col2:
        st.image(os.path.join(BASE, "assets", "compound_icons", "medium.png"), width=28)
    with col2:
        st.markdown("Medium")
    #Hard tyre image
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image(os.path.join(BASE, "assets", "compound_icons", "hard.png"), width=28)
    with col2:
        st.markdown("Hard")

st.session_state['circuit'] = selected_circuit

st.write("Circuit found:", circuits)

col_logo, col_title = st.columns([1,8])
with col_logo:
    st.image(os.path.join(BASE, "assets", "logo.png"), width=90)
with col_title:
    st.markdown("# BOXBOX - F1 Strategy Intelligence")
    st.caption("Because some pit walls need help")

st.markdown(f"### {selected_circuit} - Strategy Intelligence")

#Circuit Map
st.subheader("Circuit Map")
circuit_fig = load_circuit_map(selected_circuit)
if circuit_fig is not None:
    st.plotly_chart(circuit_fig, use_container_width=True)
else:
    st.info("Circuit map not available for this track.")

st.divider()

#Strategy cards
st.subheader("Race Strategy Plans")

plan_abc = load_plan_abc()
circuit_plans = plan_abc[plan_abc['CircuitName'] == selected_circuit]

if circuit_plans.empty:
    st.warning("No strategy data available for this sircuit")
else:
    cols = st.columns(3)
    plan_order = ['A', 'B', 'C']
    plan_titles = {
        'A': 'PLAN A - Optimal',
        'B': 'PLAN B - Real-World',
        'C': 'PLAN C - Alternative',
    }

    for i, label in enumerate(plan_order):
        plan_row = circuit_plans[circuit_plans['PlanLabel'] == label]
        if plan_row.empty:
            continue
        plan_row = plan_row.iloc[0]

        risk_class = f"risk-{plan_row['RiskLevel'].lower()}"

        with cols[i]:
            st.markdown(f"""
            <div class = "strategy-card {risk_class}">
                <h4>{plan_titles[label]}</h4>
                <p><b>{plan_row['NumStops']}</b> stops(s) &nbsp; | &nbsp; Risk: <b>
                {plan_row['RiskLevel']} </b> ({plan_row['strategy']})</p>
                <p style="font-size: 18px;">{plan_row['strategy']}</p>
                <p>Predicted Time: <b>{plan_row['PredictedTotalTime']:.1f}s</b></p>
            </div>
            """, unsafe_allow_html=True)

st.divider()
st.caption("BOXBOX - Because some pit walls needs help. Built on 2024 F1 season data.")