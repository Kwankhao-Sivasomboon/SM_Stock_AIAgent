import yfinance as yf
import pandas as pd
from llm_service import LLMService

class AnalysisEngine:
    def __init__(self):
        self.llm = LLMService()

    def fetch_data(self, symbol):
        """Fetches financial data including technical indicators"""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                ticker = yf.Ticker(symbol)
                
                # 1. Fetch History (1 Year for Technicals)
                try:
                    hist = ticker.history(period='1y')
                except Exception:
                    hist = pd.DataFrame()

                if hist.empty:
                    # Retry logic handled by outer loop
                    if attempt < max_retries: continue
                    return None

                current_price = hist['Close'].iloc[-1]
                prices_list = hist['Close'].tail(30).tolist() # Sparkline data (30 days)

                # 2. Calculate Technicals (RSI, SMA)
                technicals = {}
                try:
                    # SMA 50
                    if len(hist) >= 50:
                        technicals['sma50'] = f"{hist['Close'].rolling(window=50).mean().iloc[-1]:.2f}"
                    else:
                        technicals['sma50'] = "N/A"

                    # RSI 14
                    delta = hist['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    technicals['rsi'] = f"{rsi.iloc[-1]:.2f}"
                except:
                    technicals['rsi'] = "N/A"
                    technicals['sma50'] = "N/A"

                # 3. Fetch Info (Fundamental)
                pe = 0
                yd = 0
                rec_key = 'none'
                try:
                    info = ticker.info
                    pe = info.get('trailingPE') or info.get('forwardPE') or 0
                    yd = (info.get('dividendYield', 0) or 0) * 100
                    rec_key = info.get('recommendationKey', 'none')
                    
                    # Add Info Technicals
                    technicals['market_cap'] = f"{info.get('marketCap', 0):,}"
                    technicals['year_high'] = f"{info.get('fiftyTwoWeekHigh', 0):.2f}"
                    technicals['year_low'] = f"{info.get('fiftyTwoWeekLow', 0):.2f}"
                except:
                    pass

                # 4. News
                news_items = []
                try:
                    raw_news = ticker.news
                    if raw_news:
                        for n in raw_news[:5]:
                             title = n.get('title') or n.get('content', {}).get('title')
                             if title: news_items.append(title)
                except:
                    pass
                
                return {
                    "price": current_price,
                    "pe_ratio": pe,
                    "div_yield": yd,
                    "recommendation_key": rec_key,
                    "news": news_items,
                    "history": prices_list,
                    "technicals": technicals
                }

            except Exception as e:
                print(f"Fetch Error {symbol}: {e}")
                if attempt == max_retries: return None

        return None

    def analyze(self, symbol, strategy="Value", goal="Medium", risk="Medium"):
        """
        Analyzes a stock based on the strategy, goal, and risk.
        """
        data = self.fetch_data(symbol)
        if not data:
            return {
                "symbol": symbol,
                "metrics": {"Price": "N/A", "P/E": "-", "Yield": "-"},
                "signal": "ERROR",
                "reason": "ไม่สามารถดึงข้อมูลได้ (Data Unavailable)"
            }

        result = {
            "symbol": symbol,
            "metrics": {
                "Price": f"{data['price']:,.2f}",
                "P/E": f"{data['pe_ratio']:.2f}" if data['pe_ratio'] else "N/A",
                "Yield": f"{data['div_yield']:.2f}%" if data['div_yield'] else "N/A",
                "RSI": data['technicals']['rsi']
            },
            "history": data['history'],
            "news": data['news'],
            "technicals": data['technicals'] # Pass full tech data for template if needed
        }

        # --- AI Analysis ---
        # Generate summary and signal using Gemini
        try:
            # News Summary
            news_summary = ""
            if data['news']:
                news_summary = self.llm.summarize_news(data['news'])
                result['news_summary'] = news_summary
            
            # AI Decision
            ai_output = self.llm.analyze_stock_ai(
                symbol, data['price'], data['pe_ratio'], data['div_yield'], 
                news_summary, strategy=strategy, goal=goal, technicals=data['technicals']
            )
            
            # Parse AI Output (Category | Recommendation | Reason)
            parts = ai_output.split('|')
            if len(parts) >= 3:
                result['signal'] = parts[1].strip()
                result['reason'] = parts[2].strip()
            else:
                # Fallback format if AI goes rogue
                result['signal'] = "HOLD" 
                result['reason'] = ai_output
                
        except Exception as e:
            print(f"Analysis Error: {e}")
            result['signal'] = "WAIT"
            result['reason'] = "ระบบ AI ขัดข้อง กำลังตรวจสอบ"

        return result
