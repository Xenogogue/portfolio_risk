import time, math, os, json, requests
import pandas as pd
import numpy as np
from statistics import stdev
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional

def _cg_base_and_headers(secrets):
    key = secrets.get("COINGECKO_API_KEY", "")
    base = secrets.get("COINGECKO_BASE", "https://api.coingecko.com/api/v3")
    headers = {"x-cg-pro-api-key": key} if key else {}
    return base, headers


def fetch_simple_prices(ids, secrets):
    """Fallback: fetch current prices via /simple/price for a list of CoinGecko IDs.
    Returns dict {id: {"price": float}} for ids that resolve.
    """
    if not ids:
        return {}
    base, headers = _cg_base_and_headers(secrets)
    ids_param = ",".join(sorted(set([cid for cid in ids if cid])))
    url = f"{base}/simple/price?ids={ids_param}&vs_currencies=usd"
    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code != 200:
        return {}
    data = r.json() or {}
    out = {}
    for cid, obj in data.items():
        try:
            price = obj.get("usd")
            if price is not None:
                out[cid] = {"price": float(price)}
        except Exception:
            continue
    return out

def fetch_markets_batch(ids, secrets):
    if not ids:
        return {}
    base, headers = _cg_base_and_headers(secrets)
    ids_param = ",".join(sorted(set([cid for cid in ids if cid])))
    url = f"{base}/coins/markets?vs_currency=usd&ids={ids_param}&per_page=250&page=1"
    r = requests.get(url, headers=headers, timeout=25)
    out = {}
    if r is not None and r.status_code == 200:
        for item in r.json():
            cid = item.get("id")
            out[cid] = {
                "price": item.get("current_price"),
                "market_cap": item.get("market_cap"),
                "volume_24h": item.get("total_volume"),
                "price_source": "markets",
            }
    # Fallback for IDs omitted by /coins/markets
    requested = set([cid for cid in ids if cid])
    missing = list(requested.difference(out.keys()))
    if missing:
        simple = fetch_simple_prices(missing, secrets)
        for cid, obj in simple.items():
            if cid not in out and obj.get("price") is not None:
                out[cid] = {
                    "price": obj.get("price"),
                    "market_cap": None,
                    "volume_24h": None,
                    "price_source": "simple",
                }
    return out

def fetch_history(cid, days, secrets, cache):
    base, headers = _cg_base_and_headers(secrets)
    if cid is None: return None
    key = f"hist:{cid}:{days}"
    if key in cache: return cache[key]
    url = f"{base}/coins/{cid}/market_chart?vs_currency=usd&days={days}&interval=daily"
    r = requests.get(url, headers=headers, timeout=25)
    if r.status_code != 200: return None
    prices = [p[1] for p in r.json().get("prices", [])]
    cache[key] = prices
    time.sleep(0.25 if headers else 1.0)
    return prices

def fetch_history_range(cid: str, start_dt: datetime, end_dt: datetime, secrets, cache) -> Optional[List[Tuple[int, float]]]:
    """
    Return a list of [ [ts_ms, price], ... ] between start_dt and end_dt (inclusive),
    using CoinGecko /market_chart/range. Timestamps in seconds per API.
    """
    base, headers = _cg_base_and_headers(secrets)
    if not cid or start_dt >= end_dt:
        return None
    # Cache key
    key = f"range:{cid}:{int(start_dt.timestamp())}:{int(end_dt.timestamp())}"
    if cache.get(key) is not None:
        return cache[key]
    url = (
        f"{base}/coins/{cid}/market_chart/range"
        f"?vs_currency=usd&from={int(start_dt.timestamp())}&to={int(end_dt.timestamp())}"
    )
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    prices = data.get("prices", [])
    # prices: [[ts_ms, price], ...]
    cache[key] = prices
    time.sleep(0.25 if headers else 1.0)
    return prices or None

def _pick_price_from_series(series: List[Tuple[int, float]], pick: str = "first") -> Optional[float]:
    """
    series: [[ts_ms, price], ...]
    pick: "first" or "last"
    """
    if not series:
        return None
    if pick == "first":
        return float(series[0][1])
    return float(series[-1][1])

