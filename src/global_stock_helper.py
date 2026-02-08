import requests
import requests
try:
    from src.config import Config
except ImportError:
    from config import Config
import time
import datetime

# --- CONFIGS ---
FINNHUB_KEY = Config.FINNHUB_API_KEY
FINNHUB_URL = "https://finnhub.io/api/v1"

TWELVE_KEY = Config.TWELVE_DATA_API_KEY
TWELVE_URL = "https://api.twelvedata.com"

# --- HELPER FUNCTIONS ---

def _get_finnhub(endpoint, params={}):
    """ Get data from Finnhub (News Only) """
    params['token'] = FINNHUB_KEY
    try:
        # Reduced timeout to 3s to prevent hanging on slow news/profile fetch
        res = requests.get(f"{FINNHUB_URL}{endpoint}", params=params, timeout=3)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[FINNHUB ERROR] {endpoint}: {e}")
        return None

def _get_twelve(endpoint, params={}):
    """ Get data from Twelve Data (Quote, Timeseries) """
    if not TWELVE_KEY:
        print("[TWELVE ERROR] No API Key provided")
        return None
        
    params['apikey'] = TWELVE_KEY
    try:
        res = requests.get(f"{TWELVE_URL}{endpoint}", params=params, timeout=8) # Longer timeout for heavy data
        res.raise_for_status()
        data = res.json()
        if 'code' in data and data['code'] != 200:
             print(f"[TWELVE API ERROR] {data.get('message')}")
             return None
        return data
    except Exception as e:
        print(f"[TWELVE NETWORK ERROR] {endpoint}: {e}")
        return None

# --- PUBLIC FUNCTIONS (Hybrid Strategy: Twelve Data + Finnhub) ---

def get_quote(symbol):
    """ 
    Get Realtime Price from Twelve Data (1 Credit)
    """
    # 1. Quote Endpoint
    q_data = _get_twelve("/quote", {"symbol": symbol})
    if not q_data: return None

    try:
        return {
            "c": float(q_data.get("close", 0)),
            "d": float(q_data.get("change", 0)),
            "dp": float(q_data.get("percent_change", 0)),
            "h": float(q_data.get("high", 0)),
            "l": float(q_data.get("low", 0)),
            "o": float(q_data.get("open", 0)),
            "pc": float(q_data.get("previous_close", 0)),
            "name": q_data.get("name", symbol)
        }
    except Exception as e:
        print(f"[QUOTE PARSE ERROR] {symbol}: {e}")
        return None

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
try:
    from init_cache_db import GlobalStockInfo
except ImportError:
    from src.init_cache_db import GlobalStockInfo
try:
    from config import Config
except ImportError:
    from src.config import Config

# DB Setup for Cache
engine = create_engine(Config.DATABASE_URL)
Session = sessionmaker(bind=engine)

