from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

SECRET_KEY = "secret-key-change-this"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# bcrypt ベースのパスワードハッシュ化を行うためのコンテキスト。
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """平文パスワードとハッシュ済みパスワードを照合する。"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """パスワードを bcrypt でハッシュ化して返す。"""
    return pwd_context.hash(password)


def authenticate_user(db, username: str, password: str):
    """ユーザー名とパスワードから認証対象ユーザーを取得する。"""
    from models.user import User

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """JWT アクセストークンを生成する。"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
