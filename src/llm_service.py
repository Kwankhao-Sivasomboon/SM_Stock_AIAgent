from config import Config
import logging

try:
    import google.generativeai as genai
except ImportError:
    genai = None
    print("Warning: 'google-generativeai' package not found. Please install via: pip install google-generativeai")

class LLMService:
    def __init__(self):
        self.client = None
        self.model_name = Config.GEMINI_MODEL_NAME
        
        # Initialize Client (Old SDK Style)
        if Config.GEMINI_API_KEY:
             if genai:
                 try:
                     genai.configure(api_key=Config.GEMINI_API_KEY)
                     self.model = genai.GenerativeModel(self.model_name)
                     print(f"[LLM] Initialized Gemini Model: {self.model_name}")
                 except Exception as e:
                     print(f"[LLMINIT ERROR] {e}")
             else:
                 print("Warning: google-generativeai library is missing.")
        else:
            print("Warning: GEMINI_API_KEY not found in environment.")

    def _call_gemini(self, prompt):
        if not self.model:
            return "AI Service Not Configured."
        try:
            # Old SDK Call Structure
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
            return "No response from AI."
        except Exception as e:
            return f"AI Connection Error: {str(e)}"

    def analyze_stock_ai(self, symbol, price, pe_ratio, div_yield, news_summary, strategy="General", goal="Medium", technicals=None):
        """
        Uses Gemini (via google.generativeai) to analyze stock based on comprehensive financial data.
        """
        
        # Robust Missing Data Handling
        pe_str = str(pe_ratio)
        dy_str = str(div_yield)
        missing_note = ""
        if pe_str == "0" or pe_str == "N/A" or pe_str == "None" or not pe_ratio:
            pe_str = "N/A (Ignore P/E)"
            missing_note += " P/E is missing."
        if dy_str == "0" or dy_str == "N/A" or dy_str == "None" or not div_yield:
            dy_str = "N/A (Ignore Yield)"
            missing_note += " Yield is missing."

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
            f"Analyze stock {symbol} for Strategy: '{strategy}' (Goal: '{goal}').\n"
            f"Financial Data: Price={price}, P/E={pe_str}, DivYield={dy_str}%\n"
            f"{tech_context}"
            f"News Context: {news_summary}\n\n"
            "Task: Provide a Buy/Sell/Hold recommendation.\n"
            "CRITICAL RULES:\n"
            f"1. STRICTLY follow the User Strategy '{strategy}'.\n"
            f"2. If P/E or Yield is N/A/0, DO NOT mention them in reason. Focus on Price Trend/Technicals/News.{missing_note}\n"
            "3. Output format MUST be exactly: Category | Signal | Reason (Thai)\n"
            "4. Reason must be short, concise, in Thai (Max 1 sentence).\n"
            "Example: Value | WAIT | ข้อมูลพื้นฐานไม่ครบถ้วน รอสัญญาณทางเทคนิคชัดเจนกว่านี้"
        )
        
        return self._call_gemini(prompt)

    def summarize_news(self, news_list):
        if not news_list:
            return "ไม่มีข่าวสารสำคัญในช่วงนี้"
            
        # Limit to top 3 news for speed context window efficiency
        combined_news = "\n- ".join(news_list[:3])
        
        prompt = (
            f"Summarize these stock news headlines into a concise Thai paragraph.\n"
            f"Headlines:\n{combined_news}\n\n"
            f"Requirements:\n"
            f"1. Translate and summarize the key points into Thai language ONLY.\n"
            f"2. Keep it informative but concise.\n"
            f"Thai Summary:"
        )
        
        return self._call_gemini(prompt)
