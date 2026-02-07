from sqlalchemy import create_engine, Column, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
try:
    from config import Config
except ImportError:
    from src.config import Config
import datetime

Base = declarative_base()

class GlobalStockInfo(Base):
    __tablename__ = 'global_stock_info'
    
    symbol = Column(String, primary_key=True)
    company_name = Column(String)
    market_cap = Column(String) # Store as string '2.5T' or raw number
    pe_ratio = Column(Float)
    dividend_yield = Column(Float)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

def init_db():
    engine = create_engine(Config.DATABASE_URL)
    Base.metadata.create_all(engine)
    print("✅ Table 'global_stock_info' created/verified.")

if __name__ == "__main__":
    init_db()
