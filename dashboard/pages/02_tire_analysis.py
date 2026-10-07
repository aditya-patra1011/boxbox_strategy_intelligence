import streamlit as st
import plotly.graph_objects as go

from common import (
    show_chart, apply_theme, sidebar_header, circuit_selector, style_fig, hex_to_rgba,
    load_feature_store, load_engineered_laps, load_survival_curves,
    load_degradation_profiles, COMPOUNDS, COMPOUND_COLORS, SEASON
)

st.set_page_config(page_title="Tire Analysis - BoxBox", layout="wide")
apply_theme()

feature_store = load_feature_store()
circuits = sorted(feature_store['CircuitName'].unique())

with st.sidebar:
    sidebar_header()
    circuit = circuit_selector(circuits)

st.title(f"📊 Tire Analysis - {circuit}")

laps = load_engineered_laps()
circuit_laps = laps[laps['CircuitName'] == circuit]

if circuit_laps.empty:
    st.warning("No lap data available for this circuit.")
    st.stop()

survival = load_survival_curves()
degradation = load_degradation_profiles()
circuit_degradation = degradation[degradation['CircuitName'] == circuit]


# --- DEGRADATION CURVES --------------------------
st.subheader("Tire Degradation Curves")
st.caption("Feul-corrected lap time as tire age increases, per compound. "
        "Dots are real laps, lines are the model's degradation rate.")

fig1 = go.Figure()
for compound in COMPOUNDS:
    comp_data = circuit_laps[circuit_laps['Compound'] == compound]
    if comp_data.empty:
        continue

    fig1.add_trace(go.Scatter(
        x=comp_data['TyreLife'], y=comp_data['FuelCorrectedLapTime'],
        mode='markers',
        marker=dict(color=COMPOUND_COLORS[compound], size=4, opacity=0.3),
        name = f'{compound} (laps)', showlegend=False
    ))

    profile = circuit_degradation[circuit_degradation['Compound'] == compound]
    if not profile.empty:
        deg_rate = profile.iloc[0]['DegradationRate']
        avg_time = profile.iloc[0]['AvgLapTime']
        avg_tyre_life = profile.iloc[0]['AvgTyreLife']

        # Lap time of a fresh tyre, then add the degradation rate per lap of age
        base_time = avg_time - deg_rate * avg_tyre_life
        x_line = [0, comp_data['TyreLife'].max()]
        y_line = [base_time + deg_rate * x for x in x_line]

        fig1.add_trace(go.Scatter(
            x=x_line, y=y_line, mode='lines',
            line = dict(color=COMPOUND_COLORS[compound], width=3),
            name=f'{compound} ({deg_rate:+.3f}s/lap)'
        ))

style_fig(fig1, height=450)
fig1.update_xaxes(title='Tire Age (laps)')
fig1.update_yaxes(title='Feul-corrected lap Time (s)')
show_chart(fig1)

st.divider()

# ------ KAPLAN-MEIER SURVIVAL CURVES --------------
st.subheader("Tire Survival Probability")
st.caption("Probability the tire is still competitive at a given age, with confidence bands.")

fig2 = go.Figure()
compounds_shown = []
for compound in COMPOUNDS:
    curve_data = survival[
        (survival['CircuitName'] == circuit) & (survival['Compound'] == compound)
    ].sort_values('TyreAge')

    if curve_data.empty:
        continue
    compounds_shown.append(compound)

    fig2.add_trace(go.Scatter(
        x=curve_data['TyreAge'], y=curve_data['CI_Upper'],
        mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    fig2.add_trace(go.Scatter(
        x=curve_data['TyreAge'], y=curve_data['CI_Lower'],
        mode='lines', line=dict(width=0), fill='tonexty',
        fillcolor=hex_to_rgba(COMPOUND_COLORS[compound], alpha=0.2)
    ))
    fig2.add_trace(go.Scatter(
        x=curve_data['TyreAge'], y=curve_data['SurvivalProbability'],
        mode='lines', line=dict(color=COMPOUND_COLORS[compound], width=3, shape='hv'),
        name=compound
    ))

missing = set(COMPOUNDS) - set(compounds_shown)
if missing:
    st.caption(f"⚠️ Insufficient stint data to compute a reliable survival curve for: "
            f"{' '.join(sorted(missing))}")

style_fig(fig2, height=450)
fig2.update_xaxes(title='Tire Age (laps)')
fig2.update_yaxes(title='Survival Probability', range=[0, 1.05])
show_chart(fig2)

st.divider()

# ----- STINT LENGTH DISTRIBUTOR -------------------
st.subheader("Real-World Stint Length Distribution")
st.caption(f"How many laps drivers actually ran on each compound at this circuit in {SEASON}")

stint_lengths = circuit_laps.groupby(
    ['Driver', 'Stint', 'Compound']
).agg(
    FirstLap = ('LapNumber', 'min'),
    LastLap = ('LapNumber', 'max')
).reset_index()
stint_lengths['StintLength'] = stint_lengths['LastLap'] - stint_lengths['FirstLap'] + 1

fig3 = go.Figure()
for compound in COMPOUNDS:
    comp_stints = stint_lengths[stint_lengths['Compound'] == compound]
    if comp_stints.empty:
        continue
    fig3.add_trace(go.Box(
        y=comp_stints['StintLength'], name=compound,
        marker_color = COMPOUND_COLORS[compound]
    ))

style_fig(fig3, height=400, showlegend=False)
fig3.update_yaxes(title='Stint Length (laps)')
show_chart(fig3)

st.divider()

# -------- COMPOUND PACE COMPARISON -----------------------------
st.subheader("Compound Pace Comparison")
st.caption("Average fuel-corrected lap time per compound at this circuit.")

pace_data = circuit_laps.groupby('Compound')['FuelCorrectedLapTime'].mean().reset_index()
pace_data = pace_data[pace_data['Compound'].isin(COMPOUNDS)]

if pace_data.empty:
    st.info("No compound pace data available for this circuit.")
else:
    fig4 = go.Figure(go.Bar(
        x=pace_data['Compound'], y=pace_data['FuelCorrectedLapTime'],
        marker_color=[COMPOUND_COLORS[c] for c in pace_data['Compound']],
        text=pace_data['FuelCorrectedLapTime'].round(2),
        textposition='outside'
    ))

    y_min = pace_data['FuelCorrectedLapTime'].min() - 0.5
    y_max = pace_data['FuelCorrectedLapTime'].max() + 0.5

    style_fig(fig4, height=400)
    fig4.update_yaxes(title='Avg Fuel-corrected Lap Time (s)', range=[y_min, y_max])
    show_chart(fig4)