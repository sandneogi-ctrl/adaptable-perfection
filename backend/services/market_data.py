from SmartApi import SmartConnect
import pyotp
import pytz
import os
from datetime import datetime, time as dtime, timedelta

IST = pytz.timezone("Asia/Kolkata")

NAME_MAP = {
    "RELIANCE":   "Reliance Industries",
    "TCS":        "Tata Consultancy Services",
    "HDFCBANK":   "HDFC Bank",
    "INFY":       "Infosys",
}

NIFTY50_STOCKS = [
    {"symbol": "RELIANCE",   "token": "2885"},
    {"symbol": "TCS",        "token": "11536"},
    {"symbol": "HDFCBANK",   "token": "1333"},
    {"symbol": "INFY",       "token": "1594"},
]

_smart_api  = None
_auth_token = None


def get_market_status():
    now = datetime.now(IST)
    is_open = now.weekday() < 5 and dtime(9, 15) <= now.time() <= dtime(15, 30)
    return {
        "is_open":    is_open,
        "label":      "Market Open" if is_open else "Market Closed",
        "note":       None if is_open else "Showing last session historical data. Market is closed.",
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S IST")
    }


def _last_trading_day():
    """Return last weekday date as string YYYY-MM-DD."""
    d = datetime.now(IST).date()
    # Go back until we hit a weekday (Mon-Fri)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    # If today is a weekday but market hasn't opened yet, use previous day
    now = datetime.now(IST)
    if now.weekday() < 5 and now.time() < dtime(9, 15):
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _login():
    global _smart_api, _auth_token
    try:
        api_key     = os.environ.get("ANGEL_API_KEY")
        client_id   = os.environ.get("ANGEL_CLIENT_ID")
        password    = os.environ.get("ANGEL_PASSWORD")
        totp_secret = os.environ.get("ANGEL_TOTP_SECRET")

        if not all([api_key, client_id, password, totp_secret]):
            print("[Angel One] ERROR: Missing credentials.")
            print(f"  ANGEL_API_KEY     : {'SET' if api_key     else 'MISSING'}")
            print(f"  ANGEL_CLIENT_ID   : {'SET' if client_id   else 'MISSING'}")
            print(f"  ANGEL_PASSWORD    : {'SET' if password    else 'MISSING'}")
            print(f"  ANGEL_TOTP_SECRET : {'SET' if totp_secret else 'MISSING'}")
            return False

        _smart_api = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_secret).now()
        data = _smart_api.generateSession(
            clientCode=client_id,
            password=password,
            totp=totp
        )

        if data and data.get("status"):
            _auth_token = data["data"]["jwtToken"]
            print("[Angel One] Login successful.")
            return True

        print(f"[Angel One] Login REJECTED. Response: {data}")
        return False

    except Exception as e:
        print(f"[Angel One] Login exception: {e}")
        return False


def _ensure_logged_in():
    global _auth_token
    if not _auth_token:
        return _login()
    return True


def _fetch_live(stock):
    """Fetch live market data during market hours."""
    try:
        resp = _smart_api.getMarketData({
            "mode": "FULL",
            "exchangeTokens": {"NSE": [stock["token"]]}
        })
        if resp and resp.get("status") and resp.get("data"):
            fetched = resp["data"].get("fetched", [])
            if fetched:
                d          = fetched[0]
                ltp        = round(float(d.get("ltp",   0)), 2)
                close      = round(float(d.get("close", 0)), 2)
                open_      = round(float(d.get("open",  0)), 2)
                high       = round(float(d.get("high",  0)), 2)
                low        = round(float(d.get("low",   0)), 2)
                volume     = int(d.get("tradeVolume", 0))
                change     = round(ltp - close, 2) if close else 0
                change_pct = round((change / close * 100), 2) if close else 0
                return {
                    "symbol":         stock["symbol"],
                    "name":           NAME_MAP.get(stock["symbol"], stock["symbol"]),
                    "ltp":            ltp,
                    "open":           open_,
                    "high":           high,
                    "low":            low,
                    "close":          close,
                    "prev_close":     close,
                    "change":         change,
                    "change_percent": change_pct,
                    "volume":         volume,
                    "data_type":      "live"
                }
    except Exception as e:
        print(f"[Angel One] Live fetch error {stock['symbol']}: {e}")
    return None


