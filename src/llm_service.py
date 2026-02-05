from config import Config

# New Google GenAI SDK (v2026 Compatible)
try:
    from google import genai
except ImportError:
    genai = None
    print("Warning: 'google-genai' package not found. Please install via: pip install google-genai")

class LLMService:
    def __init__(self):
        self.client = None
        self.model_name = Config.GEMINI_MODEL_NAME
        
        # Initialize Client
        if Config.GEMINI_API_KEY:
             if genai:
                 try:
                     self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
                 except Exception as e:
                     print(f"GenAI Client Init Error: {e}")
             else:
                 print("Warning: google-genai library is missing.")
        else:
            print("Warning: GEMINI_API_KEY not found in environment.")

    def _call_gemini(self, prompt):
        if not self.client:
            return "AI Service Not Configured."
        try:
            # New API Call Structure
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            return f"AI Connection Error: {str(e)}"

    def analyze_stock_ai(self, symbol, price, pe_ratio, div_yield, news_summary, strategy="General", goal="Medium", technicals=None):
        """
        Uses Gemini (via google.genai) to analyze stock based on comprehensive financial data.
        """
        
        # Build Technical Context
        tech_context = ""
        if technicals:
            tech_context = (
                f"Technical Indicators:\n"
                f"- RSI (14): {technicals.get('rsi', 'N/A')}\n"
                f"- SMA (50): {technicals.get('sma50', 'N/A')}\n"
                f"- Market Cap: {technicals.get('market_cap', 'N/A')}\n"
                f"- 52W Range: {technicals.get('year_low', 'N/A')} - {technicals.get('year_high', 'N/A')}\n"
            )

        prompt = (
            f"Analyze stock {symbol} for a user with Strategy='{strategy}' and Goal='{goal}'.\n"
            f"Current Data: Price={price}, P/E={pe_ratio}, DivYield={div_yield}%\n"
            f"{tech_context}"
            f"News Summary: {news_summary}\n\n"
            "Task: Act as a financial analyst. Determine the Recommendation (BUY/SELL/HOLD/WAIT).\n"
            "Rules:\n"
            "1. Consider the User's Strategy and Goal in your decision.\n"
            "2. Reason MUST be a single short sentence in Thai language.\n"
            "3. Output a SINGLE LINE in this exact format:\n"
            "Category | Recommendation | Reason\n"
            "Example: Value | BUY | ราคาต่ำกว่ามูลค่าพื้นฐานและปันผลน่าสนใจเหมาะกับการถือยาว"
        )
        
        return self._call_gemini(prompt)

    def summarize_news(self, news_list):
        if not news_list:
            return "ไม่มีข่าวสารสำคัญในช่วงนี้"
            
        # Limit to top 3 news for speed context window efficiency
        combined_news = "\n- ".join(news_list[:3])
        
        prompt = (
            f"Summarize these stock news headlines into one short Thai paragraph (2-3 lines max).\n"
            f"Headlines:\n{combined_news}\n\n"
            f"Thai Summary:"
        )
        
        return self._call_gemini(prompt)