def calc_vol(prices, window=30):
    if not prices or len(prices) < 2: return None
    w = min(window, len(prices)-1)
    rets = [(prices[i]-prices[i-1])/prices[i-1] for i in range(1,len(prices))]
    if len(rets[-w:]) < 2: return None
    return stdev(rets[-w:]) * math.sqrt(365)

def corr_matrix(series_dict):
    if not series_dict: return pd.DataFrame()
    valid = {k:v for k,v in series_dict.items() if v and len(v)>1}
    if not valid: return pd.DataFrame()
    df = pd.DataFrame(valid)
    return df.pct_change().corr()

def score_market(mcap, vol, corr_btc, corr_eth, is_stable):
    if is_stable: return 1.5
    # vol bucket
    if vol is None: vol_s = 3
    elif vol < 0.5: vol_s = 1
    elif vol < 1.0: vol_s = 3
    else: vol_s = 5
    # mcap bucket
    if mcap is None: mcap_s = 3
    elif mcap > 10e9: mcap_s = 1
    elif mcap > 1e9: mcap_s = 3
    else: mcap_s = 5
    # corr bucket
    avg_corr = np.mean([abs(corr_btc or 0), abs(corr_eth or 0)])
    if avg_corr < 0.4: corr_s = 1
    elif avg_corr < 0.7: corr_s = 3
    else: corr_s = 5
    return round(vol_s*0.5 + mcap_s*0.3 + corr_s*0.2, 2)

def score_other(volume_24h, tvl, is_stable):
    liq = 3 if volume_24h is None else (1 if volume_24h>500e6 else 3 if volume_24h>50e6 else 5)
    prot = 3 if tvl is None else (1 if tvl>1e9 else 3 if tvl>100e6 else 5)
    reg = 3 if is_stable else (2 if (volume_24h or 0)>500e6 else 4)
    return liq, prot, reg

def weighted(risks, w):
    return round(sum(risks[k]*w[k] for k in w), 2)

def debug_usdy_range(secrets, start_dt, end_dt):
    cid = "ondo-us-dollar-yield"
    base, headers = _cg_base_and_headers(secrets)
    url = (f"{base}/coins/{cid}/market_chart/range"
           f"?vs_currency=usd&from={int(start_dt.timestamp())}&to={int(end_dt.timestamp())}")
    try:
        r = requests.get(url, headers=headers, timeout=30)
        ok = r.status_code
        data = r.json() if ok == 200 else {}
        series = data.get("prices", [])
    except Exception as e:
        ok, series = f"ERR:{e}", []
    return {"status": ok, "count": len(series), 
            "first": series[0] if series else None, 
            "last": series[-1] if series else None, 
            "url": url}

