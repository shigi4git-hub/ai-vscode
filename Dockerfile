# ベースイメージ: Python 3.10 の軽量版を使用
FROM python:3.10-slim

# 作業ディレクトリを設定
WORKDIR /ai-vscode

# 依存関係のみを先にコピーして、レイヤーを分離
# これにより requirements.txt が変わらない限り、依存関係のインストールをキャッシュできる
COPY requirements.txt ./

# Python の依存関係をインストール
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# アプリケーション本体をコピー
# 依存関係のレイヤーとアプリコードのレイヤーを分離して管理しやすくする
COPY . .

# FastAPI / Uvicorn が 8000 番ポートを使うことを明示
EXPOSE 8000

# アプリ起動コマンド
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
