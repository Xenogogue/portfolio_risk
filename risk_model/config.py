MODEL_PORTFOLIO = [
    {"token": "BUIDL/USDY", "coingecko": "ondo-us-dollar-yield",           "defillama": None,       "alloc_pct": 20, "stable": True},
    {"token": "USDC",       "coingecko": "usd-coin",     "defillama": None,       "alloc_pct": 10, "stable": True},
    {"token": "BTC",        "coingecko": "bitcoin",      "defillama": None,       "alloc_pct": 20, "stable": False},
    {"token": "ETH",        "coingecko": "ethereum",     "defillama": None,       "alloc_pct": 15, "stable": False},
    {"token": "wstETH",     "coingecko": "wrapped-steth","defillama": "lido",     "alloc_pct": 10, "stable": False},
    {"token": "SOL",        "coingecko": "solana",       "defillama": None,       "alloc_pct": 10, "stable": False},
    {"token": "AAVE",       "coingecko": "aave",         "defillama": "aave-v3",  "alloc_pct": 3,  "stable": False},
    {"token": "UNI",        "coingecko": "uniswap",      "defillama": "uniswap-v3","alloc_pct": 3, "stable": False},
    {"token": "LINK",       "coingecko": "chainlink",    "defillama": None,       "alloc_pct": 3,  "stable": False},
    {"token": "ONDO",       "coingecko": "ondo-finance", "defillama": None,       "alloc_pct": 3,  "stable": False},
    {"token": "PENDLE",     "coingecko": "pendle",       "defillama": "pendle",   "alloc_pct": 3,  "stable": False},
]

WEIGHTS = {
    "ShortTerm":   {"Market": 0.4, "Liquidity": 0.4, "Protocol": 0.1, "Regulatory": 0.1},
    "MediumTerm":  {"Market": 0.3, "Liquidity": 0.2, "Protocol": 0.3, "Regulatory": 0.2},
    "LongTerm":    {"Market": 0.2, "Liquidity": 0.1, "Protocol": 0.4, "Regulatory": 0.3},
}

STARTING_NAV = 100_000
HISTORY_DAYS = 90
VOL_WINDOW = 30