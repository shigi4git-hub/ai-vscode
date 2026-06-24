"""
トークン使用状況のログ記録モジュール

このモジュールはAPI呼び出しのトークン使用状況をCSVファイルに記録します。
"""

import csv
from datetime import datetime
from uuid import uuid4
from pathlib import Path


# ログディレクトリのパス
LOGS_DIR = Path("logs")


def generate_request_id() -> str:
    """
    UUID4を使用してリクエストIDを生成する
    
    Returns:
        str: 生成されたリクエストID（UUID4形式）
    
    Example:
        >>> request_id = generate_request_id()
        >>> len(request_id) > 0
        True
    """
    return str(uuid4())


def log_token_usage(
    request_id: str,
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int
) -> None:
    """
    トークン使用状況をCSVファイルに記録する
    
    logsディレクトリが存在しない場合は自動作成します。
    token_usage.csvファイルが存在しない場合はヘッダー付きで新規作成します。
    
    Args:
        request_id (str): リクエストの一意識別子
        operation (str): 実行された操作の名前（例：'qa'、'summarize'など）
        model (str): 使用されたモデルの名前（例：'gpt-4'など）
        input_tokens (int): 入力トークン数
        output_tokens (int): 出力トークン数
    
    Example:
        >>> log_token_usage(
        ...     request_id="123e4567-e89b-12d3-a456-426614174000",
        ...     operation="qa",
        ...     model="gpt-4",
        ...     input_tokens=100,
        ...     output_tokens=50
        ... )
    """
    # logsディレクトリが存在しない場合は作成
    LOGS_DIR.mkdir(exist_ok=True)
    
    # CSVファイルのパス
    csv_path = LOGS_DIR / "token_usage.csv"
    
    # 現在時刻をISO形式のタイムスタンプとして取得
    timestamp = datetime.now().isoformat()
    
    # 合計トークン数を計算
    total_tokens = input_tokens + output_tokens
    
    # ファイルが存在するかチェック（ヘッダー書き込みの判定用）
    file_exists = csv_path.exists()
    
    # CSVファイルを追記モードで開く
    with open(csv_path, mode='a', newline='', encoding='utf-8') as csvfile:
        # フィールド定義
        fieldnames = [
            'timestamp',
            'request_id',
            'operation',
            'model',
            'input_tokens',
            'output_tokens',
            'total_tokens'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # ファイルが新しい場合はヘッダーを書き込む
        if not file_exists:
            writer.writeheader()
        
        # データ行を書き込む
        writer.writerow({
            'timestamp': timestamp,
            'request_id': request_id,
            'operation': operation,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': total_tokens
        })


def log_feedback_loop(
    request_id: str,
    question: str,
    prompt_type: str,
    prompt_content: str,
    answer: str,
    rating: str,
    loop_count: int,
    input_tokens: int,
    output_tokens: int
) -> None:
    """
    フィードバックループの質問・回答・評価ログをCSVファイルに記録する
    
    logsディレクトリが存在しない場合は自動作成します。
    feedback_loop_log.csvファイルが存在しない場合はヘッダー付きで新規作成します。
    
    Args:
        request_id (str): リクエストの一意識別子
        question (str): ユーザーから送信された質問テキスト
        prompt_type (str): 使用したプロンプトタイプ（"normal" または "retry"）
        prompt_content (str): 実際に使用したプロンプトの内容（テンプレート部分）
        answer (str): AIが生成した回答テキスト
        rating (str): ユーザーによる評価（"good" または "bad"）
        loop_count (int): フィードバックループの回数（0=初回, 1=1回目の再質問, ...）
        input_tokens (int): 入力トークン数
        output_tokens (int): 出力トークン数
    
    Example:
        >>> log_feedback_loop(
        ...     request_id="123e4567-e89b-12d3-a456-426614174000",
        ...     question="FastAPIの特徴は？",
        ...     prompt_type="normal",
        ...     prompt_content="あなたはPDFドキュメント...",
        ...     answer="FastAPIは型検証と自動ドキュメント...",
        ...     rating="good",
        ...     loop_count=0,
        ...     input_tokens=150,
        ...     output_tokens=80
        ... )
    """
    # logsディレクトリが存在しない場合は作成
    LOGS_DIR.mkdir(exist_ok=True)
    
    # CSVファイルのパス
    csv_path = LOGS_DIR / "feedback_loop_log.csv"
    
    # 現在時刻をISO形式のタイムスタンプとして取得
    timestamp = datetime.now().isoformat()
    
    # 合計トークン数を計算
    total_tokens = input_tokens + output_tokens
    
    # ファイルが存在するかチェック（ヘッダー書き込みの判定用）
    file_exists = csv_path.exists()
    
    # CSVファイルを追記モードで開く
    with open(csv_path, mode='a', newline='', encoding='utf-8-sig') as csvfile:
        # フィールド定義
        fieldnames = [
            'timestamp',
            'request_id',
            'question',
            'prompt_type',
            'prompt_content',
            'answer',
            'rating',
            'loop_count',
            'input_tokens',
            'output_tokens',
            'total_tokens'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # ファイルが新しい場合はヘッダーを書き込む
        if not file_exists:
            writer.writeheader()
        
        # データ行を書き込む
        writer.writerow({
            'timestamp': timestamp,
            'request_id': request_id,
            'question': question,
            'prompt_type': prompt_type,
            'prompt_content': prompt_content,
            'answer': answer,
            'rating': rating,
            'loop_count': loop_count,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': total_tokens
        })
