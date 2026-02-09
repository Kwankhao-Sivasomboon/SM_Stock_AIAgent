import time
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from linebot import LineBotApi
from linebot.models import FlexSendMessage

from config import Config
from database import SessionLocal, Schedule, User, Watchlist
from init_cache_db import GlobalStockInfo
from analyzer import AnalysisEngine
from line_templates import get_analysis_flex

# Initialize Services
line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
analyzer = AnalysisEngine()

def prune_cache():
    """
    Daily Cache Maintenance: Remove entries older than 24 hours.
    Runs at 03:00 AM (Before Thai/US Market active hours)
    """
    print("[Worker] Pruning Global Stock Cache...")
    db = SessionLocal()
    try:
        # Define threshold (e.g., 24 hours ago)
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        deleted = db.query(GlobalStockInfo).filter(GlobalStockInfo.updated_at < cutoff).delete()
        db.commit()
        print(f"[Worker] Cache Pruned: Removed {deleted} old entries.")
    except Exception as e:
        print(f"[Worker] Pruning Error: {e}")
    finally:
        db.close()

def process_schedule(schedule):
    """
    Process a single schedule: Fetch data, Analyze, Send Message (Carousel)
    """
    print(f"Running schedule for User {schedule.user_id}")
    db = SessionLocal()
    try:
        # 1. IMMEDIATE LOCK: Update last_run first to prevent double-firing from Scheduler Retries
        # Re-fetch schedule from this session to ensure attachment
        current_sched = db.query(Schedule).filter(Schedule.id == schedule.id).first()
        if not current_sched: return

        current_sched.last_run = datetime.datetime.now()
        db.commit()

        user = db.query(User).filter(User.id == schedule.user_id).first()
        if not user: return

        watchlist = db.query(Watchlist).filter(Watchlist.user_id == user.id).all()
        if not watchlist:
            print(f"User {user.id} has no watchlist.")
            return

        # Deduplicate Watchlist (Keep unique symbols only)
        seen_symbols = set()
        unique_watchlist = []
        for item in watchlist:
            if item.symbol not in seen_symbols:
                unique_watchlist.append(item)
                seen_symbols.add(item.symbol)

        # Container for Carousel Bubbles
        flex_bubbles = []

        # Sequential processing
        total_items = len(unique_watchlist)
        for index, item in enumerate(unique_watchlist):
            # Use specific setting if set, else fallback to global user setting
            strat = item.strategy or user.core_strategy
            goal = item.goal or user.investment_goal
            risk = item.risk or user.risk_appetite
            
            print(f"[{index+1}/{total_items}] Analyzing {item.symbol}...")
            
            try:
                # Pass ALL user contexts to Analyzer -> LLM
                analysis_result = analyzer.analyze(
                    item.symbol, 
                    strategy=strat,
                    goal=goal,
                    risk=risk
                )
                
                if analysis_result:
                    # Debug News
                    print(f"   > News Count for {item.symbol}: {len(analysis_result.get('news', []))}")

                    # Create Flex Message Bubble
                    flex = get_analysis_flex(
                        symbol=analysis_result['symbol'],
                        signal=analysis_result['signal'],
                        recommendation=analysis_result['reason'],
                        details=analysis_result['metrics']
                    )
                    
                    # Extract only the 'contents' (Bubble) part for Carousel
                    if flex and 'contents' in flex:
                        flex_bubbles.append(flex['contents'])
            except Exception as e_an:
                print(f"Analysis Error {item.symbol}: {e_an}")

            # Rate Limit Delay (skip after last item)
            if index < total_items - 1:
                print("Waiting 15s for API Rate Limit protection...")
                time.sleep(15) 
        
        # Send All as Carousel
        if flex_bubbles:
            try:
                # LINE limit is 12 bubbles per carousel (our max watchlist is 10, so safe)
                carousel_payload = {
                    "type": "carousel",
                    "contents": flex_bubbles
                }
                
                line_bot_api.push_message(
                    user.line_user_id, 
                    FlexSendMessage(alt_text=f"Daily Report ({total_items} Stocks)", contents=carousel_payload)
                )
                print(f"Sent Carousel Report to {user.line_user_id}")
            except Exception as e:
                print(f"Failed to send line message: {e}")
        else:
            print("No analysis generated.")

    except Exception as e:
        print(f"Error in process_schedule: {e}")
    finally:
        db.close()

def check_jobs():
    """
    Runs hourly (at minute 0) to check if any schedule needs to trigger.
    """
    import pytz
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.datetime.now(tz)
    # Snap to nearest hour for comparison (e.g. 09:01 -> 09:00)
    current_time_str = now.strftime("%H:00")
    
    print(f"Worker checking jobs for: {current_time_str}")
    
    db = SessionLocal()
    try:
        # Check active schedules matching current hour
        schedules = db.query(Schedule).filter(
            Schedule.is_active == True,
            Schedule.alert_time == current_time_str
        ).all()
        
        for sched in schedules:
            # Debounce: Check if already ran today
            if sched.last_run and sched.last_run.date() == now.date() and sched.last_run.hour == now.hour:
                 print(f"Skipping {sched.id}, already ran this hour.")
                 continue
                
            process_schedule(sched)
            
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting AI Agent Worker (Hourly Mode + Daily Maintenance)...")
    scheduler = BlockingScheduler(timezone=Config.SCHEDULER_TIMEZONE)
    
    # Hourly Job (Check User Schedules)
    scheduler.add_job(check_jobs, 'cron', minute=0)
    
    # Daily Job (Reset Cache at 03:00 AM)
    scheduler.add_job(prune_cache, 'cron', hour=4, minute=0)
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