def _fetch_historical(stock):
    """
    Fetch last session OHLC via getCandleData.
    Used when market is closed — always returns last trading day data.
    Candle format: [timestamp, open, high, low, close, volume]
    """
    try:
        last_day = _last_trading_day()
        params = {
            "exchange":    "NSE",
            "symboltoken": stock["token"],
            "interval":    "ONE_DAY",
            "fromdate":    f"{last_day} 09:15",
            "todate":      f"{last_day} 15:30"
        }
        resp = _smart_api.getCandleData(params)
        if resp and resp.get("status") and resp.get("data"):
            candles = resp["data"]
            if len(candles) >= 2:
                # Last candle = current/last session
                # Previous candle = day before (for change calculation)
                curr = candles[-1]
                prev = candles[-2]
                open_      = round(float(curr[1]), 2)
                high       = round(float(curr[2]), 2)
                low        = round(float(curr[3]), 2)
                close      = round(float(curr[4]), 2)
                volume     = int(curr[5])
                prev_close = round(float(prev[4]), 2)
                change     = round(close - prev_close, 2)
                change_pct = round((change / prev_close * 100) if prev_close else 0, 2)
                return {
                    "symbol":         stock["symbol"],
                    "name":           NAME_MAP.get(stock["symbol"], stock["symbol"]),
                    "ltp":            close,
                    "open":           open_,
                    "high":           high,
                    "low":            low,
                    "close":          close,
                    "prev_close":     prev_close,
                    "change":         change,
                    "change_percent": change_pct,
                    "volume":         volume,
                    "data_type":      "historical"
                }
            elif len(candles) == 1:
                # Only one candle — no prev close available
                curr = candles[0]
                close = round(float(curr[4]), 2)
                return {
                    "symbol":         stock["symbol"],
                    "name":           NAME_MAP.get(stock["symbol"], stock["symbol"]),
                    "ltp":            close,
                    "open":           round(float(curr[1]), 2),
                    "high":           round(float(curr[2]), 2),
                    "low":            round(float(curr[3]), 2),
                    "close":          close,
                    "prev_close":     close,
                    "change":         0.0,
                    "change_percent": 0.0,
                    "volume":         int(curr[5]),
                    "data_type":      "historical"
                }
        print(f"[Angel One] No historical data for {stock['symbol']}")
    except Exception as e:
        print(f"[Angel One] Historical fetch error {stock['symbol']}: {e}")
    return None


def fetch_nifty50():
    """
    Fetch all Nifty50 stocks.
    - Market OPEN  → live getMarketData (real-time LTP)
    - Market CLOSED → historical getCandleData (last session OHLC)
    No MySQL — pure in-memory.
    """
    if not _ensure_logged_in():
        print("[Angel One] Cannot fetch — not logged in.")
        return []

    status   = get_market_status()
    is_open  = status["is_open"]
    mode     = "LIVE" if is_open else "HISTORICAL"
    print(f"[Angel One] Fetching in {mode} mode (market {'open' if is_open else 'closed'})...")

    results = []
    failed  = 0

    for stock in NIFTY50_STOCKS:
        data = _fetch_live(stock) if is_open else _fetch_historical(stock)
        if data:
            results.append(data)
        else:
            if failed == 0:
                print(f"[Angel One] First failure: {stock['symbol']} in {mode} mode.")
            failed += 1
            # Reset session on auth errors
            global _auth_token
            _auth_token = None if failed > 5 else _auth_token

    print(f"[Angel One] Done. Fetched {len(results)}/50. Failed: {failed}.")
    return results
from SmartApi import SmartConnect
import pyotp
import pytz
import os
from datetime import datetime, time as dtime, timedelta

IST = pytz.timezone("Asia/Kolkata")

