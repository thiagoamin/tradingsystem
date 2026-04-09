# Installing TWS API (ibapi) in a Conda enviroment
This is gives you instructions on how to install the ipapi package in your python enviroment. Make sure you DON'T just use `pip install ibapi`. Instructions adapted from here https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#unix-install.
1. Go to https://interactivebrokers.github.io in your browser, accept the license agreement, then download the "TWS API Stable" zip file. A folder called "twsapi_{mac or windows}" will be downloaded.
2. Open the terminal, navigate to the download folder, enter the folder (in my case `cd Downloads/twsapi_macunix`), and then navigate to the Python client source folder (`cd IBJts/source/pythonclient`). Use `ls` to make sure you see a `setup.py` file.
3. Activate your conda (or any virtual) envirtoment (in my case `conda activate trading_system`).
4. Install the api into your conda env (`pip install .`) (If you get a ModuleNotFoundError: No module named 'setuptools' error (since setuptools is deprecated), use this instead `sudo chmod -R 777 .` and `python3 -m pip install .`)
5. Verify the installation: `pip show ibapi` (I have version: 10.37.2)

# Installing TWS
In order to use the TWS API, you have to install either Trader Workstation - TWS (GUI) or IB Gateway (no GUI) to connect the API to. Here is the download link: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#tws-download. I personally use the IB Gateway since its lighter.

# Open TWS 
Make sure that before sending API requests, that your IB Gateway (or TWS) is open and you are logged in (either in paper or live account). 

Also, go to `Configure -> Settings -> API -> Settings`. Then
- Disable "Read-Only API"
- Confirm socket port (usually 4001 for live trading, 4002 for paper trading)
- If using TWS, enable "ActiveX and Socket Clients" (this is always enabled by default on IB Gateway)

Link here for more info on configuration for API isue: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#tws-settings

# Started Universe
We start with the following 12 ETFs for backtesting:
| Ticker | Definition | Exposure
|---|---|---|
| SPY | SPDR S&P 500 ETF Trust | Broad U.S. large-cap equity exposure |
| QQQ | Invesco QQQ Trust — Nasdaq-100 | Tilted toward large-cap growth and technology |
| IWM | iShares Russell 2000 ETF | U.S. small-cap equities (2000 small-cap U.S. stocks) |
| VXUS | Vanguard Total International Stock ETF | Broad international equities excluding the U.S. | 
| EEM | iShares MSCI Emerging Markets ETF | Emerging market equities
| XLK | Technology Select Sector SPDR Fund | U.S. technology sector exposure |
| XLF | Financial Select Sector SPDR Fund | U.S. financial sector exposure |
| XLV | Health Care Select Sector SPDR Fund | U.S. health care sector exposure |
| XLE | Energy Select Sector SPDR Fund | U.S. energy sector exposure |
| VNQ | Vanguard Real Estate ETF | U.S. real estate investment trusts and real estate equities |
| TLT | iShares 20+ Year Treasury Bond ETF  | Long-duration U.S. Treasury bonds |
| GLD | SPDR Gold Shares |Gold exposure |


# TO-DO
1. Create a Pacer: right now I have "reject messages above maximum allowed message rate vs. applying pacing" unchecked (which means that IBKR won’t necessarily fail my request, but it may slow my API flow down).