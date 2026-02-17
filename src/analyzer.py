import pandas as pd
from llm_service import LLMService
import time

class AnalysisEngine:
    def __init__(self):
        self.llm = LLMService()

    def fetch_data(self, symbol):
        """
        Fetch stock data from Settrade (Thai) or TwelveData/Finnhub (Global).
        """
        try:
            from thai_stock_helper import get_thai_stock_data as get_thai_quote
            from global_stock_helper import get_quote, get_company_profile, get_market_news, get_candles_and_indicators, get_general_market_news
        except ImportError as e:
            print(f"[IMPORT ERROR] {e}")
            return None

        symbol = symbol.upper().strip()
        is_thai = symbol.endswith('.BK')
        
        price = 0
        pe = 0
        yd = 0
        market_cap = "N/A"
        technicals = {"rsi": "N/A", "sma50": "N/A", "year_high": "-", "year_low": "-", "market_cap": "N/A"}
        prices_list = []
        news_items = []

        # Thai Stocks
        if is_thai:
            print(f"[ANALYZER] Thai Stock detected ({symbol}).")
            try:
                thai_data = get_thai_quote(symbol)
                if thai_data and thai_data.get('price', 0) > 0:
                    price = thai_data['price']
                    pe = thai_data.get('pe', 0)
                    yd = thai_data.get('yield', 0)
                    technicals['year_high'] = f"{thai_data.get('high', 0):.2f}"
                    technicals['year_low'] = f"{thai_data.get('low', 0):.2f}"

                    prices_list = thai_data.get('history', [])
                    
                    if prices_list and len(prices_list) >= 14:
                        try:
                            series = pd.Series(prices_list)
                            
                            # SMA 50
                            if len(series) >= 50:
                                sma50_val = series.rolling(window=50).mean().iloc[-1]
                                technicals['sma50'] = f"{sma50_val:.2f}"
                            
                            # RSI 14
                            delta = series.diff()
                            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                            rs = gain / loss
                            rsi_calc = 100 - (100 / (1 + rs))
                            val_rsi = rsi_calc.iloc[-1]
                            if not pd.isna(val_rsi):
                                technicals['rsi'] = f"{val_rsi:.2f}"
                        except Exception as e:
                            print(f"[CALC ERROR] {e}")

                else:
                    return None
            except Exception as e:
                print(f"[ANALYZER] Settrade Error: {e}")
                return None

        # Global Stocks
        else:
            try:
                quote = get_quote(symbol)
                if quote and quote.get('c', 0) > 0:
                    price = quote['c']
                
                # Profile (Fail silently for ETFs)
                try:
                    profile = get_company_profile(symbol) or {}
                    pe = profile.get('pe', 0)
                    cap = profile.get('marketCapitalization', 0)
                    market_cap = f"{cap:,.2f} M" if cap else "N/A"
                    yd = profile.get('dividendYield', 0) 
                    technicals['market_cap'] = market_cap
                except Exception as e: 
                    print(f"[PROFILE ERROR] {symbol}: {e}")
                
                # Technicals (Fail silently if Rate Limited)
                try:
                    time.sleep(1) 
                    tech_data = get_candles_and_indicators(symbol)
                    if tech_data:
                        prices_list = tech_data.get('history', [])
                        technicals.update(tech_data.get('technicals', {}))
                        if market_cap != "N/A": technicals['market_cap'] = market_cap
                except Exception as e: 
                    print(f"[TECH DATA ERROR] {symbol}: {e}")
                
                # News (Fail silently)
                try:
                    specific_news = get_market_news(symbol)
                    s_items = [n['headline'] for n in specific_news[:3] if 'headline' in n] if specific_news else []
                    macro_news = get_general_market_news()
                    m_items = [f"[GLOBAL MACRO] {n.get('headline', '')}" for n in macro_news[:2]]
                    news_items = s_items + m_items
                except Exception as e: 
                    print(f"[NEWS ERROR] {symbol}: {e}")

                # Final Check: As long as we have a price, we continue
                if price <= 0:
                    print(f"[ANALYZER] No price for {symbol}, aborting.")
                    return None

            except Exception as e:
                print(f"[ANALYZER] Global Stock Critical Error: {e}")
                return None

        return {
            "price": price,
            "pe_ratio": pe,
            "div_yield": yd, 
            "news": news_items,
            "history": prices_list,
            "technicals": technicals
        }

    def analyze(self, symbol, strategy="Value", goal="Medium", risk="Medium"):
        try:
            data = self.fetch_data(symbol)
            
            if not data:
                return {
                    "symbol": symbol,
                    "metrics": {
                        "Price": "N/A", "P/E": "-", "Yield": "-", "RSI": "-",
                        "price": 0.0, "pe_ratio": 0.0, "div_yield": 0.0, "market_cap": "N/A",
                        "technicals": {"rsi": "-", "sma50": "-", "year_high": "-", "year_low": "-"}
                    },
                    "signal": "ERROR",
                    "reason": "ไม่สามารถดึงข้อมูลได้ (ตลาดปิดหรืออยู่นอกเวลาทำการ)",
                    "news_summary": "-",
                    "history": [],
                    "news": [],
                    "technicals": {}
                }

            result = {
                "symbol": symbol,
                "metrics": {
                    "Price": f"{data['price']:,.2f}",
                    "P/E": f"{data['pe_ratio']:.2f}" if data['pe_ratio'] else "N/A",
                    "Yield": f"{data['div_yield']:.2f}%" if data['div_yield'] else "N/A",
                    "RSI": data['technicals'].get('rsi', 'N/A'),
                    
                    "price": data['price'],
                    "pe_ratio": data['pe_ratio'],
                    "div_yield": data['div_yield'],
                    "market_cap": data['technicals'].get('market_cap') if data['technicals'].get('market_cap') != "N/A" else None,
                    "technicals": data['technicals']
                },
                "history": data['history'],
                "news": data['news'],
                "technicals": data['technicals']
            }
            
            result.update(result['metrics'])

            # AI Analysis (One-Shot: Signal + Reason + News Summary)
            try:
                ai_output = self.llm.analyze_stock_ai(
                    symbol, data['price'], data['pe_ratio'], data['div_yield'], 
                    data.get('news', []), strategy=strategy, goal=goal, technicals=data['technicals']
                )
                
                import re
                # Robust Regex Parsing for "SIGNAL | REASON | NEWS_SUMMARY"
                # Matches: (BUY/SELL...) | (Text) | (Text)
                pattern = r"(BUY|SELL|HOLD|WAIT)\s*\|\s*(.*?)\s*\|\s*(.*)"
                match = re.search(pattern, ai_output, re.DOTALL | re.IGNORECASE)
                
                found_signal = "WAIT"
                reason_text = "รอการวิเคราะห์เพิ่มเติม"
                news_summary_text = "ไม่มีข่าวสำคัญในช่วงนี้"

                valid_signals = ["BUY", "SELL", "HOLD", "WAIT"]

                if match:
                    # Regex Success
                    found_signal = match.group(1).upper()
                    reason_text = match.group(2).strip()
                    news_summary_text = match.group(3).strip()
                else:
                    # Fallback: Manual Split (Handle cases where | might be missing or format slightly off)
                    parts = [p.strip() for p in ai_output.split('|')]
                    if len(parts) >= 1:
                        # Attempt to find signal in first part
                        sig_candidate = parts[0].upper()
                        for vs in valid_signals:
                            if vs in sig_candidate:
                                found_signal = vs
                                break
                    if len(parts) >= 2: reason_text = parts[1]
                    if len(parts) >= 3: news_summary_text = parts[2]

                result['signal'] = found_signal
                result['reason'] = reason_text
                result['news_summary'] = news_summary_text
                
            except Exception as e:
                print(f"[AI ERROR] {e}")
                result['signal'] = "WAIT"
                result['reason'] = "AI ประมวลผลขัดข้อง"
                result['news_summary'] = "-"

            return result

        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)}"
            print(f"[CRITICAL ANALYZE ERROR] {err_msg}")
            return {
                "symbol": symbol,
                "metrics": {
                    "Price": "N/A", "P/E": "-", "Yield": "-", "RSI": "-",
                    "price": 0.0, "pe_ratio": 0.0, "div_yield": 0.0, "market_cap": "N/A",
                    "technicals": {"rsi": "-", "sma50": "-", "year_high": "-", "year_low": "-"}
                },
                "signal": "ERROR",
                "reason": f"Error: {err_msg[:100]}",
                "news_summary": "-",
                "history": [],
                "news": [],
                "technicals": {}
            }