NAME_MAP = {
    "RELIANCE":   "Reliance Industries",
    "TCS":        "Tata Consultancy Services",
    "HDFCBANK":   "HDFC Bank",
    "INFY":       "Infosys",
    "ICICIBANK":  "ICICI Bank",
    "HINDUNILVR": "Hindustan Unilever",
    "SBIN":       "State Bank of India",
    "BHARTIARTL": "Bharti Airtel",
    "ITC":        "ITC",
    "KOTAKBANK":  "Kotak Mahindra Bank",
    "LT":         "Larsen & Toubro",
    "AXISBANK":   "Axis Bank",
    "ASIANPAINT": "Asian Paints",
    "MARUTI":     "Maruti Suzuki",
    "SUNPHARMA":  "Sun Pharmaceutical",
    "TITAN":      "Titan Company",
    "BAJFINANCE": "Bajaj Finance",
    "WIPRO":      "Wipro",
    "ULTRACEMCO": "UltraTech Cement",
    "NESTLEIND":  "Nestle India",
    "POWERGRID":  "Power Grid Corporation",
    "NTPC":       "NTPC",
    "TECHM":      "Tech Mahindra",
    "HCLTECH":    "HCL Technologies",
    "ONGC":       "ONGC",
    "TATAMOTORS": "Tata Motors",
    "TATASTEEL":  "Tata Steel",
    "ADANIENT":   "Adani Enterprises",
    "ADANIPORTS": "Adani Ports",
    "COALINDIA":  "Coal India",
    "DIVISLAB":   "Divi's Laboratories",
    "DRREDDY":    "Dr. Reddy's Laboratories",
    "EICHERMOT":  "Eicher Motors",
    "GRASIM":     "Grasim Industries",
    "HDFCLIFE":   "HDFC Life",
    "HEROMOTOCO": "Hero MotoCorp",
    "HINDALCO":   "Hindalco Industries",
    "INDUSINDBK": "IndusInd Bank",
    "JSWSTEEL":   "JSW Steel",
    "M&M":        "Mahindra & Mahindra",
    "CIPLA":      "Cipla",
    "BAJAJFINSV": "Bajaj Finserv",
    "BAJAJ-AUTO": "Bajaj Auto",
    "APOLLOHOSP": "Apollo Hospitals",
    "BRITANNIA":  "Britannia Industries",
    "SBILIFE":    "SBI Life Insurance",
    "TATACONSUM": "Tata Consumer Products",
    "UPL":        "UPL",
    "BPCL":       "Bharat Petroleum",
    "SHREECEM":   "Shree Cement",
}

NIFTY50_STOCKS = [
    {"symbol": "RELIANCE",   "token": "2885"},
    {"symbol": "TCS",        "token": "11536"},
    {"symbol": "HDFCBANK",   "token": "1333"},
    {"symbol": "INFY",       "token": "1594"},
    {"symbol": "ICICIBANK",  "token": "4963"},
    {"symbol": "HINDUNILVR", "token": "1394"},
    {"symbol": "SBIN",       "token": "3045"},
    {"symbol": "BHARTIARTL", "token": "10604"},
    {"symbol": "ITC",        "token": "1660"},
    {"symbol": "KOTAKBANK",  "token": "1922"},
    {"symbol": "LT",         "token": "11483"},
    {"symbol": "AXISBANK",   "token": "5900"},
    {"symbol": "ASIANPAINT", "token": "236"},
    {"symbol": "MARUTI",     "token": "10999"},
    {"symbol": "SUNPHARMA",  "token": "3351"},
    {"symbol": "TITAN",      "token": "3506"},
    {"symbol": "BAJFINANCE", "token": "317"},
    {"symbol": "WIPRO",      "token": "3787"},
    {"symbol": "ULTRACEMCO", "token": "11532"},
    {"symbol": "NESTLEIND",  "token": "17963"},
    {"symbol": "POWERGRID",  "token": "14977"},
    {"symbol": "NTPC",       "token": "11630"},
    {"symbol": "TECHM",      "token": "13538"},
    {"symbol": "HCLTECH",    "token": "7229"},
    {"symbol": "ONGC",       "token": "2475"},
    {"symbol": "TATAMOTORS", "token": "3456"},
    {"symbol": "TATASTEEL",  "token": "3499"},
    {"symbol": "ADANIENT",   "token": "25"},
    {"symbol": "ADANIPORTS", "token": "15083"},
    {"symbol": "COALINDIA",  "token": "20374"},
    {"symbol": "DIVISLAB",   "token": "10940"},
    {"symbol": "DRREDDY",    "token": "881"},
    {"symbol": "EICHERMOT",  "token": "910"},
    {"symbol": "GRASIM",     "token": "1232"},
    {"symbol": "HDFCLIFE",   "token": "467"},
    {"symbol": "HEROMOTOCO", "token": "1348"},
    {"symbol": "HINDALCO",   "token": "1363"},
    {"symbol": "INDUSINDBK", "token": "5258"},
    {"symbol": "JSWSTEEL",   "token": "11723"},
    {"symbol": "M&M",        "token": "2031"},
    {"symbol": "CIPLA",      "token": "694"},
    {"symbol": "BAJAJFINSV", "token": "16675"},
    {"symbol": "BAJAJ-AUTO", "token": "16669"},
    {"symbol": "APOLLOHOSP", "token": "157"},
    {"symbol": "BRITANNIA",  "token": "547"},
    {"symbol": "SBILIFE",    "token": "21808"},
    {"symbol": "TATACONSUM", "token": "3432"},
    {"symbol": "UPL",        "token": "11287"},
    {"symbol": "BPCL",       "token": "526"},
    {"symbol": "SHREECEM",   "token": "3103"},
]

