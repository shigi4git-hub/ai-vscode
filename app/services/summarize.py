"""
要約サービスモジュール。
OpenAI Chat Completions API を使用してテキストの要約を生成する。
APIキーは python-dotenv 経由で .env ファイルから読み込む。
"""

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

# .env ファイルをプロジェクトルートから読み込む（既にロード済みでも安全に再呼び出し可）
load_dotenv()

# モジュールレベルのロガーを設定
logger = logging.getLogger(__name__)

# OpenAI クライアントをモジュールロード時に一度だけ初期化する。
# OPENAI_API_KEY 環境変数が存在しない場合は None のまま保持し、
# 呼び出し時にエラーハンドリングで吸収する。
_api_key = os.getenv("OPENAI_API_KEY")
_client: OpenAI | None = OpenAI(api_key=_api_key) if _api_key else None


def summarize_text(text: str, max_chars: int = 150) -> str | None:
    """
    テキストを OpenAI API で要約して返す。

    Parameters
    ----------
    text : str
        要約対象の本文テキスト。
    max_chars : int
        要約の目標文字数（プロンプトで指示するだけであり厳密な制限ではない）。

    Returns
    -------
    str | None
        要約文字列。API キー未設定・API エラー等の場合は None を返す。
    """
    # クライアントが初期化されていない場合はスキップ
    if _client is None:
        logger.warning("OPENAI_API_KEY が設定されていないため要約をスキップします。")
        return None

    try:
        response = _client.chat.completions.create(
            model="gpt-4o-mini",  # 軽量・低コストモデルを使用
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは日本語テキストを簡潔に要約するアシスタントです。"
                        f"与えられた文章を {max_chars} 文字以内で要約してください。"
                    ),
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
            # トークン数を抑えてコストを削減する（約150文字 ≒ 200トークン程度）
            max_tokens=300,
            temperature=0.3,  # 要約には低めの温度で安定した出力を得る
        )
        # 生成されたテキストを取り出して前後の空白を除去する
        summary = response.choices[0].message.content
        return summary.strip() if summary else None

    except Exception as exc:
        # API 障害・ネットワークエラー等、あらゆる例外をキャッチしてログに残す
        logger.error("要約の生成に失敗しました: %s", exc)
        return None
