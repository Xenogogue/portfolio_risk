# DeFi Portfolio Risk Model

A real-time risk assessment tool for DeFi portfolios built with Streamlit. This application provides live risk metrics for a $100k portfolio across multiple time horizons.

## Features

- **Real-time Risk Assessment**: Live calculation of risk metrics for DeFi tokens
- **Multi-horizon Analysis**: Short-term (0-3m), Medium-term (3-18m), and Long-term (18m+) risk perspectives
- **Portfolio Visualization**: Interactive dashboard showing current holdings and risk metrics
- **Risk Categories**: Market risk, liquidity risk, protocol risk, and regulatory risk
- **Live Data**: Real-time price feeds and market data integration

## Risk Model Components

### Market Risk
- Volatility analysis (30-day rolling)
- Market cap tier assessment
- BTC/ETH correlation analysis

### Liquidity Risk
- 24-hour volume analysis
- Trading volume tiers

### Protocol Risk
- TVL (Total Value Locked) monitoring
- Protocol-specific risk factors

### Regulatory Risk
- Simple heuristic scoring:
  - Stables: 3 points
  - Blue chips: 2 points
  - Others: 4 points

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd portfolio-risk
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (create a `.env` file):
```bash
# Add your API keys and configuration
COINGECKO_API_KEY=your_api_key_here
```

## Usage

Run the Streamlit application:
```bash
streamlit run app.py
```

The application will be available at `http://localhost:8501`

## Configuration

### Portfolio Settings
- Modify `risk_model/config.py` to adjust portfolio composition
- Update weights and risk parameters as needed

### API Configuration
- Add your CoinGecko API key to environment variables
- Configure rate limiting and data sources

## Project Structure

```
portfolio-risk/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── README.md            # This file
├── .gitignore           # Git ignore rules
└── risk_model/
    ├── __init__.py
    ├── config.py        # Configuration and portfolio settings
    └── engine.py        # Risk calculation engine
```

## Dependencies

- `streamlit`: Web application framework
- `pandas`: Data manipulation
- `numpy`: Numerical computations
- `requests`: API calls
- `python-dotenv`: Environment variable management
- `matplotlib`: Plotting (if needed)
- `plotly`: Interactive visualizations

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational and research purposes. Always conduct your own due diligence before making investment decisions. The risk metrics provided are estimates and should not be considered as financial advice.
