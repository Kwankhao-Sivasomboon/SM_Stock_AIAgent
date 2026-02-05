from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, FlexSendMessage
)
import yfinance as yf
from config import Config
from database import SessionLocal, User, Watchlist
from line_templates import (
    get_add_stock_confirm_flex, get_watchlist_carousel,
    get_global_setting_flex, get_specific_setting_flex,
    get_scheduler_flex, get_analysis_flex
)
from analyzer import AnalysisEngine
from datetime import datetime, timedelta

app = Flask(__name__)

# Initialize Line API
line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
analyzer = AnalysisEngine()

# Simple In-Memory State
USER_STATES = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

def get_or_create_user(line_user_id):
    db = SessionLocal()
    user = db.query(User).filter(User.line_user_id == line_user_id).first()
    if not user:
        user = User(line_user_id=line_user_id)
        db.add(user)
        db.commit()
    return user, db

def check_stock_exists(symbol):
    """Helper to find stock, supports automatic .BK suffixing"""
    # 1. Try exact match (Priority for US Data)
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1d") 
        if not hist.empty:
            return symbol, hist['Close'].iloc[-1]
    except:
        pass

    # 2. Try adding .BK (Fallback for Thai Data)
    if not symbol.endswith(".BK") and "." not in symbol:
        try:
            bk_symbol = symbol + ".BK"
            t_bk = yf.Ticker(bk_symbol)
            hist = t_bk.history(period="1d")
            if not hist.empty:
                return bk_symbol, hist['Close'].iloc[-1]
        except:
            pass
            
    return None, None

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    
    if text == "เพิ่มรายชื่อหุ้น":
        USER_STATES[user_id] = "ADD_STOCK"
        line_bot_api.reply_message(
            event.reply_token, 
            TextSendMessage(text="พิมพ์ชื่อหุ้นที่ต้องการเพิ่ม (เช่น PTT NVDA) หรือพิมพ์หลายตัวด้วยการเว้นวรรค")
        )
        return

    menu_keywords = ["ตั้งเวลา", "แสดงผล", "รายการหุ้น", "ตั้งค่า", "ผลงาน", "Setting", "Watcher"]
    if any(k in text for k in menu_keywords):
        if user_id in USER_STATES:
            del USER_STATES[user_id]
        return

    # Check State
    current_state = USER_STATES.get(user_id)

    if current_state == "ADD_STOCK":
        potential_stocks = text.split()
        confirm_flexes = []
        duplicate_list = []
        
        # Open DB once for checking
        user, db = get_or_create_user(user_id)
        
        for raw_symbol in potential_stocks:
            symbol = raw_symbol.upper()
            if len(symbol) < 2 or len(symbol) > 10:
                continue
                
            found_symbol, price = check_stock_exists(symbol)
                
            if found_symbol and price:
                # Check DB for duplicate
                exists = db.query(Watchlist).filter_by(user_id=user.id, symbol=found_symbol).first()
                if exists:
                    duplicate_list.append(found_symbol)
                else:
                    flex_content = get_add_stock_confirm_flex(found_symbol, found_symbol, price)
                    if flex_content and 'contents' in flex_content:
                        confirm_flexes.append(flex_content['contents'])
        
        db.close()

        # Construct Reply
        msgs = []
        
        # 1. Duplicates
        if duplicate_list:
             dup_text = "! หุ้นเหล่านี้มีอยู่แล้ว: " + ", ".join(duplicate_list)
             msgs.append(TextSendMessage(text=dup_text))
        
        # 2. Carousel for new ones
        if confirm_flexes:
             if len(confirm_flexes) > 10:
                 confirm_flexes = confirm_flexes[:10]
             
             carousel = FlexSendMessage(
                 alt_text="ยืนยันการเพิ่มหุ้น",
                 contents={"type": "carousel", "contents": confirm_flexes}
             )
             msgs.append(carousel)
        
        # 3. Not found fallback
        if not confirm_flexes and not duplicate_list:
             line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"ไม่พบข้อมูลหุ้น: {text}"))
        else:
             try:
                 line_bot_api.reply_message(event.reply_token, msgs)
             except Exception as e:
                 print(f"Reply Error (Likely Timeout): {e}")

        del USER_STATES[user_id]
            
    else:
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="กรุณาเลือกเมนูจากด้านล่างครับ ↓"))
        except Exception:
            pass # Suppress silent fail for expired tokens


