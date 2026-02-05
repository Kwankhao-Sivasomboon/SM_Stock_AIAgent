import time
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from linebot import LineBotApi
from linebot.models import FlexSendMessage

from config import Config
from database import SessionLocal, Schedule, User, Watchlist
from analyzer import AnalysisEngine
from line_templates import get_analysis_flex

# Initialize Services
line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
analyzer = AnalysisEngine()

def process_schedule(schedule):
    """
    Process a single schedule: Fetch data, Analyze, Send Message
    """
    print(f"Running schedule for User {schedule.user_id}")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == schedule.user_id).first()
        if not user:
            return

        watchlist = db.query(Watchlist).filter(Watchlist.user_id == user.id).all()
        if not watchlist:
            print(f"User {user.id} has no watchlist.")
            return

        # Simple batch processing
        for item in watchlist:
            # Use specific setting if set, else fallback to global user setting
            strat = item.strategy or user.core_strategy
            goal = item.goal or user.investment_goal
            risk = item.risk or user.risk_appetite
            
            print(f"Analyzing {item.symbol} (Strat:{strat}, Goal:{goal})...")
            
            # Pass ALL user contexts to Analyzer -> LLM
            analysis_result = analyzer.analyze(
                item.symbol, 
                strategy=strat,
                goal=goal,
                risk=risk
            )
            
            if analysis_result:
                # Format: Specific > Global
                fmt = item.report_format or user.report_format or "Summary"
                
                # Create Flex Message with new Technical Data inside details
                flex = get_analysis_flex(
                    symbol=analysis_result['symbol'],
                    signal=analysis_result['signal'],
                    recommendation=analysis_result['reason'],
                    details=analysis_result['metrics'], # Contains Technicals like RSI
                    report_format=fmt
                )
                
                # Push Message to Line
                try:
                    line_bot_api.push_message(user.line_user_id, FlexSendMessage(alt_text=f"Update: {item.symbol}", contents=flex['contents']))
                    print(f"Sent report for {item.symbol} to {user.line_user_id}")
                except Exception as e:
                    print(f"Failed to send line message: {e}")
                    
        # Update last run time
        schedule.last_run = datetime.datetime.now()
        db.commit()

    except Exception as e:
        print(f"Error in process_schedule: {e}")
    finally:
        db.close()

def check_jobs():
    """
    Runs hourly (at minute 0) to check if any schedule needs to trigger.
    """
    now = datetime.datetime.now()
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
    print("Starting AI Agent Worker (Hourly Mode)...")
    scheduler = BlockingScheduler(timezone=Config.SCHEDULER_TIMEZONE)
    
    # minute 0 of every hour (09:00, 10:00, ...)
    scheduler.add_job(check_jobs, 'cron', minute=0)
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
