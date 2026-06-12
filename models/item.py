from sqlalchemy import Column, Integer, String, Text
from database import Base, engine


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    # OpenAI API で生成した本文の要約。要約失敗時は NULL のまま保持する。
    summary = Column(Text, nullable=True)


# テーブルを自動生成
Base.metadata.create_all(bind=engine)
