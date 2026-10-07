import streamlit as st

from common import(
    show_chart, apply_theme, show_logo, sidebar_header, circuit_selector, compound_legend,
    load_feature_store, load_plan_abc, load_circuit_map,
    format_race_time, colorize_strategy, SEASON
)

st.set_page_config(
    page_title="BOXBOX - F1 Strategy Intelligence",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)
apply_theme()

feature_store = load_feature_store()
circuits = sorted(feature_store['CircuitName'].unique())

with st.sidebar:
    sidebar_header()
    selected_circuit = circuit_selector(circuits)
    st.divider()
    compound_legend()

col_logo, col_title = st.columns([1, 8])
with col_logo:
    show_logo(90)
with col_title:
    st.markdown("# BOXBOX - F1 Strategy Intelligence")
    st.caption("Because some pit walls need help")

st.markdown(f"### {selected_circuit} - Strategy Intelligence")

# ------ CIRCUIT MAP -----------------------------
st.subheader("Circuit Map")
circuit_fig = load_circuit_map(selected_circuit)
if circuit_fig is not None:
    show_chart(circuit_fig)
else:
    st.info("Circuit map not available for this track")

st.divider()

# ------- STRATEGY CARDS --------------------------
st.subheader("Race Strategy Plans")

plan_abc = load_plan_abc()
circuit_plans = plan_abc[plan_abc['CircuitName'] == selected_circuit]

if circuit_plans.empty:
    st.warning("No strategy data available for this circuit")
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

        risk_level = str(plan_row['RiskLevel'])
        risk_key = risk_level.lower()
        risk_class = f"risk-{risk_key if risk_key in ('low', 'medium', 'high') else 'medium'}"

        card_html = (
            f'<div class="strategy-card {risk_class}">'
            f'<h4>{plan_titles[label]}</h4>'
            f'<p><b>{int(plan_row["NumStops"])}</b> stop(s) &nbsp;|&nbsp; '
            f'Risk: <b>{risk_level}</b> ({plan_row["RiskScore"]})</p>'
            f'<p style="font-size: 18px;">{colorize_strategy(plan_row["strategy"])}</p>'
            f'<p>Predicted time: <b>{format_race_time(plan_row["PredictedTotalTime"])}</b> '
            f'({plan_row["PredictedTotalTime"]:.1f} s)</p>'
            f'</div>'
        )

        with cols[i]:
            st.markdown(card_html, unsafe_allow_html=True)

st.divider()
st.caption(f"BOXBOX - Because some pit walls need help. Built on {SEASON} F1 season data.")