def get_company_profile(symbol):
    """ 
    Get Profile from Cache first, then Finnhub.
    """
    session = Session()
    try:
        # 1. Check Cache
        cached = session.query(GlobalStockInfo).filter_by(symbol=symbol).first()
        if cached:
            # Check freshness (e.g., 30 days) - Optional, implementation simplified
            now = datetime.datetime.utcnow()
            age = (now - cached.updated_at).days
            
            # Logic: Return cache only if it seems valid (has P/E) OR if it's very recent (< 1 day)
            # If P/E is 0, we might want to retry fetching unless we just fetched it today.
            # Logic: Return cache only if it seems valid (has P/E)
            # If P/E is 0, we FORCE re-fetch (Fall through to Finnhub)
            if age < 30 and (str(cached.pe_ratio) != '0.0' and cached.pe_ratio != 0):
                print(f"[CACHE HIT] Profile for {symbol} (Age: {age} days)")
                return {
                    "pe": cached.pe_ratio,
                    "marketCapitalization": float(cached.market_cap) if cached.market_cap and cached.market_cap != 'N/A' else 0,
                    "dividendYield": cached.dividend_yield,
                    "name": cached.company_name
                }
            
            if age < 30:
                print(f"[CACHE HIT-BUT-INVALID] Profile for {symbol} (Age: {age} days) has P/E=0. Refetching...")
        
        # 2. Fetch Finnhub
        print(f"[CACHE MISS] Fetching Profile for {symbol} from Finnhub...")
        profile = _get_finnhub('/stock/profile2', {'symbol': symbol})
        
        if profile:
            # 3. Save to Cache
            pe = profile.get('pe', 0) or 0
            cap = profile.get('marketCapitalization', 0) or 0
            yd = profile.get('dividendYield', 0) or 0
            name = profile.get('name', symbol)
            
            # Additional attributes if available (Fallback to Metric endpoint)
            if pe == 0 or yd == 0 or cap == 0: 
                 try:
                     print(f"[FINNHUB METRIC] Fetching extra metrics for {symbol}...")
                     # Reduced timeout for metrics too
                     metrics = _get_finnhub('/stock/metric', {'symbol': symbol, 'metric': 'all'})
                     if metrics and 'metric' in metrics:
                         m = metrics['metric']
                         # Try multiple keys for P/E
                         pe = pe or m.get('peBasicExclExtraTTM') or m.get('peTTM') or m.get('peNormalized') or m.get('peExclExtraTTM') or 0
                         # Try multiple keys for Yield
                         yd = yd or m.get('dividendYieldIndicatedAnnual') or m.get('dividendYield5Y') or m.get('currentDividendYieldTTM') or 0
                         # Try multiple keys for Cap
                         cap = cap or m.get('marketCapitalization') or 0
                 except Exception as e:
                     print(f"[FINNHUB METRIC ERROR] {e}")

            if cached:
                cached.pe_ratio = pe
                cached.market_cap = str(cap)
                cached.dividend_yield = yd
                cached.company_name = name
                cached.updated_at = datetime.datetime.utcnow()
            else:
                new_entry = GlobalStockInfo(
                    symbol=symbol,
                    company_name=name,
                    pe_ratio=pe,
                    market_cap=str(cap),
                    dividend_yield=yd
                )
                session.add(new_entry)
            
            session.commit()
            return profile
            
        else:
            # Finnhub Failed/Empty -> Return Cache even if old? Or empty.
            if cached:
                print(f"[CACHE FALLBACK] Using old data for {symbol}")
                return {
                    "pe": cached.pe_ratio,
                    "marketCapitalization": float(cached.market_cap) if cached.market_cap and cached.market_cap != 'N/A' else 0,
                    "dividendYield": cached.dividend_yield,
                    "name": cached.company_name
                }
            return {}

    except Exception as e:
        print(f"[CACHE ERROR] {e}")
        return {}
    finally:
        session.close()

def get_market_news(symbol):
    """ Get News from Finnhub (0 Twelve Data Credits) """
    end = datetime.date.today()
    start = end - datetime.timedelta(days=3)
    return _get_finnhub('/company-news', {
        'symbol': symbol,
        'from': start.strftime('%Y-%m-%d'),
        'to': end.strftime('%Y-%m-%d')
    }) or []

def get_candles_and_indicators(symbol):
    """ 
    Get Candles from Twelve Data (1 Credit)
    Calculate indicators manually 
    """
    # 1. Get Time Series (Daily)
    ts_data = _get_twelve("/time_series", {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 60 
    })
    
    if not ts_data or 'values' not in ts_data:
        return None

    # Parse Values (Twelve returns Newest First)
    candles = ts_data['values']
    candles.reverse() # Oldest -> Newest
    
    closes = [float(c['close']) for c in candles]
    highs = [float(c['high']) for c in candles]
    lows = [float(c['low']) for c in candles]

    # Calculate Indicators
    import pandas as pd
    try:
        series = pd.Series(closes)

        # SMA 50
        sma50 = "N/A"
        if len(series) >= 50:
            val = series.rolling(window=50).mean().iloc[-1]
            sma50 = f"{val:.2f}"
            
        # RSI 14
        rsi = "N/A"
        if len(series) >= 14:
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_val = 100 - (100 / (1 + rs))
            rsi = f"{rsi_val.iloc[-1]:.2f}"

        return {
            "history": closes, 
            "technicals": {
                "rsi": rsi,
                "sma50": sma50,
                "year_high": f"{max(highs):.2f}" if highs else "-",
                "year_low": f"{min(lows):.2f}" if lows else "-",
                "market_cap": "N/A" # Profile gets this
            }
        }
    except Exception as e:
        print(f"[INDICATOR ERROR] {symbol}: {e}")
        return {"history": closes, "technicals": {}}

def get_general_market_news():
    """ 
    Get General Market News from Finnhub (Fallback when specific news is missing).
    """
    try:
        # category='general' for US/Global macro
        news = _get_finnhub('/news', {'category': 'general'})
        if news and isinstance(news, list):
            # Take top 5 to avoid token overload
            return news[:5]
        return []
    except Exception as e:
        print(f"[MARKET NEWS ERROR] {e}")
        return []
