import json
import os
import urllib.parse
from config import Config

# Helper to load JSON safely
TEMPLATE_DIR = os.path.join(Config.BASE_DIR, 'line_ux')

def load_template(filename):
    path = os.path.join(TEMPLATE_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def _replace_recursive(obj, replacements):
    if isinstance(obj, dict):
        return {k: _replace_recursive(v, replacements) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_replace_recursive(i, replacements) for i in obj]
    elif isinstance(obj, str):
        for key, val in replacements.items():
            obj = obj.replace(key, str(val))
        return obj
    return obj

def get_add_stock_confirm_flex(symbol, company_name, price):
    # Safe Price Format
    price_fmt = "N/A"
    try:
        if price:
            val = float(price)
            price_fmt = f"{val:,.2f}"
    except:
        price_fmt = str(price)

    try:
        template = load_template("add.json")
        if template:
            replacements = {
                "Stock_Name": str(symbol),
                "company_name": str(company_name or symbol),
                "current_price": price_fmt
            }
            bubble = _replace_recursive(template, replacements)
            return {"type": "flex", "altText": f"Confirm {symbol}", "contents": bubble}
    except Exception as e:
        print(f"[TEMPLATE ERROR] {e}")

    # Fallback Hardcoded Bubble (Safety Net)
    return {
      "type": "flex",
      "altText": f"Confirm {symbol}",
      "contents": {
        "type": "bubble",
        "body": {
          "type": "box",
          "layout": "vertical",
          "contents": [
            {"type": "text", "text": "CONFIRM ADD", "weight": "bold", "color": "#1DB446", "size": "xs"},
            {"type": "text", "text": str(symbol), "weight": "bold", "size": "xl", "margin": "md"},
            {"type": "text", "text": f"Price: {price_fmt}", "size": "md", "color": "#555555", "margin": "sm"},
            {"type": "separator", "margin": "lg"},
            {"type": "box", "layout": "horizontal", "margin": "md", "spacing": "md", "contents": [
                {
                    "type": "button", "style": "primary", "height": "sm", "color": "#1DB446",
                    "action": {"type": "postback", "label": "YES", "data": f"action=confirm_add&symbol={symbol}"}
                },
                {
                    "type": "button", "style": "secondary", "height": "sm", "color": "#aaaaaa",
                    "action": {"type": "postback", "label": "NO", "data": "action=cancel"}
                }
            ]}
          ]
        }
      }
    }

def get_watchlist_carousel(stocks):
    try:
        base_bubble = load_template("watch_list.json")
        if base_bubble:
            bubbles = []
            for stock in stocks:
                symbol = stock.symbol
                company = getattr(stock, 'company_name', symbol) or symbol
                replacements = {"Stock_Name": str(symbol), "stock_name": str(symbol), "company_name": str(company)}
                bubbles.append(_replace_recursive(base_bubble, replacements))
            if bubbles:
                 return {"type": "flex", "altText": "Watchlist", "contents": {"type": "carousel", "contents": bubbles}}
    except Exception as e:
        print(f"[TEMPLATE ERROR Watchlist] {e}")

    # Fallback Carousel (Premium Design)
    bubbles = []
    for stock in stocks:
        sym = str(stock.symbol)
        
        # Determine color based on index (Just for variety or fixed)
        header_color = "#0D47A1" # Deep Blue
        
        bubbles.append({
            "type": "bubble",
            "size": "micro",
            "header": {
                "type": "box", "layout": "vertical", "backgroundColor": header_color, "paddingAll": "10px",
                "contents": [
                    {"type": "text", "text": sym, "color": "#ffffff", "weight": "bold", "size": "xl"},
                    {"type": "text", "text": "WATCHLIST", "color": "#eeeeee", "size": "xxs"}
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "10px",
                "contents": [
                    {
                        "type": "box", "layout": "vertical", "spacing": "sm",
                        "contents": [
                            {"type": "button", "style": "primary", "height": "sm", "color": "#1DB446",
                             "action": {"type": "message", "label": "📈 Analyze", "text": f"Analyze {sym}"}},
                            {"type": "button", "style": "secondary", "height": "sm", "color": "#aaaaaa",
                             "action": {"type": "postback", "label": "⚙️ Settings", "data": f"action=settings&symbol={sym}"}},
                            {"type": "separator", "margin": "sm"},
                            {"type": "button", "style": "link", "height": "sm", "color": "#ff4444",
                             "action": {"type": "postback", "label": "❌ Remove", "data": f"action=delete&symbol={sym}"}}
                        ]
                    }
                ]
            }
        })
    return {"type": "flex", "altText": "Watchlist", "contents": {"type": "carousel", "contents": bubbles}}

def get_global_setting_flex():
    try:
        template = load_template("carousel_setting_global.json")
        if template: return {"type": "flex", "altText": "Global Settings", "contents": template}
    except: pass
    
    # Fallback
    return {"type": "text", "text": "Global Settings Template Error. Please use menu."}

def get_specific_setting_flex(symbol):
    try:
        template = load_template("carousel_setting_stock.json")
        if template:
            replacements = {"stock_name": str(symbol), "Stock_Name": str(symbol)}
            return {"type": "flex", "altText": f"Settings {symbol}", "contents": _replace_recursive(template, replacements)}
    except Exception as e:
        print(f"[TEMPLATE ERROR Settings] {e}")

    # Fallback
    return {
        "type": "flex", "altText": f"Settings {symbol}",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box", "layout": "vertical",
                "contents": [
                    {"type": "text", "text": f"SETTINGS: {symbol}", "weight": "bold", "size": "lg"},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "Adjust your preferences below", "size": "xs", "color": "#aaaaaa", "margin": "sm"},
                    {"type": "button", "style": "secondary", "height": "sm", "margin": "md",
                     "action": {"type": "postback", "label": "Toggle RSI Check", "data": f"action=toggle_rsi&symbol={symbol}"}},
                     {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                     "action": {"type": "postback", "label": "Custom Alert", "data": f"action=set_alert&symbol={symbol}"}}
                ]
            }
        }
    }

