"""
Data + model access layer. No dash imports here,
so it is esy to test.
"""
import os
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

BASE = Path(os.environ.get("BOXBOX_BASE", Path(__file__).resolve().parent.parent))
PROCESSED = BASE / "data" / "processed"
OUTPUTS = BASE / "data" / "outputs"
MODELS = BASE / "models"
MAPS = BASE / "circuit_maps"

COMPOUNDS = ["SOFT", "MEDIUM", "HARD"]

LAP_COLUMNS = {"CircuitName", "Compound", "TyreLife", "LapTimeSeconds", "Driver", "Stint"}

def _find(name):
    for d in (PROCESSED, OUTPUTS):
        p = d / name
        if p.exists():
            return p
    return None

@lru_cache(maxsize=None)
def csv(name, only_cols=None):
    p = _find(name)
    if p is None:
        return pd.DataFrame()
    if only_cols:
        return pd.read_csv(p, usecols=lambda c: c in only_cols)
    return pd.read_csv(p)

def feature_store():
    return csv("feature_store.csv")
def plan_abc():
    return csv("plan_abc.csv")
def degradation():
    return csv("degradation_profiles.csv")
def survival():
    return csv("survival_curves.csv")
def shap_values():
    return csv("shap_values.csv")
def clusters():
    return csv("circuit_clusters.csv")
def optimal():
    return csv("optimal_strategies.csv")
def dbscan():
    # The comparison file has every summary column plus the manual-cleaning ones
    df = csv("dbscan_vs_manual_comparison.csv")
    return df if not df.empty else csv("dbscan_anomaly_summary.csv")
def laps():
    return csv("engineered_laps.csv", frozenset(LAP_COLUMNS))

def circuits():
    fs = feature_store()
    return sorted(fs["CircuitName"].unique()) if not fs.empty else []

def circuit_row(circuit):
    fs = feature_store()
    r = fs[fs["CircuitName"] == circuit]
    return r.iloc[0] if not r.empty else None

@lru_cache(maxsize=None)
def compound_counts():
    df = laps()
    if df.empty:
        return pd.DataFrame(columns=["Compound", "Count"])
    c = df["Compound"].value_counts().reset_index()
    c.columns = ["Compound", "Count"]
    c = c[c["Compound"].isin(COMPOUNDS)]
    return c.set_index("Compound").reindex([x for x in COMPOUNDS if x in set(c["Compound"])]).reset_index()

@lru_cache(maxsize=None)
def circuit_laps(circuit):
    df = laps()
    return df[df["CircuitName"] == circuit] if not df.empty else df

@lru_cache(maxsize=None)
def circuit_map(circuit):
    p = MAPS / f"{circuit.lower().replace(' ', '_')}.json"
    if p.exists():
        return go.Figure(pio.from_json(p.read_text()))
    return None

@lru_cache(maxsize=None)
def model(name):
    try:
        import joblib
        return joblib.load(MODELS / name)
    except Exception:
        return None

def compound_probabilities(circuit, stint):
    m = model("compound_selector.pkl")
    r = circuit_row(circuit)
    if m is None or r is None:
        raise RuntimeError("compound_selector.pkl or feature_store row not available")
    cols = ["CircuitTypeEncoded", "AvgTrackTemp", "StintNumber", "SafetyCarProbability"]
    X = pd.DataFrame([{"CircuitTypeEncoded": r["CircuitTypeEncoded"], "AvgTrackTemp": r["AvgTrackTemp"],
                       "StintNumber": stint, "SafetyCarProbability": r["SafetyCarProbability"]}])[cols]
    return [str(c) for c in m.classes_], m.predict_proba(X)[0]

UNDERCUT_COLS = ["PositionBeforePit", "TyreLifeAtPit", "CompoundOffEncoded",
                 "PitDurationSeconds", "CircuitTypeEncoded"]
PIT_LOSS_OFFSET = 0     # Keep identical to the Streamlit version

@lru_cache(maxsize=512)
def undercut_all(position, tyre_life, compound_idx):
    """Undercut success probability for EVERY circuit under one scenario."""
    bundle = model("undercut_classifier.pkl")
    fs = feature_store()
    if bundle is None or fs.empty:
        raise RuntimeError("undercut_classifier.pkl or feature_store not available")
    X = pd.DataFrame({
        "PositionBeforePit": position,
        "TyreLifeAtPit": tyre_life,
        "CompoundOffEncoded": compound_idx,
        "PitDurationSeconds": fs["AvgPitLoss"].values - PIT_LOSS_OFFSET,
        "CircuitTypeEncoded": fs["CircuitTypeEncoded"].values,
    })[UNDERCUT_COLS]
    p = bundle["model"].predict_proba(bundle["scaler"].transform(X))[:, 1]
    return pd.Series(p, index=fs["CircuitName"].values)

def list_tables():
    out = {}
    for label, d in (("processed", PROCESSED), ("outputs", OUTPUTS)):
        if d.exists():
            for p in sorted(d.glob("*.csv")):
                out[f"{label}/{p.name}"] = p
    return out

@lru_cache(maxsize=32)
def read_table(key):
    tables = list_tables()
    if key not in tables:
        return pd.DataFrame()
    return pd.read_csv(tables[key])

def format_race_time(seconds):
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "—"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{sec:04.1f}"

def parse_compounds(text):
    return re.findall(r"SOFT|MEDIUM|HARD", str(text).upper())