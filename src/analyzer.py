import pandas as pd
from llm_service import LLMService
import time

class AnalysisEngine:
    def __init__(self):
        self.llm = LLMService()

    def fetch_data(self, symbol):
        """
        Smart Fetch: 
        - If .BK -> Go straight to Settrade (Skip Finnhub latency)
        - If US -> Try Finnhub -> Fallback Settrade? (No, Settrade only Thai) -> Fail
        """
        from thai_stock_helper import get_thai_stock_data as get_thai_quote
        from global_stock_helper import get_quote, get_company_profile, get_market_news, get_candles_and_indicators

        symbol = symbol.upper()
        is_thai = symbol.endswith('.BK')
        
        # Data Containers
        price = 0
        pe = 0
        yd = 0
        market_cap = "N/A"
        technicals = {"rsi": "N/A", "sma50": "N/A", "year_high": "-", "year_low": "-", "market_cap": "N/A"}
        prices_list = []
        news_items = []

        # --- PATH 1: THAI STOCK (.BK) ---
        if is_thai:
            print(f"[ANALYZER] Thai Stock detected ({symbol}). Using Settrade directly.")
            try:
                thai_data = get_thai_quote(symbol)
                if thai_data and thai_data.get('price', 0) > 0:
                    price = thai_data['price']
                    pe = thai_data.get('pe', 0)
                    yd = thai_data.get('yield', 0)
                    # Year Low/High
                    technicals['year_high'] = f"{thai_data.get('high', 0):.2f}"
                    technicals['year_low'] = f"{thai_data.get('low', 0):.2f}"
                    # Market Cap (Estimate or N/A) -- Settrade doesn't give total shares easily in this endpoint
                    if thai_data.get('val', 0) > 0:
                         # Value / Vol approx Price? No, Value is turnover. 
                         pass 

                    # History & Technicals
                    prices_list = thai_data.get('history', [])
                    
                    # Calculate Indicators (Pandas)
                    if prices_list and len(prices_list) >= 14:
                        try:
                            # Convert to Series
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
                    print(f"[ANALYZER] Settrade returned no data for {symbol}")
                    return None
            except Exception as e:
                print(f"[ANALYZER] Settrade Error: {e}")
                return None

        # --- PATH 2: US/GLOBAL STOCK (No .BK) ---
        else:
            try:
                # 1. Quote (Price) - Twelve Data
                quote = get_quote(symbol)
                if quote and quote.get('c', 0) > 0:
                    price = quote['c']
                    
                    # 2. Profile (PE, Cap, Yield) - Finnhub
                    # Note: Finnhub 'profile2' is free and lightweight.
                    try:
                        profile = get_company_profile(symbol) or {}
                        pe = profile.get('pe', 0)
                        cap = profile.get('marketCapitalization', 0)
                        market_cap = f"{cap:,.2f} M" if cap else "N/A"
                        yd = profile.get('dividendYield', 0) 
                        technicals['market_cap'] = market_cap
                    except Exception as e: 
                        print(f"[PROFILE ERROR] {e}")
                    
                    # 3. Candles & Technicals (History, RSI, SMA) - Twelve Data
                    # Rate Limit Protection: 8 req/min = 1 req every 7.5s.
                    # Since we already called quote (1 credit), candles cost another (1 credit). 
                    # Total 2 credits per stock. 4 stocks per minute max if sequential.
                    try:
                        time.sleep(1) # Small delay to be polite
                        tech_data = get_candles_and_indicators(symbol)
                        if tech_data:
                            prices_list = tech_data.get('history', [])
                            technicals.update(tech_data.get('technicals', {}))
                            # Re-assert market cap
                            if market_cap != "N/A": technicals['market_cap'] = market_cap
                    except Exception as e: 
                        print(f"[TECH DATA ERROR] {e}")
                    
                    # 4. News - Finnhub
                    try:
                        raw_news = get_market_news(symbol)
                        for n in raw_news:
                            if 'headline' in n: news_items.append(n['headline'])
                    except: pass
                else:
                    print(f"[ANALYZER] No Quote Data for {symbol}")
                    return None

            except Exception as e:
                print(f"[ANALYZER] Global Stock Error: {e}")
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
            # Fetch Data
            data = self.fetch_data(symbol)
            
            if not data:
                return {
                    "symbol": symbol,
                    "metrics": {
                        "Price": "N/A", "P/E": "-", "Yield": "-", "RSI": "-",
                        "price": None, "pe_ratio": None, "div_yield": None, "market_cap": None,
                        "technicals": {} # Crucial: Must exist for template safe_get
                    },
                    "signal": "WAIT",
                    "reason": "ไม่สามารถดึงข้อมูลได้ (ตลาดปิดหรืออยู่นอกเวลาทำการ)",
                    "news_summary": "-",
                    "history": [],
                    "news": [],
                    "technicals": {}
                }

            # Prepare Result Dict
            result = {
                "symbol": symbol,
                "metrics": {
                    # Display Strings
                    "Price": f"{data['price']:,.2f}",
                    "P/E": f"{data['pe_ratio']:.2f}" if data['pe_ratio'] else "N/A",
                    "Yield": f"{data['div_yield']:.2f}%" if data['div_yield'] else "N/A",
                    "RSI": data['technicals'].get('rsi', 'N/A'),
                    
                    # Raw Values for Template (Fix Missing Data Issue)
                    "price": data['price'],
                    "pe_ratio": data['pe_ratio'] if data['pe_ratio'] and data['pe_ratio'] != 0 else None,
                    "div_yield": data['div_yield'] if data['div_yield'] and data['div_yield'] != 0 else None,
                    "market_cap": data['technicals'].get('market_cap') if data['technicals'].get('market_cap') != "N/A" else None,
                    "technicals": data['technicals'] # Pass nested technicals
                },
                "history": data['history'],
                "news": data['news'],
                "technicals": data['technicals']
            }
            
            # Flatten metrics to top-level for Template compatibility
            result.update(result['metrics'])

            # AI Analysis (One-Shot: Signal + Reason + News Summary)
            # AI Analysis (One-Shot: Signal + Reason + News Summary)
            try:
                ai_output = self.llm.analyze_stock_ai(
                    symbol, data['price'], data['pe_ratio'], data['div_yield'], 
                    data.get('news', []), strategy=strategy, goal=goal, technicals=data['technicals']
                )
                
                # Smart Parsing for Signal | Reason | News Summary
                parts = [p.strip() for p in ai_output.split('|')]
                
                valid_signals = ["BUY", "SELL", "HOLD", "WAIT"]
                found_signal = "WAIT"
                reason_text = "รอการวิเคราะห์เพิ่มเติม"
                news_summary_text = "ไม่มีข่าวสำคัญในช่วงนี้"

                # Parse Parts (Index 0: Signal, 1: Reason, 2: News)
                if len(parts) >= 1:
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
        print(f"[CRITICAL ANALYZE ERROR] {e}")
        return None
