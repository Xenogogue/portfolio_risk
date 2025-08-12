import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from risk_model.config import MODEL_PORTFOLIO, WEIGHTS, STARTING_NAV, HISTORY_DAYS, VOL_WINDOW
from risk_model.engine import run_model
from datetime import datetime, date, timedelta, timezone
import requests

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
# --- Ensure USDY price is populated even if engine didn't provide it ---
USYD_LABELS = ["USDY", "BUIDL/USDY"]
usdy_mask = df["Token"].isin(USYD_LABELS)

# If the engine didn't deliver a price for USDY, try a direct simple/price fetch
if usdy_mask.any() and df.loc[usdy_mask, "Price"].isna().any():
    base = st.secrets.get("COINGECKO_BASE", "https://api.coingecko.com/api/v3")
    key = st.secrets.get("COINGECKO_API_KEY", "")
    headers = {"x-cg-pro-api-key": key} if key else {}
    try:
        url = f"{base}/simple/price?ids=ondo-us-dollar-yield&vs_currencies=usd"
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            price = r.json().get("ondo-us-dollar-yield", {}).get("usd")
            if price:
                df.loc[usdy_mask, "Price"] = float(price)
    except Exception:
        pass
# Fallback: if USDY (or legacy BUIDL/USDY) is missing a price, pin to $1.00 so NAV sums correctly
# TEMP: Disable forced $1 fallback while debugging USDY
# df.loc[(df["Token"].isin(["USDY","BUIDL/USDY"])) & (df["Price"].isna()), "Price"] = 1.00
# if "Price" in df.columns:
#     df.loc[(df["Token"].isin(["USDY","BUIDL/USDY"])) & (df["Price"].isna()), "Price"] = 1.00

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


st.markdown("---")
st.header("Backtest — Buy & Hold Snapshot")

# Defaults and state for backtest dates
today = date.today()
default_start = today - timedelta(days=30)
default_end = today
if "bt_start_date" not in st.session_state:
    st.session_state["bt_start_date"] = default_start
if "bt_end_date" not in st.session_state:
    st.session_state["bt_end_date"] = default_end

# Presets
col_a, col_b, col_c, col_d, col_e = st.columns(5)
with col_a:
    preset_1w = st.button("1W")
with col_b:
    preset_1m = st.button("1M")
with col_c:
    preset_1y = st.button("1Y")
with col_d:
    preset_ytd = st.button("YTD")
with col_e:
    preset_custom = st.button("Custom")

# Apply presets by writing to session_state so widgets update correctly
if preset_1w:
    st.session_state["bt_start_date"] = today - timedelta(days=7)
    st.session_state["bt_end_date"] = today
elif preset_1m:
    st.session_state["bt_start_date"] = today - timedelta(days=30)
    st.session_state["bt_end_date"] = today
elif preset_1y:
    st.session_state["bt_start_date"] = today - timedelta(days=365)
    st.session_state["bt_end_date"] = today
elif preset_ytd:
    st.session_state["bt_start_date"] = date(today.year, 1, 1)
    st.session_state["bt_end_date"] = today
# 'Custom' leaves current widget values as-is

# Date pickers bound to state keys
c1, c2 = st.columns(2)
with c1:
    start_date = st.date_input(
        "Start date",
        key="bt_start_date",
        max_value=today,
    )
with c2:
    end_date = st.date_input(
        "End date",
        key="bt_end_date",
        min_value=st.session_state["bt_start_date"],
        max_value=today,
    )

run_bt = st.button("Run Backtest")

if run_bt:
    # Build UTC boundaries (or swap to Aus/Sydney if you like)
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt   = datetime.combine(end_date,   datetime.max.time()).replace(tzinfo=timezone.utc)

    # Run the backtest
    from risk_model.engine import backtest_portfolio
    bt = backtest_portfolio(
        MODEL_PORTFOLIO, st.secrets,
        start_dt=start_dt, end_dt=end_dt,
        starting_nav=STARTING_NAV, stable_price_fallback=1.0
    )

    st.subheader("Backtest Results")
    st.dataframe(
        bt,
        use_container_width=True,
        column_config={
            "Alloc_%": st.column_config.NumberColumn("Alloc %", format="%.0f%%"),
            "Start_Price": st.column_config.NumberColumn("Start Price", format="$%.6f"),
            "End_Price": st.column_config.NumberColumn("End Price", format="$%.6f"),
            "Units": st.column_config.NumberColumn("Units", format="%.6f"),
            "Start_Value_$": st.column_config.NumberColumn("Start Value", format="$%.0f"),
            "End_Value_$": st.column_config.NumberColumn("End Value", format="$%.0f"),
            "PnL_$": st.column_config.NumberColumn("P/L $", format="$%.0f"),
            "PnL_%": st.column_config.NumberColumn("P/L %", format="%.2f%%"),
        }
    )

    # Summary cards
    total_row = bt[bt["Token"]=="TOTAL"].iloc[0]
    col1, col2, col3 = st.columns(3)
    col1.metric("Start NAV", f"${total_row['Start_Value_$']:,.0f}")
    col2.metric("End NAV", f"${total_row['End_Value_$']:,.0f}")
    col3.metric("Return", f"{total_row['PnL_%']:.2f}%")

    # Download
    st.download_button(
        "Download backtest CSV",
        bt.to_csv(index=False),
        file_name=f"backtest_{start_date}_{end_date}.csv",
        mime="text/csv"
    )

# --- Downloads ---
st.subheader("Download")
st.download_button(
    "Download risk table (CSV)",
    df[show_cols].to_csv(index=False),
    file_name="risk_table.csv",
    mime="text/csv"
)