import os
from dotenv import load_dotenv

# Get the base directory of the project
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Load environment variables from the project root
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Config:
    BASE_DIR = BASE_DIR
    # Database (Ensure app.db is in the project root)
    DB_PATH = os.path.join(BASE_DIR, 'app.db')
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = database_url or f'sqlite:///{DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Line API
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_CHANNEL_SECRET')

    # LLM Settings
    # LLM Settings (Primary: Google Gemini)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL_NAME = os.getenv('GEMINI_MODEL_NAME', 'gemini-3-flash')

    # App Settings
    SCHEDULER_TIMEZONE = 'Asia/Bangkok'
    DEBUG = False
