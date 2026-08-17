import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import joblib
import os

BASE = r'C:\Users\adity\Desktop\BoxBox'

st.set_page_config(page_title="Model Insights - BoxBox", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp{
        background: radial-gradient(ellipse at top left, #14161A 0%, #0A0A0C 55%, #050506 100%);
        color: #E8E8E8;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #17181C 0%, #0F1013 100%);
        border-right: 1px solid #232428;
    }
    h2, h3 {
        font-0weight: 700; letter-spacing: -0.3px;
        position: relative; padding-left: 14px;
    }
    h2::before, h3::before {
        content: ""; position: absolute; left: 0; top: 6px; bottom: 6px;
        width: 4px; background: linear-gradient(180deg, #E8002D, #FF4D6D);
        border-radius: 2px;
    }
    hr { border: none; border-top: 1px solid #232428; margin: 28px 0; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_feature_store():
    return pd.read_csv(os.path.join(BASE, 'data', 'processed', 'feature_store.csv'))

@st.cache_data
def load_shap_values():
    return pd.read_csv(os.path.join(BASE, 'data', 'outputs', 'shap_values.csv'))

@st.cache_data
def load_dbscan_summary():
    return pd.read_csv(os.path.join(BASE, 'data', 'outputs', 'dbscan_anomaly_summary.csv'))

@st.cache_data
def load_compound_selector():
    return joblib.load(os.path.join(BASE, 'models', 'compound_selector.pkl'))

@st.cache_data
def load_undercut_classifier():
    return joblib.load(os.path.join(BASE, 'models', 'undercut_classifier.pkl'))

#SIDEBAR (duplicated so this page works standalone)
feature_store = load_feature_store()
circuits = sorted(feature_store['CircuitName'].unique())

with st.sidebar:
    st.markdown("## 🏎️ BoxBox")
    st.caption("F1 Strategy Intelligence - 2024 Season")
    default_circuit = st.session_state.get('circuit', circuits[0])
    default_index = circuits.index(default_circuit) if default_circuit in circuits else 0
    selected_circuit = st.selectbox("Select Circuit", circuits, index=default_index, key='circuit_selector_p3')
    st.session_state['circuit'] = selected_circuit

circuit = st.session_state['circuit']

st.title(f" Model Insights - {circuit}")

#SHAP FEATURE IMPORTANCE
st.subheader("What actually Drives Tire Degradation Here")
st.caption("SHAP feature importance - which factors most influence predicted lap time at this circuit")

shap_df = load_shap_values()
circuit_shap = shap_df[shap_df['CircuitName'] == circuit].sort_values('MeanAbsSHAP', ascending=True)

if circuit_shap.empty:
    st.info("No SHAP data available for this circuit")
else:
    fig1 = go.Figure(go.Bar(
        x=circuit_shap['MeanAbsSHAP'], y=circuit_shap['Feature'],
        orientation = 'h', marker_color = '#E8002D'
    ))
    fig1.update_layout(
        plot_bgcolor='#0D0D0D', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#CCCCCC'),
        xaxis=dict(title='Mean | SHAP values |', gridcolor='#2A2A2A'),
        yaxis=dict(title=''), height=350, margin=dict(l=10, r=10, t=20, b=10)
    )
    st.plotly_chart(fig1, use_container_width=True)

st.divider()

#COMPOUND SELECTOR PROBABILITIES
st.subheader("Compound Selection Confidence")
st.caption("Model's predicted probability for each compound, given this circuit's characterstics.")

circuit_row = feature_store[feature_store['CircuitName'] == circuit]

if not circuit_row.empty:
    try:
        model = load_compound_selector()
        features = ['CircuitTypeEncoded', 'AvgTrackTemp', 'SafetyCarProbability']
        #Using mid race stint number (2) as a representative input
        stint_choice = st.select_slider(
            "Stint Number", options=[1, 2, 3], value=1,
            help="See how predicted compounds choice shifts across the race"
        )
        X_input = pd.DataFrame([{
            'CircuitTypeEncoded': circuit_row.iloc[0]['CircuitTypeEncoded'],
            'AvgTrackTemp': circuit_row.iloc[0]['AvgTrackTemp'],
            'StintNumber': stint_choice,
            'SafetyCarProbability': circuit_row.iloc[0]['SafetyCarProbability']
        }])[['CircuitTypeEncoded', 'AvgTrackTemp', 'StintNumber', 'SafetyCarProbability']]

        probs = model.predict_proba(X_input)[0]
        classes = model.classes_

        COMPOUND_COLORS = {'Soft': '#FF3B3B', 'Medium': '#FFD500', 'Hard': '#E0E0E0'}
        fig2 = go.Figure(go.Bar(
            x=classes, y=probs,
            marker_color = [COMPOUND_COLORS.get(c, '#888888') for c in classes],
            text = [f'{p:.1f}' for p in probs], textposition='outside'
        ))
        fig2.update_layout(
            plot_bgcolor = '#0D0D0D', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#CCCCCC'),
            yaxis = dict(title='Probability', gridcolor='#2A2A2A', range=[0, 1.1]),
            xaxis = dict(title=''), height=350, margin=dict(l=10, r=10, t=20, b=10)
        )
        st.plotly_chart(fig2, use_container_width=True)
    except Exception as e:
        st.info(f"Compound selector prediction unavailable: {e}")

st.divider()

#UNDERCUT VIABILITY GAUGE
st.subheader("Undercut Viability")
st.caption("Estimates probability that pitting early to undercut a rival suceeds at this circuit")

if not circuit_row.empty:
    try:
        undercut_bundle = load_undercut_classifier()
        undercut_model = undercut_bundle['model']
        undercut_scaler = undercut_bundle['scaler']

        #Representative mid feild scenario input
        X_input = pd.DataFrame([{
            'PositionBeforePit': 10,
            'TyreLifeAtPit': 15,
            'CompoundOffEncoded': 1,
            'PitDurationSeconds': circuit_row.iloc[0]['AvgPitLoss'] - 17,
            'CircuitTypeEncoded': circuit_row.iloc[0]['CircuitTypeEncoded']
        }])

        X_scaled = undercut_scaler.transform(X_input)
        prob_success = undercut_model.predict_proba(X_scaled)[0][1]

        fig3 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=prob_success * 100,
            number={'suffix': '%', 'font': {'color': '#FFFFFF', 'size': 40}},
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
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("Note: It uses a proxy for undercut success (position held/improved shortly after pitting), since" \
        " live rival gap telemetry wasn't collected - see README for details")

    except Exception as e:
        st.info(f" Undercut prediction available: {e}")
st.divider()

#DBSCAN ANOMALY SUMMARY
st.subheader("Data quality - Anomaly Detection")
st.caption("DBSCAN-flagged anomalies remaining after cleaning, vs. how much manual cleaning removed.")

dbscan_summary = load_dbscan_summary()
circuit_dbscan = dbscan_summary[dbscan_summary['CircuitName'] == circuit]

if not circuit_dbscan.empty:
    row = circuit_dbscan.iloc[0]
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Laps (Cleaned)", f"{int(row['TotalLaps'])}")
    col2.metric("Anomalies Detected", f"{int(row['AnomaliesDetected'])}")
    col3.metric("Anomaly Rate", f"{row['AnomalyRate']:.2%}")
    st.caption(f"Manual cleaning (Phase 2) removed {row['ManualCleaningRate']:.1%}")
else:
    st.info("No anomaly data available for this cirucuit")

#C:\Users\adity\Desktop\BoxBox\dashboard
#python -m streamlit run app.py