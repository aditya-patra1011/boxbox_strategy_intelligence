import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os

BASE = r'C:\Users\adity\Desktop\BoxBox'

st.set_page_config(page_title="Season Overview - BoxBox", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp {
        background: radial-gradient(ellipse at top left, #14161A 0%, #0A0A0C 55%, #050506 100%);
        color: #E8E8E8;
    }
    section[data-testid="stSidebar"]{
        background: linear-gradient(180deg, #17181C 0%, #OF1013 100%);
        border-right: 1px solid #232428;
    }
    h2, h3 {
        font-weight: 700; letter-spacing: -0.3px;
        position: relative; padding-left: 14px;
    }
    h2::before, h3::before {
        content: ""; position: absolute; left: 0; top: 6px; bottom: 6px;
        width: 4px; background: linear-gradient(180deg, #E8002D, #FF4D6D);
        border-radius: 2px;
    }
    hr { border: none; border-top: 1px solid #232428; marrgin: 28px 0;}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_optimal_strategies():
    return pd.read_csv(os.path.join(BASE, 'data', 'outputs', 'optimal_strategies.csv'))


@st.cache_data
def load_circuit_clusters():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'circuit_clusters.csv'))


@st.cache_data
def load_feature_store():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'feature_store.csv'))

@st.cache_data
def load_engineered_laps():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'engineered_laps.csv'))

#SIDEBAR (keeping the circuit selector too)
feature_store = load_feature_store()
circuits = sorted(feature_store['CircuitName'].unique())

with st.sidebar:
    st.markdown("##  🏎️  BoxBox")
    st.caption("F1 Strategy Intelligence - 2024 Season")
    default_circuit = st.session_state.get('circuit', circuits[0])
    default_index = circuits.index(default_circuit) if default_circuit in circuits else 0
    selected_circuit = st.selectbox("Select Circuit", circuits, index=default_index)
    st.session_state['circuit'] = selected_circuit

st.title(" Season Overview - 2024")
st.caption("A full season view of strategy patterns, circuit clusters, and compounds usage. Not filtered by circuit selection")

#STRATEGY HEATMAP: 1-stop v/s 2-stop
st.subheader("Strategy Landscape Across the Season")
st.caption("Optimal stop count and predicted race time per ciruit")

optimal = load_optimal_strategies()
optimal_sorted = optimal.sort_values('PredictedTotalTime')

fig1 = go.Figure(go.Bar(
    x=optimal_sorted['CircuitName'],
    y=optimal_sorted['PredictedTotalTime'],
    marker=dict(
        color=optimal_sorted['NumStops'],
        colorscale = [[0, '#00C853'], [1, '#E8002D']],
        colorbar=dict(title='Stops', tickvals=[1,2], tickfont=dict(color='#CCCCCC')),
    ),
    text = optimal_sorted['NumStops'].astype(str) + '-stop',
    textposition='outside'
))
fig1.update_layout(
    plot_bgcolor='#0D0D0D', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#CCCCCC'),
    xaxis=dict(title='', tickangle=-45, gridcolor='#2A2A2A'),
    yaxis=dict(title='Predicted Race Time (s)', gridcolor='#2A2A2A'),
    height=500, margin=dict(l=10, r=10, t=20, b=100)
)
st.plotly_chart(fig1, use_container_width=True)

st.divider()

#CIRCUIT CLUSTER
st.subheader("Circuit Clusters")
st.caption("Circuit grouped by degradation behavior, pit loss, and safety car risk (K-Means)")

clusters = load_circuit_clusters()
cluster_merged = clusters.merge(feature_store, on='CircuitName', how='left')
fig2 = px.scatter(
    cluster_merged,
    x='AvgTrackTemp', y='SafetyCarProbability',
    color=cluster_merged['Cluster'].astype(str),
    size='AvgStintLength',
    hover_name = 'CircuitName',
    color_discrete_sequence= ['#E8002D', '#FFD500', '#00C853', '#448AFF'],
    labels={'AvgTrackTemp': 'Avg Track Temp (°C)', 'SafetyCarProbability': 'Safety Car Probability', 'color': 'Cluster'}
)
fig2.update_layout(
    plot_bgcolor='#0D0D0D', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#CCCCCC'),
    xaxis=dict(gridcolor='#2A2A2A'),
    yaxis=dict(gridcolor='#2A2A2A'),
    legend=dict(bgcolor='rgba(0,0,0,0)'),
    height=500
)
st.plotly_chart(fig2, use_container_width=True)
st.caption("Cluster selection on this chart doesn't sync with the sidebar - this is a season-wide reference view.")

st.divider()

#COMPOUND USAGE FREQUENCY
st.subheader("Compound Usage Across the Season")
st.caption("How often each compound was actually used across all 2024 races")

laps = load_engineered_laps()
compound_counts = laps['Compound'].value_counts().reset_index()
compound_counts.columns = ['Compound', 'Count']
compound_counts = compound_counts[compound_counts['Compound'].isin(['SOFT', 'MEDIUM', 'HARD'])]

COMPOUND_COLORS = {'SOFT': '#FF3B3B', 'MEDIUM': '#FFD500', 'HARD': '#E0E0E0'}

fig3 = go.Figure(go.Bar(
    x=compound_counts['Compound'], y=compound_counts['Count'],
    marker_color=[COMPOUND_COLORS[c] for c in compound_counts['Compound']],
    text=compound_counts['Count'], textposition='outside'
))
fig3.update_layout(
    plot_bgcolor='#0D0D0D', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#CCCCCC'),
    yaxis=dict(title='Total Laps', gridcolor='#2A2A2A'),
    xaxis=dict(title=''), height=400
)
st.plotly_chart(fig3, use_container_width=True)
#C:\Users\adity\Desktop\BoxBox\dashboard
#python -m streamlit run app.py