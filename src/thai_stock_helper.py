from settrade_v2 import Investor
from config import Config
import logging

# Global Cache for Investor (Singleton Pattern)
_INVESTOR_INSTANCE = None

class SettradeHelper:
    def __init__(self):
        global _INVESTOR_INSTANCE
        
        self.app_id = Config.SETTRADE_APP_ID
        self.app_secret = Config.SETTRADE_APP_SECRET
        self.broker_id = Config.SETTRADE_BROKER_ID
        self.app_code = Config.SETTRADE_APP_CODE
        self.is_sandbox = Config.SETTRADE_IS_SANDBOX
        
        if _INVESTOR_INSTANCE:
             self.investor = _INVESTOR_INSTANCE
             # logging.info("[SETTRADE] Reusing Cached Investor")
        else:
             try:
                 # Sandbox Parameter Logic
                 b_id = "SANDBOX" if self.is_sandbox else self.broker_id
                 a_code = "SANDBOX" if self.is_sandbox else self.app_code
                 
                 self.investor = Investor(
                     app_id=self.app_id,
                     app_secret=self.app_secret,
                     broker_id=b_id,
                     app_code=a_code,
                     is_auto_queue=False
                 )
                 _INVESTOR_INSTANCE = self.investor
                 print("[SETTRADE] Login Successful (New Session)")
             except Exception as e:
                 print(f"[SETTRADE LOGIN ERROR] {e}")
                 self.investor = None

    def get_quote(self, symbol):
        """ Get Realtime Quote from SET """
        if not self.investor:
            print("[SETTRADE] Investor not initialized")
            return None
            
        try:
            # Clean Symbol
            symbol = symbol.upper().replace(".BK", "").strip()
            
            # Get Market Data Object
            market = self.investor.MarketData()
            quote = market.get_quote_symbol(symbol)
            if not quote: return None
            
            # Helper to safely get float
            def safe_float(val):
                try: 
                    if val is None or val == '-': return 0.0
                    return float(val)
                except: return 0.0

            # Handle Attributes (SDK v2)
            last = getattr(quote, 'last', 0)
            if not last: last = quote.get('last', 0)
            if safe_float(last) == 0: return None

            return {
                "price": safe_float(last),
                "change": safe_float(getattr(quote, 'change', 0)),
                "percent_change": safe_float(getattr(quote, 'percentChange', 0)),
                "high": safe_float(getattr(quote, 'high', 0)),
                "low": safe_float(getattr(quote, 'low', 0)),
                "vol": safe_float(getattr(quote, 'volume', 0)),
                "val": safe_float(getattr(quote, 'value', 0)),
                "pe": safe_float(getattr(quote, 'pe', 0)),         
                "pbv": safe_float(getattr(quote, 'pbv', 0)),
                "yield": safe_float(getattr(quote, 'yield', 0))    
            }
        except Exception as e:
            print(f"[SETTRADE QUOTE ERROR] {symbol}: {e}")
            return None

    def get_candles(self, symbol, interval='1d', limit=60):
        """ Get Historical Candles """
        if not self.investor: return None
        try:
            symbol = symbol.upper().replace(".BK", "").strip()
            market = self.investor.MarketData()
            
            # history args: symbol, interval, limit
            candles = market.get_candlestick(symbol, interval, limit=limit)
             
            # Expected Structure check
            if not candles or 'close' not in candles:
                return None
                
            return {
                "time": candles.get('time', []),
                "close": [float(x) for x in candles.get('close', [])],
                "high": [float(x) for x in candles.get('high', [])],
                "low": [float(x) for x in candles.get('low', [])]
            }

        except Exception as e:
            print(f"[SETTRADE CANDLES ERROR] {symbol}: {e}")
            return None

# Wrapper Function used by analyzer.py
def get_thai_stock_data(symbol):
    helper = SettradeHelper() # Will use Cached Instance
    
    # 1. Get Quote (Realtime)
    quote = helper.get_quote(symbol)
    if not quote: return None
    
    # 2. Get History (Candles)
    history = []
    # Fetch 60 days to support SMA50 calculation
    candles = helper.get_candles(symbol, interval='1d', limit=60)
    if candles and candles['close']:
        history = candles['close']
        
    # Merge History into result
    quote['history'] = history
    
    return quote
