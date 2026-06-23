from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from database import Base, engine


class Feedback(Base):
    """フィードバック（評価）テーブルの ORM モデル"""
    __tablename__ = "feedbacks"

    # 主キー
    id = Column(Integer, primary_key=True, index=True)
    # 対象の投稿 ID
    item_id = Column(Integer, nullable=False, index=True)
    # 評価："good" または "bad" のみ
    rating = Column(String, nullable=False)
    # 作成日時
    created_at = Column(DateTime, default=datetime.utcnow)


# テーブルを自動生成
Base.metadata.create_all(bind=engine)
