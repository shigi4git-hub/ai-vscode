from sqlalchemy import Column, Integer, String, Text
from database import Base, engine


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)


# テーブルを自動生成
Base.metadata.create_all(bind=engine)
