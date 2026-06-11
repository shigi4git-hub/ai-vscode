from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from database import Session
from models.user import User
from app.services.auth import authenticate_user, create_access_token, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


class UserCreate(BaseModel):
    """ユーザー登録リクエスト用の入力モデル。"""
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/register")
def register_user(user: UserCreate):
    """新規ユーザーを登録する。"""
    db = Session()
    try:
        existing_user = db.query(User).filter(User.username == user.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already registered")

        hashed_password = hash_password(user.password)
        db_user = User(username=user.username, hashed_password=hashed_password)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    finally:
        db.close()

    return JSONResponse(
        status_code=201,
        content={
            "message": "User registered",
            "user": {
                "id": db_user.id,
                "username": db_user.username,
            },
        },
    )


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """メールアドレス風の username と password でログインし JWT を返す。"""
    db = Session()
    try:
        db_user = authenticate_user(db, form_data.username, form_data.password)
        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        access_token = create_access_token(data={"sub": db_user.username})
    finally:
        db.close()

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
