from flask import Blueprint, jsonify, request
from services.market_data import fetch_nifty50, get_market_status
from datetime import datetime
import threading

stocks_bp = Blueprint('stocks', __name__)

_cache = {"data": [], "fetched_at": None}
_lock  = threading.Lock()   # prevents simultaneous fetches on cache miss


def _get_data():
    """Return cached data. If empty, fetch once (locked so only one thread fetches)."""
    if _cache["data"]:
        return _cache["data"]
    with _lock:
        # Re-check inside lock — another thread may have fetched while we waited
        if not _cache["data"]:
            _cache["data"]      = fetch_nifty50()
            _cache["fetched_at"] = datetime.now().isoformat()
    return _cache["data"]


def _refresh():
    with _lock:
        _cache["data"]      = fetch_nifty50()
        _cache["fetched_at"] = datetime.now().isoformat()
    return _cache["data"]


@stocks_bp.route('/api/top-gainers')
def top_gainers():
    try:
        limit = request.args.get('limit', 10, type=int)
        data  = sorted(_get_data(), key=lambda x: x['change_percent'], reverse=True)
        return jsonify({
            "success": True,
            "data": data[:limit],
            "count": len(data[:limit]),
            "fetched_at": _cache["fetched_at"],
            "market_status": get_market_status()
        })
    except Exception as e:
        print(f"top-gainers error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stocks_bp.route('/api/top-losers')
def top_losers():
    try:
        limit = request.args.get('limit', 10, type=int)
        data  = sorted(_get_data(), key=lambda x: x['change_percent'])
        return jsonify({
            "success": True,
            "data": data[:limit],
            "count": len(data[:limit]),
            "fetched_at": _cache["fetched_at"],
            "market_status": get_market_status()
        })
    except Exception as e:
        print(f"top-losers error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stocks_bp.route('/api/all-stocks')
def all_stocks():
    try:
        data = _get_data()
        return jsonify({
            "success": True,
            "data": data,
            "count": len(data),
            "fetched_at": _cache["fetched_at"],
            "market_status": get_market_status()
        })
    except Exception as e:
        print(f"all-stocks error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stocks_bp.route('/api/market-summary')
def market_summary():
    try:
        data = _get_data()
        if not data:
            return jsonify({"success": False, "error": "No data available"}), 500
        gainers   = [s for s in data if s['change_percent'] > 0]
        losers    = [s for s in data if s['change_percent'] < 0]
        unchanged = [s for s in data if s['change_percent'] == 0]
        return jsonify({
            "success": True,
            "data": {
                "total_stocks":     len(data),
                "gainers_count":    len(gainers),
                "losers_count":     len(losers),
                "unchanged_count":  len(unchanged),
                "average_change":   round(sum(s['change_percent'] for s in data) / len(data), 2),
                "top_gainer":       max(data, key=lambda x: x['change_percent']),
                "top_loser":        min(data, key=lambda x: x['change_percent']),
                "market_sentiment": "Bullish" if len(gainers) > len(losers) else "Bearish"
            },
            "fetched_at": _cache["fetched_at"],
            "market_status": get_market_status()
        })
    except Exception as e:
        print(f"market-summary error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stocks_bp.route('/api/refresh', methods=['POST'])
def refresh():
    try:
        data = _refresh()
        return jsonify({
            "success": True,
            "message": f"Refreshed {len(data)} stocks",
            "fetched_at": _cache["fetched_at"]
        })
    except Exception as e:
        print(f"refresh error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stocks_bp.route('/api/nifty-index')
def nifty_index():
    """Fetch Nifty 50 index value from Angel One."""
    try:
        from services.market_data import _login
        import os

        smart_api = _login()
        if not smart_api:
            return jsonify({"success": False, "error": "Login failed"}), 500

        # Nifty 50 index token: 99926000, exchange: NSE
        resp = smart_api.getMarketData({
            "mode": "LTP",
            "exchangeTokens": {"NSE": ["99926000"]}
        })

        if resp and resp.get("status") and resp.get("data"):
            fetched = resp["data"].get("fetched", [])
            if fetched:
                ltp        = round(float(fetched[0].get("ltp", 0)), 2)
                close      = round(float(fetched[0].get("close", 0)), 2)
                change     = round(ltp - close, 2) if close else 0
                change_pct = round((change / close * 100), 2) if close else 0
                return jsonify({
                    "success":        True,
                    "index":          "NIFTY 50",
                    "ltp":            ltp,
                    "close":          close,
                    "change":         change,
                    "change_percent": change_pct,
                    "market_status":  get_market_status()
                })

        return jsonify({"success": False, "error": "No index data"}), 500

    except Exception as e:
        print(f"nifty-index error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