_smart_api  = None
_auth_token = None


def get_market_status():
    now = datetime.now(IST)
    is_open = now.weekday() < 5 and dtime(9, 15) <= now.time() <= dtime(15, 30)
    return {
        "is_open":    is_open,
        "label":      "Market Open" if is_open else "Market Closed",
        "note":       None if is_open else "Showing last session historical data. Market is closed.",
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S IST")
    }


def _last_trading_day():
    """Return last weekday date as string YYYY-MM-DD."""
    d = datetime.now(IST).date()
    # Go back until we hit a weekday (Mon-Fri)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    # If today is a weekday but market hasn't opened yet, use previous day
    now = datetime.now(IST)
    if now.weekday() < 5 and now.time() < dtime(9, 15):
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _login():
    global _smart_api, _auth_token
    try:
        api_key     = os.environ.get("ANGEL_API_KEY")
        client_id   = os.environ.get("ANGEL_CLIENT_ID")
        password    = os.environ.get("ANGEL_PASSWORD")
        totp_secret = os.environ.get("ANGEL_TOTP_SECRET")

        if not all([api_key, client_id, password, totp_secret]):
            print("[Angel One] ERROR: Missing credentials.")
            print(f"  ANGEL_API_KEY     : {'SET' if api_key     else 'MISSING'}")
            print(f"  ANGEL_CLIENT_ID   : {'SET' if client_id   else 'MISSING'}")
            print(f"  ANGEL_PASSWORD    : {'SET' if password    else 'MISSING'}")
            print(f"  ANGEL_TOTP_SECRET : {'SET' if totp_secret else 'MISSING'}")
            return False

        _smart_api = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_secret).now()
        data = _smart_api.generateSession(
            clientCode=client_id,
            password=password,
            totp=totp
        )

        if data and data.get("status"):
            _auth_token = data["data"]["jwtToken"]
            print("[Angel One] Login successful.")
            return True

        print(f"[Angel One] Login REJECTED. Response: {data}")
        return False

    except Exception as e:
        print(f"[Angel One] Login exception: {e}")
        return False


def _ensure_logged_in():
    global _auth_token
    if not _auth_token:
        return _login()
    return True


def _fetch_live(stock):
    """Fetch live market data during market hours."""
    global _smart_api
    try:
        resp = _smart_api.getMarketData({
            "mode": "FULL",
            "exchangeTokens": {"NSE": [stock["token"]]}
        })
        if resp and resp.get("status") and resp.get("data"):
            fetched = resp["data"].get("fetched", [])
            if fetched:
                d          = fetched[0]
                ltp        = round(float(d.get("ltp",   0)), 2)
                close      = round(float(d.get("close", 0)), 2)
                open_      = round(float(d.get("open",  0)), 2)
                high       = round(float(d.get("high",  0)), 2)
                low        = round(float(d.get("low",   0)), 2)
                volume     = int(d.get("tradeVolume", 0))
                change     = round(ltp - close, 2) if close else 0
                change_pct = round((change / close * 100), 2) if close else 0
                return {
                    "symbol":         stock["symbol"],
                    "name":           NAME_MAP.get(stock["symbol"], stock["symbol"]),
                    "ltp":            ltp,
                    "open":           open_,
                    "high":           high,
                    "low":            low,
                    "close":          close,
                    "prev_close":     close,
                    "change":         change,
                    "change_percent": change_pct,
                    "volume":         volume,
                    "data_type":      "live"
                }
    except Exception as e:
        print(f"[Angel One] Live fetch error {stock['symbol']}: {e}")
    return None


