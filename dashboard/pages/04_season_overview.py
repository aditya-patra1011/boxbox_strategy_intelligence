import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from common import (
    show_chart, apply_theme, sidebar_header, circuit_selector, style_fig,
    load_feature_store, load_engineered_laps, load_optimal_strategies,
    load_circuit_clusters, COMPOUNDS, COMPOUND_COLORS, SEASON
)

st.set_page_config(page_title="Season Overview - BoxBox", layout="wide")
apply_theme()

STOP_COLORS = {1: '#00C853', 2: '#FFB300', 3: '#E8002D'}

feature_store = load_feature_store()
circuits = sorted(feature_store['CircuitName'].unique())

with st.sidebar:
    sidebar_header()
    #Kept so the selected circuit carries over to the other pages
    circuit_selector(circuits)

st.title(f"Season Overview - {SEASON}")
st.caption("A full season overview of strategy patterns, circuit clusters, and compound usage. "
        "Not filtered by circuit selection")

# --------- STRATEGY LANDSCAPE ------------------
st.subheader("Strategy Landscape Across the Season")
st.caption("Plan A stop count and risk score per circuit. Hover for the full strategy")

optimal = load_optimal_strategies()
optimal_sorted = optimal.sort_values('RiskScore', ascending=False)

fig1 = go.Figure()
for stops, group in optimal_sorted.groupby('NumStops'):
    stops = int(stops)
    fig1.add_trace(go.Bar(
        x=group['CircuitName'], y=group['RiskScore'],
        name=f'{stops}-stop',
        marker_color = STOP_COLORS.get(stops, '#888888'),
        text = [f'{stops}-stop'] * len(group), textposition='outside',
        customdata=group[['strategy', 'PredictedTotalTime', 'RiskLevel']].values,
        hovertemplate=('<br>%{x}</b><br>%{customdata[0]}</br>'
                       'Risk: %{y} (%{customdata[2]})<br>'
                       'Predicted time: %{customdata[1]:.0f} s<extra></extra>')
    ))

style_fig(fig1, height=500, margin=dict(l=10, r=10, t=20, b=100))
fig1.update_xaxes(
    title='', tickangle=-45,
    categoryorder='array', categoryarray=list(optimal_sorted['CircuitName'])
)
fig1.update_yaxes(title='Risk Score (Plan A)')
show_chart(fig1)

st.divider()

# ---- CIRCUIT CLUSTERS --------------------------
st.subheader("Circuit Clusters")
st.caption("Circuits grouped by track conditions, pit loss, stint length and safety car risk (K-Means)")

clusters = load_circuit_clusters()
cluster_merged = clusters.merge(feature_store, on='CircuitName', how='left')
cluster_merged['Cluster'] = cluster_merged['Cluster'].astype(str)
cluster_merged['AvgStintLength'] = cluster_merged['AvgStintLength'].fillna(
    cluster_merged['AvgStintLength'].mean()
)

fig2 = px.scatter(
    cluster_merged,
    x='AvgTrackTemp', y='SafetyCarProbability',
    color='Cluster', size='AvgStintLength',
    hover_name='CircuitName',
    category_orders={'Cluster': sorted(cluster_merged['Cluster'].unique())},
    color_discrete_sequence=['#E8002D', '#FFD500', '#00C853', '#448AFF'],
    labels={'AvgTrackTemp': 'Avg Track Temp (°C)',
            'SafetyCarProbability': 'Safety Car Probability'}
)
style_fig(fig2, height=500)
show_chart(fig2)
st.caption("This chart doesn't sync with the sidebar  - it is a season-wide reference view")

st.divider()

# ---------- COMPOUND USAGE ----------------------
st.subheader("Compound Usage Across the Season")
st.caption(f"How often compound was actually used across all {SEASON} races")

laps = load_engineered_laps()
compound_counts = laps['Compound'].value_counts().reset_index()
compound_counts.columns = ['Compound', 'Count']
compound_counts = compound_counts[compound_counts['Compound'].isin(COMPOUNDS)]

fig3 = go.Figure(go.Bar(
    x=compound_counts['Compound'], y=compound_counts['Count'],
    marker_color=[COMPOUND_COLORS[c] for c in compound_counts['Compound']],
    text=compound_counts['Count'], textposition='outside'
))
style_fig(fig3, height=400)
fig3.update_yaxes(title='Total Laps')
show_chart(fig3)