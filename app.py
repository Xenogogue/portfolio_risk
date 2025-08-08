import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from risk_model.config import MODEL_PORTFOLIO, WEIGHTS, STARTING_NAV, HISTORY_DAYS, VOL_WINDOW
from risk_model.engine import run_model

st.set_page_config(page_title="DeFi Risk Model", layout="wide")

st.title("DeFi Risk Assessment — Live Model & $100k Portfolio")

# --- Sidebar controls ---
st.sidebar.header("Settings")
exclude_stables = st.sidebar.checkbox("Exclude stables from vol/corr", True)
hist_days = st.sidebar.slider("History window (days)", 45, 180, HISTORY_DAYS, step=15)
vol_window = st.sidebar.slider("Volatility lookback (days)", 14, 60, VOL_WINDOW, step=2)

# Horizon emphasis (optional tweak)
emphasis = st.sidebar.selectbox("Horizon emphasis", ["Balanced", "ShortTerm", "MediumTerm", "LongTerm"])
weights = WEIGHTS.copy()
if emphasis != "Balanced":
    # light emphasis: +0.1 to chosen horizon's Market weight (renormalize)
    w = weights[emphasis].copy()
    w["Market"] = min(w["Market"] + 0.1, 0.7)
    norm = sum(w.values())
    for k in w: w[k] = w[k]/norm
    weights[emphasis] = w

st.sidebar.write("—")
if st.sidebar.button("Refresh"):
    st.rerun()

# --- Explanatory notes ---
with st.expander("How to use this model"):
    st.markdown("""
**What it measures**  
- *Market risk* (volatility, market cap tier, BTC/ETH correlation)  
- *Liquidity risk* (24h volume tiers)  
- *Protocol risk* (placeholder here; wire DefiLlama TVL if desired)  
- *Regulatory risk* (simple heuristic: stables=3, blue chips=2, others=4)

**Horizons**  
- **Short (0–3m)** overweights market & liquidity  
- **Medium (3–18m)** balances market & protocol  
- **Long (18m+)** overweights protocol & regulatory

**When to act** *(example rules)*  
- If **ShortTerm_Risk > 4** → trim highest-vol sleeve by ~20%  
- If a token’s **TVL −20% in 7 days** → move to watchlist  
- Rebalance on **10–15% drift** or triggered thresholds

**Limitations**  
- API availability / rate limits  
- Young tokens may have limited history → softer confidence  
- Protocol events can dominate models — always overlay human judgment
""")

# --- Run model ---
risk_df, markets, corr = run_model(
    MODEL_PORTFOLIO, weights, st.secrets, history_days=hist_days,
    vol_window=vol_window, exclude_stables_for_vol=exclude_stables
)

# --- Build $100k live portfolio view ---
df = risk_df.copy()
df["Alloc_%"] = [row["alloc_pct"] for row in MODEL_PORTFOLIO]
df["Target_$"] = (df["Alloc_%"]/100.0) * STARTING_NAV

# Fallback: if USDY (or legacy BUIDL/USDY) is missing a price, pin to $1.00 so NAV sums correctly
if "Price" in df.columns:
    df.loc[(df["Token"].isin(["USDY","BUIDL/USDY"])) & (df["Price"].isna()), "Price"] = 1.00

df["Units"] = df["Target_$"] / df["Price"]
df["Current_Value_$"] = df["Units"] * df["Price"]

# --- NAV on top ---
nav_val = float(df["Current_Value_$"].sum())
st.metric("Current NAV (sum of holdings)", f"${nav_val:,.0f}")
st.caption("NAV is recomputed from live prices at load time.")

# --- Full-width table below ---
st.subheader("Risk‑Adjusted $100k Portfolio (Live)")
show_cols = [
    "Token","Price","Alloc_%","Units","Current_Value_$",
    "Volatility_30d","Corr_BTC","Corr_ETH",
    "ShortTerm_Risk","MediumTerm_Risk","LongTerm_Risk"
]
st.dataframe(
    df[show_cols],
    use_container_width=True,
    column_config={
        "Price": st.column_config.NumberColumn("Price", format="$%.4f"),
        "Alloc_%": st.column_config.NumberColumn("Alloc %", format="%.0f%%"),
        "Units": st.column_config.NumberColumn("Units", format="%.4f"),
        "Current_Value_$": st.column_config.NumberColumn("Current Value", format="$%.0f"),
        "Volatility_30d": st.column_config.NumberColumn("30d Vol", format="%.4f"),
        "Corr_BTC": st.column_config.NumberColumn("Corr BTC", format="%.2f"),
        "Corr_ETH": st.column_config.NumberColumn("Corr ETH", format="%.2f"),
        "ShortTerm_Risk": st.column_config.NumberColumn("Short", format="%.2f"),
        "MediumTerm_Risk": st.column_config.NumberColumn("Medium", format="%.2f"),
        "LongTerm_Risk": st.column_config.NumberColumn("Long", format="%.2f"),
    }
)

# --- Downloads ---
st.subheader("Download")
st.download_button(
    "Download risk table (CSV)",
    df[show_cols].to_csv(index=False),
    file_name="risk_table.csv",
    mime="text/csv"
)