def get_scheduler_flex():
    template = load_template("scheduler.json")
    if not template: return None
    return {"type": "flex", "altText": "Schedule", "contents": template}

def get_analysis_flex(symbol, signal, recommendation, details, report_format="Summary"):
    # Color Logic
    color_map = {"BUY": "#00C851", "SELL": "#ff4444", "HOLD": "#ffbb33", "WAIT": "#33b5e5", "ERROR": "#000000"}
    header_color = color_map.get(signal, "#aaaaaa")
    
    # Extract News logic
    # Priority: news_summary (Thai AI) > news (Raw list)
    news_text = ""
    if isinstance(details, dict):
        if details.get('news_summary'):
            news_text = details['news_summary']
        elif details.get('news'):
            raw_news = details.get('news', [])
            if raw_news and isinstance(raw_news, list):
                 valid_news = [n for n in raw_news if n and "ไม่มีข่าว" not in n]
                 if valid_news:
                     news_text = ", ".join(valid_news[:3]) # Show top 3

    if not news_text:
        news_text = "ไม่มีข่าวสำคัญในช่วงนี้"

    # 1. Header
    header = {
        "type": "box", "layout": "vertical",
        "contents": [
             {"type": "text", "text": "ANALYSIS REPORT", "weight": "bold", "color": "#1DB446", "size": "xxs"},
             {"type": "text", "text": f"{symbol}", "weight": "bold", "size": "xl", "margin": "md"},
             {"type": "text", "text": f"{signal}", "weight": "bold", "size": "xxl", "color": header_color, "margin": "md"}
        ]
    }
    
    # 2. Body
    body_contents = []
    
    # Main Recommendation (Reason)
    body_contents.append({
        "type": "text", "text": recommendation, "wrap": True, 
        "color": "#333333", "size": "sm", "weight": "bold"
    })

    # Sparkline Graph (Trend) - ONLY SHOW IN FULL MODE
    if report_format == "Full":
        history_prices = details.get('history', []) if isinstance(details, dict) else []
        if history_prices:
            # Downsample for graph if too many points (keep last 30 for clear trend)
            graph_data = history_prices[-30:] if len(history_prices) > 30 else history_prices
            prices_str = ",".join([str(round(p, 2)) for p in graph_data])
            
            # QuickChart Sparkline
            chart_config = f"{{type:'sparkline',data:{{datasets:[{{data:[{prices_str}],borderColor:'#8854d0',fill:false}}]}}}}"
            encoded_chart = urllib.parse.quote(chart_config)
            chart_url = f"https://quickchart.io/chart?c={encoded_chart}&w=300&h=100"
            
            body_contents.append({"type": "separator", "margin": "lg"})
            body_contents.append({
                 "type": "box", "layout": "vertical", "margin": "md",
                 "contents": [
                      {"type": "text", "text": "📈 30-Day Trend", "size": "xxs", "color": "#aaaaaa", "align": "center", "margin": "xs"},
                      {"type": "image", "url": chart_url, "size": "full", "aspectRatio": "3:1", "aspectMode": "cover"}
                 ]
            })

    # Statistics & Technicals Section - ONLY SHOW IN FULL MODE
    if report_format == "Full":
        body_contents.append({"type": "separator", "margin": "lg"})
        body_contents.append({"type": "text", "text": "📊 Key Statistics", "weight": "bold", "size": "sm", "margin": "md"})
        
        # Merge basic metrics and technicals
        display_metrics = {}
        
        # 1. Basic Metrics
        for k, v in details.items():
            if k in ['Price', 'P/E', 'Yield']:
                display_metrics[k] = v
        
        # 2. Technicals (if available)
        technicals = details.get('technicals', {})
        if technicals:
            if 'rsi' in technicals: display_metrics['RSI (14)'] = technicals['rsi']
            if 'sma50' in technicals: display_metrics['SMA (50)'] = technicals['sma50']
            if 'market_cap' in technicals: display_metrics['Mkt Cap'] = technicals['market_cap']
            if 'year_high' in technicals: display_metrics['52W High'] = technicals['year_high']
            if 'year_low' in technicals: display_metrics['52W Low'] = technicals['year_low']

        # Render Logic
        for k, v in display_metrics.items():
            if str(v) == "N/A" or not v: continue # Skip empty
            body_contents.append({
                "type": "box", "layout": "baseline", "margin": "sm",
                "contents": [
                    {"type": "text", "text": k, "flex": 3, "size": "xs", "color": "#aaaaaa"},
                    {"type": "text", "text": str(v), "flex": 4, "size": "xs", "color": "#666666", "align": "end"}
                ]
            })

    body = {"type": "box", "layout": "vertical", "contents": body_contents}
    
    # 3. Footer
    clean_symbol = symbol.replace(".BK", "")
    base_url = "https://www.set.or.th/th/market/product/stock/quote/" if ".BK" in symbol else "https://finance.yahoo.com/quote/"
    final_uri = f"{base_url}{clean_symbol}"
    if ".BK" in symbol: final_uri += "/price"

    footer = {
        "type": "box", "layout": "vertical",
        "contents": [
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "uri", "label": "See Realtime Data", "uri": final_uri}}
        ]
    }
    
    return {"type": "flex", "altText": f"Analysis {symbol}", "contents": {"type": "bubble", "header": header, "body": body, "footer": footer}}