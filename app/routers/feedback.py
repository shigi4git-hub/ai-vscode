from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List
from pydantic import BaseModel, field_validator

from database import Session as SessionLocal
from models.feedback import Feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


# ==================== Pydantic モデル ====================

class FeedbackCreate(BaseModel):
    """フィードバック作成時のリクエストボディ"""
    item_id: int
    rating: str

    @field_validator("rating")
    def validate_rating(cls, v):
        """rating は "good" または "bad" のみを受け付ける"""
        if v not in ["good", "bad"]:
            raise ValueError('rating must be "good" or "bad"')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "item_id": 1,
                "rating": "good"
            }
        }


class FeedbackSummary(BaseModel):
    """フィードバック統計情報"""
    good_count: int
    bad_count: int
    rating_rate: float  # good / (good + bad) * 100


class LowRatedItem(BaseModel):
    """低評価が多い投稿の情報"""
    item_id: int
    bad_count: int


# ==================== ヘルパー関数 ====================

def get_db():
    """DB セッションの依存性注入"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== エンドポイント ====================

@router.post("/")
def create_feedback(feedback: FeedbackCreate, db: Session = Depends(get_db)):
    """
    POST /feedback: フィードバックを作成して DB に保存
    
    - item_id: 対象の投稿 ID
    - rating: "good" または "bad"
    """
    new_feedback = Feedback(
        item_id=feedback.item_id,
        rating=feedback.rating,
        created_at=datetime.utcnow()
    )
    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)
    return {
        "id": new_feedback.id,
        "message": f"Feedback saved: {feedback.rating}"
    }


@router.get("/summary", response_model=FeedbackSummary)
def get_feedback_summary(db: Session = Depends(get_db)):
    """
    GET /feedback/summary: フィードバックの統計情報を取得
    
    返却値：
    - good_count: 良い評価の件数
    - bad_count: 悪い評価の件数
    - rating_rate: 良い評価の率（％）
    """
    good_count = db.query(func.count(Feedback.id)).filter(
        Feedback.rating == "good"
    ).scalar() or 0
    
    bad_count = db.query(func.count(Feedback.id)).filter(
        Feedback.rating == "bad"
    ).scalar() or 0

    total = good_count + bad_count
    # ゼロ除算を避ける
    rating_rate = (good_count / total * 100) if total > 0 else 0.0

    return FeedbackSummary(
        good_count=good_count,
        bad_count=bad_count,
        rating_rate=rating_rate
    )


@router.get("/low-rated", response_model=List[LowRatedItem])
def get_low_rated_items(db: Session = Depends(get_db)):
    """
    GET /feedback/low-rated: 悪い評価が多い投稿を一覧で取得
    
    返却値：
    - item_id: 投稿 ID
    - bad_count: 悪い評価の件数
    
    結果は悪い評価が多い順にソートされます。
    """
    results = db.query(
        Feedback.item_id,
        func.count(Feedback.id).label("bad_count")
    ).filter(
        Feedback.rating == "bad"
    ).group_by(
        Feedback.item_id
    ).order_by(
        func.count(Feedback.id).desc()
    ).all()

    return [LowRatedItem(item_id=r[0], bad_count=r[1]) for r in results]
