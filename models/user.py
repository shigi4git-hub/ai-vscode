from sqlalchemy import Column, Integer, String
from database import Base, engine


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)


# テーブルを自動生成
Base.metadata.create_all(bind=engine)
