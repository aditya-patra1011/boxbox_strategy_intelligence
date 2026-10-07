import os
import inspect
import pandas as pd
import streamlit as st
import plotly.io as pio
import joblib

# Project root: assumes this file lives in <BoxBox>/dashboard/.
# To use a different location, set the BOX_BOX environment variable
BASE = os.environ.get('BOXBOX_BASE') or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

SEASON = "2024"
COMPOUNDS = ['SOFT', 'MEDIUM', 'HARD']
COMPOUND_COLORS = {'SOFT': '#FF3B3B', 'MEDIUM': '#FFD500', 'HARD': '#E0E0E0'}

THEME_CSS = """
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
        font-weight: 700;
        letter-spacing: -0.3px;
        position: relative;
        padding-left: 14px;
    }

    h2::before, h3::before {
        content = "";
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
        transition: transform 0.15s ease, box-shadow 0.15 ease;
        margin-bottom: 10px; 
    }

    .strategy-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.6);
    }

    .risk-low { border-top: 4px solid #00C853; }
    .risk-medium { border-top: 4px solid #FFB300; }
    .risk-high { border-top: 4px solid #E8002D; }

    compound-soft { color: #FF3B3B; font-weight: 700; }
    .compound-medium { color: #FFD500; font-weight: 700; }
    .compound-hard { color: #E0E0E0; font-weight: 700; }

    div[data-basewen="select"] > div {
        background-color: #1B1C21 !important;
        border-color: #2A2B30 !important;
        border-radius: 8px !important;
    }

    .stButton > button {
        background: linear-gradient(135deg, #E8002D, #B8001F);
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }

    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0A0A0C; }
    ::-webkit-scrollbaar-thumb { background: #2A2B30; border-radius: 4px; }
</style>
"""

def apply_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)

# --- DATA LOADERS ----------------------
@st.cache_data
def read_csv(*parts):
    return pd.read_csv(os.path.join(BASE, *parts))

def load_feature_store():
    return read_csv('data', 'processed', 'feature_store.csv')

def load_engineered_laps():
    return read_csv('data', 'processed', 'engineered_laps.csv')

def load_degradation_profiles():
    return read_csv('data', 'processed', 'degradation_profiles.csv')

def load_survival_curves():
    return read_csv('data', 'processed', 'survival_curves.csv')

def load_shap_values():
    return read_csv('data', 'processed', 'shap_values.csv')

def load_plan_abc():
    return read_csv('data', 'processed', 'plan_abc.csv')

def load_circuit_clusters():
    return read_csv('data', 'processed', 'circuit_clusters.csv')

def load_optimal_strategies():
    return read_csv('data', 'outputs', 'optimal_strategies.csv')

def load_comparison():
    return read_csv('data', 'outputs', 'dbscan_vs_manual_comparison.csv')

@st.cache_resource
def load_model(filename):
    return joblib.load(os.path.join(BASE, 'models', filename))

def load_circuit_map(circuit_name):
    safe_name = circuit_name.lower().replace(' ', '_')
    path = os.path.join(BASE, 'circuit_maps', f'{safe_name}.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return pio.from_json(f.read())
    return None


# -- SIDEBAR / BRANDING -----------------------------
def show_logo(width):
    logo_path = os.path.join(BASE, 'assets', 'logo.png')
    if os.path.exists(logo_path):
        st.image(logo_path, width=width)

def sidebar_header():
    show_logo(70)
    st.markdown("## BOXBOX")
    st.caption(f"F1 Strategy Intelligence - {SEASON} season")
    st.divider()

def circuit_selector(circuits):
    '''One shared circuit selector. The choice is kept in session state,
    so it survives switching between pages.'''
    stored = st.session_state.get('circuit', circuits[0])
    index = circuits.index(stored) if stored in circuits else 0
    selected = st.selectbox("Selected Circuit", circuits, index=index, key='circuit_selector')
    st.session_state['circuit'] = selected
    return selected

def compound_legend():
    st.markdown("**Tire Compound Legend**")
    for name in ('Soft', 'Medium', 'Hard'):
        icon = os.path.join(BASE, 'assets', 'compound_icons', f'{name.lower()}.png')
        col_icon, col_text = st.columns([1, 4])
        with col_icon:
            if os.path.exists(icon):
                st.image(icon, width=28)
            else:
                color = COMPOUND_COLORS[name.upper()]
                st.markdown(
                    f'<span style="color: {color}; font-size:22px;">●</span>',
                    unsafe_allow_html=True
                )
        with col_text:
            st.markdown(name)

# --- CHART HELPER ---------------------
# Newer Streamlit versions use width='strech'; older ones use use_container_width
_PLOTLY_HAS_WIDTH = 'width' in inspect.signature(st.plotly_chart).parameters

def show_chart(fig):
    if _PLOTLY_HAS_WIDTH:
        st.plotly_chart(fig, width='stretch')
    else:
        st.plotly_chart(fig, use_container_width=True)

# ---- SMALL HELPERS ----------------------
def style_fig(fig, height=450, **layout):
    fig.update_layout(
        plot_bgcolor='#0D0D0D', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#CCCCCC'), legend=dict(bgcolor='rgba(0,0,0,0)'),
        height=height
    )
    fig.update_xaxes(gridcolor='#2A2A2A')
    fig.update_yaxes(gridcolor='#2A2A2A')
    if layout:
        fig.update_layout(**layout)
    return fig

def hex_to_rgba(hex_color, alpha=0.2):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f'rgba({r}, {g}, {b}, {alpha})'

def format_race_time(seconds):
    seconds = float(seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f'{h}: {m:02d}: {s:04.1f}'

def colorize_strategy(strategy):
    for compound in COMPOUNDS:
        strategy = strategy.replace(
            compound, f'<span class="compound-{compound.lower()}">{compound}</span>'
        )
    return strategy