def _fetch_historical(stock):
    """
    Fetch last session OHLC via getCandleData.
    Uses 7-day window to ensure we always get 2+ candles
    for prev_close calculation even over weekends/holidays.
    Candle format: [timestamp, open, high, low, close, volume]
    """
    global _smart_api
    try:
        now      = datetime.now(IST)
        to_dt    = now.strftime("%Y-%m-%d 15:30")
        from_dt  = (now - timedelta(days=7)).strftime("%Y-%m-%d 09:15")

        params = {
            "exchange":    "NSE",
            "symboltoken": stock["token"],
            "interval":    "ONE_DAY",
            "fromdate":    from_dt,
            "todate":      to_dt
        }
        resp = _smart_api.getCandleData(params)
        if resp and resp.get("status") and resp.get("data"):
            candles = resp["data"]
            if len(candles) >= 2:
                curr       = candles[-1]
                prev       = candles[-2]
                open_      = round(float(curr[1]), 2)
                high       = round(float(curr[2]), 2)
                low        = round(float(curr[3]), 2)
                close      = round(float(curr[4]), 2)
                volume     = int(curr[5])
                prev_close = round(float(prev[4]), 2)
                change     = round(close - prev_close, 2)
                change_pct = round((change / prev_close * 100) if prev_close else 0, 2)
                return {
                    "symbol":         stock["symbol"],
                    "name":           NAME_MAP.get(stock["symbol"], stock["symbol"]),
                    "ltp":            close,
                    "open":           open_,
                    "high":           high,
                    "low":            low,
                    "close":          close,
                    "prev_close":     prev_close,
                    "change":         change,
                    "change_percent": change_pct,
                    "volume":         volume,
                    "data_type":      "historical"
                }
            elif len(candles) == 1:
                curr  = candles[0]
                close = round(float(curr[4]), 2)
                return {
                    "symbol":         stock["symbol"],
                    "name":           NAME_MAP.get(stock["symbol"], stock["symbol"]),
                    "ltp":            close,
                    "open":           round(float(curr[1]), 2),
                    "high":           round(float(curr[2]), 2),
                    "low":            round(float(curr[3]), 2),
                    "close":          close,
                    "prev_close":     close,
                    "change":         0.0,
                    "change_percent": 0.0,
                    "volume":         int(curr[5]),
                    "data_type":      "historical"
                }
        print(f"[Angel One] No historical data for {stock['symbol']}. Response: {resp}")
    except Exception as e:
        print(f"[Angel One] Historical fetch error {stock['symbol']}: {e}")
    return None


def fetch_nifty50():
    """
    Fetch all Nifty50 stocks.
    - Market OPEN  → live getMarketData (real-time LTP)
    - Market CLOSED → historical getCandleData (last session OHLC)
    No MySQL — pure in-memory.
    """
    if not _ensure_logged_in():
        print("[Angel One] Cannot fetch — not logged in.")
        return []

    status   = get_market_status()
    is_open  = status["is_open"]
    mode     = "LIVE" if is_open else "HISTORICAL"
    print(f"[Angel One] Fetching in {mode} mode (market {'open' if is_open else 'closed'})...")

    results = []
    failed  = 0

    for stock in NIFTY50_STOCKS:
        data = _fetch_live(stock) if is_open else _fetch_historical(stock)
        if data:
            results.append(data)
        else:
            if failed == 0:
                print(f"[Angel One] First failure: {stock['symbol']} in {mode} mode.")
            failed += 1
            # Reset session on auth errors
            global _auth_token
            _auth_token = None if failed > 5 else _auth_token

    print(f"[Angel One] Done. Fetched {len(results)}/50. Failed: {failed}.")
    return results
