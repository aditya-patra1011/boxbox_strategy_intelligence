import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from common import (
    show_chart, apply_theme, sidebar_header, circuit_selector, style_fig,
    load_feature_store, load_shap_values, load_comparison, load_model,
    COMPOUND_COLORS
)

st.set_page_config(page_title="Model Insights - BoxBox", layout="wide")
apply_theme()

#Same encoding used when the undercut model was trained in Phase 6
COMPOUND_OFF_MAP = {'HARD': 0, 'MEDIUM': 1, 'SOFT': 2}

#Set this to 17 only if you did NOT apply the Phase 2 pit-loss fix
PIT_LOSS_OFFSET = 0
DEFAULT_PIT_TIME = 22.0

feature_store = load_feature_store()
circuits = sorted(feature_store['CircuitName'].unique())

with st.sidebar:
    sidebar_header()
    circuit = circuit_selector(circuits)

st.title(f"Model Insights - {circuit}")

circuit_row = feature_store[feature_store['CircuitName'] == circuit]

# -------- SHAP FEATURE IMPORTANCE ----------------
st.subheader("What Actually Drives Tire Degradation Here")
st.caption("SHAP feature importance - which factors most influence predicted lap time at this circuit")

try:
    shap_df = load_shap_values()
    circuit_shap = shap_df[shap_df['CircuitName'] == circuit].sort_values('MeanAbsSHAP', ascending=True)

    if circuit_shap.empty:
        st.info("No SHAP data available for this circuit")
    else:
        fig1 = go.Figure(go.Bar(
            x=circuit_shap['MeanAbsSHAP'], y=circuit_shap['Feature'],
            orientation='h', marker_color='#E8002D'
        ))
        style_fig(fig1, height=350, margin=dict(l=10, r=10, t=20, b=10))
        fig1.update_xaxes(title='Mean | SHAP value |')
        show_chart(fig1)
except FileNotFoundError:
    st.info("SHAP file not found. Run Phase 3 first")

st.divider()

# ---- COMPOUND SELECTOR PROBABILITIES ------------
st.subheader("Compound Selection Confidence")
st.caption("Model's predicted probability for each compound, given this circuit's characterstics.")

if not circuit_row.empty:
    try:
        model = load_model('compound_selector.pkl')
        row = circuit_row.iloc[0]

        stint_choice = st.select_slider(
            "Stint Number", options=[1, 2, 3], value=2,
            help="See how the predicted compound choice shifts across the race"
        )

        X_input = pd.DataFrame([{
            'CircuitTypeEncoded': row['CircuitTypeEncoded'],
            'AvgTrackTemp': row['AvgTrackTemp'],
            'StintNumber': stint_choice,
            'SafetyCarProbability': row['SafetyCarProbability']
        }])
        X_input = X_input[list(model.feature_names_in_)]

        probs = model.predict_proba(X_input)[0]
        classes = model.classes_

        fig2 = go.Figure(go.Bar(
            x=classes, y=probs,
            marker_color=[COMPOUND_COLORS.get(str(c).upper(), '#888888') for c in classes],
            text=[f'{p:.0%}' for p in probs], textposition='outside'
        ))
        style_fig(fig2, height=350, margin=dict(l=10, r=10, t=20, b=10))
        fig2.update_yaxes(title='Probability', range=[0, 1.1])
        show_chart(fig2)
    except Exception as e:
        st.info(f"Compound selector prediction unavailable: {e}")

st.divider()

# ------ UNDERCUT VIABILITY GAUGE --------------
st.subheader("Undercut Viability")
st.caption("Estimates how favourable an early pit stop to undercut a rival is at this circuit")

if not circuit_row.empty:
    try:
        bundle = load_model('undercut_classifier.pkl')
        undercut_model = bundle['model']
        undercut_scaler = bundle['scaler']
        row = circuit_row.iloc[0]

        col1, col2, col3 = st.columns(3)
        position = col1.slider("Position before pit", 1, 20, 10)
        tyre_age = col2.slider("Tyre age at pit (laps)", 1, 40, 15)
        compound_off = col3.selectbox("Compound being replaced", ['SOFT', 'MEDIUM', 'HARD'], index=1)

        pit_time = row['AvgPitLoss'] if pd.notna(row['AvgPitLoss']) else DEFAULT_PIT_TIME
        pit_time = pit_time - PIT_LOSS_OFFSET

        X_input = pd.DataFrame([{
            'PositionBeforePit': position,
            'TyreLifeAtPit': tyre_age,
            'CompoundOffEncoded': COMPOUND_OFF_MAP[compound_off],
            'PitDurationSeconds': pit_time,
            'CircuitTypeEncoded': row['CircuitTypeEncoded']
        }])
        X_input = X_input[list(undercut_scaler.feature_names_in_)]

        X_scaled = undercut_scaler.transform(X_input)
        success_idx = list(undercut_model.classes_).index(1)
        prob_success = undercut_model.predict_proba(X_scaled)[0][success_idx]

        fig3 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=prob_success * 100,
            number = {'suffix': '%', 'font': {'color': '#FFFFFF', 'size': 40}},
            gauge={
                'axis': {'range': [0, 100], 'tickcolor': '#CCCCCC'},
                'bar': {'color': '#E8002D'},
                'bgcolor': '#1B1C21',
                'borderwidth': 1,
                'bordercolor': '#2A2A2A',
                'steps': [
                    {'range': [0, 33], 'color': '#2A1518'},
                    {'range': [33, 66], 'color': '#2A2415'},
                    {'range': [66, 100], 'color': '#152A1A'}
                ]
            }
        ))
        fig3.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#CCCCCC'),
            height=300, margin=dict(l=20, r=20, t=30, b=10)
        )
        show_chart(fig3)
        st.caption(
            "This is a relative viability score, not a calibrated probability: the model was "
            "trained with balanced class weights. It uses a proxy for undercut success "
            "(position held or improved shortly after pitting), since live rival gap "
            "telemetry wasn't collected."
        )
    except Exception as e:
        st.info(f"Undercut prediction unavailable: {e}")

st.divider()

#--------- DBSCAN ANOMALY SUMMARY -----------------
st.subheader("Data Quality - Anomaly Detection")
st.caption("DBSCAN-flagged anomalies remaining after cleaning, vs. how much manual cleaning removed.")

try:
    comparison = load_comparison()
    circuit_dbscan = comparison[comparison['CircuitName'] == circuit]

    if not circuit_dbscan.empty:
        row = circuit_dbscan.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total laps (Cleaned)", f"{int(row['TotalLaps'])}")
        col2.metric("Anomalies Detected", f"{int(row['AnomaliesDetected'])}")
        col3.metric("Anomaly Rate", f"{row['AnomalyRate']:.2%}")
        col4.metric("Removed by Manual Cleaning", f"{row['ManualCleaningRate']:.1%}")
    else:
        st.info("No anomaly data available for this circuit")
except FileNotFoundError:
    st.info("Comparison file not found. Run Phase 7 first")