@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    user_id = event.source.user_id
    user, db = get_or_create_user(user_id)
    
    if user_id in USER_STATES:
        del USER_STATES[user_id]
    
    params = {}
    if data:
        for part in data.split('&'):
            if '=' in part:
                k, v = part.split('=', 1)
                params[k] = v
    
    action = params.get('action', '')
    symbol = params.get('symbol', '')

    try:
        # --- Add Stock ---
        if action == 'confirm_add' and symbol:
            exists = db.query(Watchlist).filter_by(user_id=user.id, symbol=symbol).first()
            if not exists:
                wl = Watchlist(user_id=user.id, symbol=symbol)
                db.add(wl)
                db.commit()
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✓ บันทึก {symbol} แล้ว"))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"! {symbol} มีอยู่แล้ว"))
                
        elif action == 'cancel_add':
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ยกเลิกรายการ"))

        # --- Delete Stock ---
        elif action == 'delete_stock' and symbol:
            item = db.query(Watchlist).filter_by(user_id=user.id, symbol=symbol).first()
            if item:
                db.delete(item)
                db.commit()
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"XXX ลบ {symbol} แล้ว"))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ไม่พบรายการที่จะลบ"))

        # --- Settings ---
        elif action == 'specific_setting' and symbol:
            flex = get_specific_setting_flex(symbol)
            if flex:
                line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text=f"Settings {symbol}", contents=flex['contents']))

        elif action in ['main_setting', 'global_setting']:
            flex = get_global_setting_flex()
            if flex:
                line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="Global Settings", contents=flex['contents']))

        # --- Save Settings ---
        elif 'global' in action and 'setting' not in action:
            parts = action.split('_')
            if len(parts) >= 3:
                setting_type = parts[0]
                val_key = parts[2]
                val_map = {
                    'dca': 'DCA', 'ai': 'AI-Auto', 'value': 'Value', 'growth': 'Growth', 
                    'dividend': 'Dividend', 'technical': 'Technical',
                    'short': 'Short', 'medium': 'Medium', 'long': 'Long',
                    'low': 'Low', 'high': 'High',
                    'summary': 'Summary', 'full': 'Full'
                }
                final_val = val_map.get(val_key, val_key.capitalize())
                
                if setting_type == 'strategy': user.core_strategy = final_val
                elif setting_type == 'goal': user.investment_goal = final_val
                elif setting_type == 'risk': user.risk_appetite = final_val
                elif setting_type == 'report': user.report_format = final_val
                
                db.commit()
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✓ Global {setting_type.capitalize()} = {final_val}"))

        elif 'stock' in action and symbol:
            parts = action.split('_')
            if len(parts) >= 3:
                setting_type = parts[0]
                val_key = parts[2]
                val_map = {
                     'dca': 'DCA', 'ai': 'AI-Auto', 'value': 'Value', 'growth': 'Growth', 
                    'dividend': 'Dividend', 'technical': 'Technical',
                    'short': 'Short', 'medium': 'Medium', 'long': 'Long',
                    'low': 'Low', 'high': 'High',
                    'summary': 'Summary', 'full': 'Full'
                }
                final_val = val_map.get(val_key, val_key.capitalize())
                
                wl_item = db.query(Watchlist).filter_by(user_id=user.id, symbol=symbol).first()
                if wl_item:
                    if setting_type == 'strategy': wl_item.strategy = final_val
                    elif setting_type == 'goal': wl_item.goal = final_val
                    elif setting_type == 'risk': wl_item.risk = final_val
                    elif setting_type == 'report': wl_item.report_format = final_val
                    db.commit()
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✓ {symbol} {setting_type.capitalize()} = {final_val}"))

        elif action == 'set_time':
            flex = get_scheduler_flex()
            if flex:
                line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="Schedule", contents=flex['contents']))
                
        elif action == 'time_set':
            time_val = event.postback.params.get('time')
            if time_val:
                try:
                    dt = datetime.strptime(time_val, "%H:%M")
                    # Snap to nearest HOUR (Logic: 30-59 -> next hour, 00-29 -> this hour)
                    if dt.minute >= 30:
                        dt = dt + timedelta(hours=1)
                    
                    final_dt = dt.replace(minute=0, second=0)
                    final_time = final_dt.strftime("%H:%M")
                    
                    from database import Schedule
                    sched = db.query(Schedule).filter_by(user_id=user.id).first()
                    if not sched:
                        sched = Schedule(user_id=user.id)
                        db.add(sched)
                    
                    sched.alert_time = final_time
                    sched.is_active = True
                    db.commit()
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"ตั้งเวลาแจ้งเตือนรายวัน (ทุกชั่วโมง): {final_time}"))
                except Exception as e:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"! รูปแบบเวลาไม่ถูกต้อง"))

        elif action == 'reset_time':
             from database import Schedule
             sched = db.query(Schedule).filter_by(user_id=user.id).first()
             if sched:
                 sched.is_active = False
                 db.commit()
             line_bot_api.reply_message(event.reply_token, TextSendMessage(text="X ปิดการแจ้งเตือนแล้ว"))

        elif action == 'view_watchlist':
            items = db.query(Watchlist).filter_by(user_id=user.id).all()
            if not items:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="Watchlist ของคุณว่างเปล่า"))
            else:
                flex = get_watchlist_carousel(items)
                if flex:
                    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="Watchlist", contents=flex['contents']))

        elif action == 'get_report':
            # --- Rate Limiting Strategy ---
            current_req_time = datetime.now()
            last_req_time = USER_STATES.get(f"{user_id}_last_report")
            
            # Cooldown Period (e.g., 30 seconds to prevent double threads)
            if last_req_time and (current_req_time - last_req_time).total_seconds() < 30:
                try:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ระบบกำลังประมวลผลคำขอเก่าอยู่ กรุณารอสักครู่..."))
                except: pass
                return # Stop processing
            
            # Update Timestamp
            USER_STATES[f"{user_id}_last_report"] = current_req_time

            items = db.query(Watchlist).filter_by(user_id=user.id).all()
            if not items:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ไม่มีหุ้นในรายการ"))
            else:
                # 1. Immediate Reply (Using Token)
                try:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="กำลังวิเคราะห์ข้อมูล กรุณารอสักครู่..."))
                except Exception:
                    pass 

                # 2. Fire-and-Forget Background Task
                import threading
                def run_analysis_task(user_id, items, user_settings):
                    # Re-create DB session inside thread if needed, or pass data explicitly
                    # Here we pass objects that don't need persistent DB session or re-query safely
                    
                    report_bubbles = []
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    
                    def process_item(item_data):
                        # Construct minimal item object or pass dict
                        symbol, strategy, goal, risk, report_fmt = item_data
                        try:
                            res = analyzer.analyze(symbol, strategy=strategy, goal=goal, risk=risk)
                            if res and 'signal' in res:
                                details = res.get('metrics', {}).copy()
                                details['history'] = res.get('history', [])
                                details['news'] = res.get('news', [])
                                details['technicals'] = res.get('technicals', {})
                                if 'news_summary' in res: details['news_summary'] = res['news_summary']
                                
                                f_msg = get_analysis_flex(symbol, res['signal'], res['reason'], details, report_fmt)
                                if f_msg and 'contents' in f_msg: return f_msg['contents']
                        except Exception as e:
                            print(f"Analyze error {symbol}: {e}")
                        return None

                    # Prepare Snapshot Data (avoid detached instance errors)
                    snapshot_items = []
                    for item in items:
                        strat = item.strategy or user_settings['core_strategy'] or "General"
                        goal = item.goal or user_settings['investment_goal'] or "Medium"
                        risk = item.risk or user_settings['risk_appetite'] or "Medium"
                        fmt = item.report_format or user_settings['report_format'] or "Summary"
                        snapshot_items.append((item.symbol, strat, goal, risk, fmt))

                    max_workers = min(len(snapshot_items), 4)
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = [executor.submit(process_item, data) for data in snapshot_items]
                        for future in as_completed(futures):
                            bubble = future.result()
                            if bubble: report_bubbles.append(bubble)
                    
                    # 3. Push Result via Push Message
                    if report_bubbles:
                        chunk_size = 10
                        for i in range(0, len(report_bubbles), chunk_size):
                            chunk = report_bubbles[i:i + chunk_size]
                            try:
                                line_bot_api.push_message(
                                    user_id, 
                                    FlexSendMessage(
                                        alt_text="Analysis Report", 
                                        contents={"type": "carousel", "contents": chunk}
                                    )
                                )
                            except Exception as e:
                                print(f"Push Error: {e}")
                    else:
                        try:
                            line_bot_api.push_message(user_id, TextSendMessage(text="! ไม่สามารถดึงข้อมูลได้ในขณะนี้"))
                        except: pass

                # Capture User Settings for Thread
                user_settings = {
                    'core_strategy': user.core_strategy,
                    'investment_goal': user.investment_goal,
                    'risk_appetite': user.risk_appetite,
                    'report_format': user.report_format
                }
                
                # Start Thread
                thread = threading.Thread(target=run_analysis_task, args=(user_id, items, user_settings))
                thread.start()
                # Function ends here, returning 200 OK immediately to LINE

        elif action == 'our_products':
             line_bot_api.reply_message(event.reply_token, TextSendMessage(text="รอติดตามผลงานเร็วๆนี้"))

    except Exception as e:
        print(f"Postback Error: {e}")
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="! เกิดข้อผิดพลาด"))
        except Exception:
            pass # Token likely expired, ignore.
    finally:
        db.close()

if __name__ == "__main__":
    app.run(port=5000)
