from SmartApi import SmartConnect
import pyotp
import pytz
import os
from datetime import datetime, time as dtime

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
]

# Module-level SmartConnect instance — reused across requests
_smart_api  = None
_auth_token = None


def get_market_status():
    now = datetime.now(IST)
    is_open = now.weekday() < 5 and dtime(9, 15) <= now.time() <= dtime(15, 30)
    return {
        "is_open":    is_open,
        "label":      "Market Open" if is_open else "Market Closed",
        "note":       None if is_open else "Showing last session data. Market is closed.",
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S IST")
    }


def _login():
    global _smart_api, _auth_token
    try:
        api_key     = os.environ.get("ANGEL_API_KEY")
        client_id   = os.environ.get("ANGEL_CLIENT_ID")
        password    = os.environ.get("ANGEL_PASSWORD")
        totp_secret = os.environ.get("ANGEL_TOTP_SECRET")

        if not all([api_key, client_id, password, totp_secret]):
            print("[Angel One] ERROR: Missing credentials in environment variables.")
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


def fetch_nifty50():
    """
    Fetch all 50 Nifty stocks from Angel One SmartAPI.
    Uses getMarketData (live during market hours).
    No MySQL — pure in-memory.
    """
    if not _ensure_logged_in():
        print("[Angel One] Cannot fetch — not logged in.")
        return []

    print("[Angel One] Fetching Nifty50 market data...")
    results = []
    failed  = 0

    for stock in NIFTY50_STOCKS:
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

                    results.append({
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
                        "volume":         volume
                    })
                    continue

            # Empty response — market may be closed
            if failed == 0:
                print(f"[Angel One] Empty response for {stock['symbol']}. "
                      f"Market may be closed (getMarketData returns blank after hours).")
            failed += 1

        except Exception as e:
            print(f"[Angel One] Error fetching {stock['symbol']}: {e}")
            # Session expired — force re-login on next call
            if "token" in str(e).lower() or "auth" in str(e).lower():
                global _auth_token
                _auth_token = None
            failed += 1

    print(f"[Angel One] Done. Fetched {len(results)}/50 stocks. Failed: {failed}.")
    return results