def backtest_portfolio(
    model_portfolio: List[Dict],
    secrets,
    start_dt: datetime,
    end_dt: datetime,
    starting_nav: float = 100_000.0,
    stable_price_fallback: float = 1.0
) -> pd.DataFrame:
    """
    Buy-and-hold backtest from start_dt to end_dt.
    - Buys each sleeve using starting_nav * alloc_pct at start price
    - Computes units, end value, P/L
    Uses CoinGecko market_chart/range for both start & end prices (USDY accrual is respected).
    """
    df = pd.DataFrame(model_portfolio)
    cache: Dict[str, any] = {}

    # Resolve CoinGecko IDs
    cids = {row["token"]: row.get("coingecko") for _, row in df.iterrows()}

    # Pull start & end prices for all assets via range endpoint
    start_prices: Dict[str, Optional[float]] = {}
    end_prices: Dict[str, Optional[float]] = {}

    for token, cid in cids.items():
        if cid:
            series = fetch_history_range(cid, start_dt, end_dt, secrets, cache)
            # If we have multiple points, we’ll take the first as start, last as end
            if series:
                start_prices[token] = _pick_price_from_series(series, "first")
                end_prices[token]   = _pick_price_from_series(series, "last")
            else:
                start_prices[token] = None
                end_prices[token]   = None
        else:
            # No CG ID (shouldn’t happen for USDY now, but keep safe fallback)
            start_prices[token] = stable_price_fallback if df[df["token"]==token]["stable"].any() else None
            end_prices[token]   = start_prices[token]

    # Build P&L table
    records = []
    for row in df.itertuples():
        token = row.token
        alloc_pct = float(row.alloc_pct)
        is_stable = bool(row.stable)
        sp = start_prices.get(token)
        ep = end_prices.get(token)

        # Fallback for stables/RWAs if CG returns nothing
        if sp is None and is_stable:
            sp = stable_price_fallback
        if ep is None and is_stable:
            ep = stable_price_fallback

        target_usd = starting_nav * (alloc_pct/100.0)
        units = (target_usd / sp) if (sp and sp > 0) else np.nan
        start_val = units * sp if (units == units) else np.nan  # nan check
        end_val   = units * ep if (units == units and ep is not None) else np.nan
        pnl_usd   = end_val - start_val if (end_val == end_val and start_val == start_val) else np.nan
        pnl_pct   = (pnl_usd / start_val * 100.0) if (pnl_usd == pnl_usd and start_val and start_val>0) else np.nan

        records.append({
            "Token": token,
            "Alloc_%": alloc_pct,
            "Start_Price": sp,
            "End_Price": ep,
            "Units": units,
            "Start_Value_$": start_val,
            "End_Value_$": end_val,
            "PnL_$": pnl_usd,
            "PnL_%": pnl_pct,
        })

    out = pd.DataFrame(records)

    # Totals row
    totals = {
        "Token": "TOTAL",
        "Alloc_%": out["Alloc_%"].sum(),
        "Start_Price": np.nan,
        "End_Price": np.nan,
        "Units": np.nan,
        "Start_Value_$": out["Start_Value_$"].sum(skipna=True),
        "End_Value_$": out["End_Value_$"].sum(skipna=True),
        "PnL_$": out["PnL_$"].sum(skipna=True),
        "PnL_%": (out["End_Value_$"].sum(skipna=True)/max(out["Start_Value_$"].sum(skipna=True), 1e-9) - 1.0) * 100.0
    }
    out = pd.concat([out, pd.DataFrame([totals])], ignore_index=True)
    return out

def run_model(model_portfolio, weights, secrets, history_days=90, vol_window=30, exclude_stables_for_vol=True):
    df = pd.DataFrame(model_portfolio)
    # batch markets
    cids = [cid for cid in df["coingecko"] if cid]
    markets = fetch_markets_batch(cids, secrets)
    # history
    cache = {}
    series = {}
    for row in df.itertuples():
        if row.coingecko and (not row.stable or not exclude_stables_for_vol):
            series[row.coingecko] = fetch_history(row.coingecko, history_days, secrets, cache)
    # correlations
    corr = corr_matrix(series)
    # vols
    vol_map = {cid: calc_vol(series.get(cid), window=vol_window) for cid in series.keys()}
    # build results
    records = []
    for row in df.itertuples():
        cid = row.coingecko
        mkt = markets.get(cid, {}) if cid else {}
        # Guard: coerce price to float if it's a string
        if mkt and isinstance(mkt.get("price"), str):
            try:
                mkt["price"] = float(mkt["price"])
            except Exception:
                pass
        vol = vol_map.get(cid) if (cid and (not row.stable or not exclude_stables_for_vol)) else None
        c_btc = corr.loc[cid, "bitcoin"] if (cid in corr.index and "bitcoin" in corr.columns) else 0
        c_eth = corr.loc[cid, "ethereum"] if (cid in corr.index and "ethereum" in corr.columns) else 0
        mkt_score = score_market(mkt.get("market_cap"), vol, c_btc, c_eth, row.stable)
        liq, prot, reg = score_other(mkt.get("volume_24h"), None, row.stable)  # TVL optional
        out = {
            "Token": row.token,
            "CoingeckoID": cid,
            "Price": mkt.get("price") if mkt else None,
            "Price_Source": mkt.get("price_source") if mkt else None,
            "MktCap": mkt.get("market_cap"),
            "Vol24h": mkt.get("volume_24h"),
            "Volatility_30d": vol,
            "Corr_BTC": c_btc,
            "Corr_ETH": c_eth,
            "Market_Risk": mkt_score,
            "Liquidity_Risk": liq,
            "Protocol_Risk": prot,
            "Regulatory_Risk": reg,
        }
        for h, w in weights.items():
            out[f"{h}_Risk"] = weighted({"Market": mkt_score, "Liquidity": liq, "Protocol": prot, "Regulatory": reg}, w)
        records.append(out)
    risk_df = pd.DataFrame(records)
    return risk_df, markets, corr