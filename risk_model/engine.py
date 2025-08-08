import time, math, os, json, requests
import pandas as pd
import numpy as np
from statistics import stdev

def _cg_base_and_headers(secrets):
    key = secrets.get("COINGECKO_API_KEY", "")
    base = secrets.get("COINGECKO_BASE", "https://api.coingecko.com/api/v3")
    headers = {"x-cg-pro-api-key": key} if key else {}
    return base, headers

def fetch_markets_batch(ids, secrets):
    if not ids: return {}
    base, headers = _cg_base_and_headers(secrets)
    ids_param = ",".join(sorted(set([cid for cid in ids if cid])))
    url = f"{base}/coins/markets?vs_currency=usd&ids={ids_param}&per_page=250&page=1"
    r = requests.get(url, headers=headers, timeout=25)
    if r.status_code != 200: return {}
    out = {}
    for item in r.json():
        cid = item.get("id")
        out[cid] = {
            "price": item.get("current_price"),
            "market_cap": item.get("market_cap"),
            "volume_24h": item.get("total_volume"),
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
        vol = vol_map.get(cid) if (cid and (not row.stable or not exclude_stables_for_vol)) else None
        c_btc = corr.loc[cid, "bitcoin"] if (cid in corr.index and "bitcoin" in corr.columns) else 0
        c_eth = corr.loc[cid, "ethereum"] if (cid in corr.index and "ethereum" in corr.columns) else 0
        mkt_score = score_market(mkt.get("market_cap"), vol, c_btc, c_eth, row.stable)
        liq, prot, reg = score_other(mkt.get("volume_24h"), None, row.stable)  # TVL optional
        out = {
            "Token": row.token,
            "CoingeckoID": cid,
            "Price": mkt.get("price"),
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