from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Supabase 접속 정보를 환경변수로 관리하는 것이 좋습니다.
SQLALCHEMY_DATABASE_URL = "postgresql://postgres.swjmwbzpfdwqfvqfplre:pGvknjc5T1ofEzJ6@aws-1-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# DB 세션 의존성 주입 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()