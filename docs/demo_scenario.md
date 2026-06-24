# デモシナリオ手順書

> **対象読者**: 本システムを初めて触る開発者・レビュアー  
> **前提**: サーバーが `http://localhost:8000` で起動済みであること  
> **Swagger UI**: `http://localhost:8000/docs` からすべての操作が可能

---

## 目次

- [正常系シナリオ](#正常系シナリオ)
  1. [ユーザー登録](#ステップ-1-ユーザー登録)
  2. [ログイン（JWT取得）](#ステップ-2-ログインjwt取得)
  3. [Swagger への認証情報の登録](#ステップ-3-swagger-への認証情報の登録)
  4. [アイテム投稿](#ステップ-4-アイテム投稿)
  5. [AI 要約の確認](#ステップ-5-ai-要約の確認)
  6. [RAG Q&A の実行](#ステップ-6-rag-qa-の実行)
  7. [フィードバックの送信](#ステップ-7-フィードバックの送信)
  8. [フィードバック集計の確認](#ステップ-8-フィードバック集計の確認)
- [異常系シナリオ](#異常系シナリオ)
  - [異常系 A：未認証でのアイテム投稿（401）](#異常系-a未認証でのアイテム投稿401)
  - [異常系 B：不正な feedback 値（422）](#異常系-b不正な-feedback-値422)
  - [異常系 C：PDF 外の内容に関する質問](#異常系-cpdf-外の内容に関する質問)

---

## 正常系シナリオ

ユーザー登録からフィードバック集計まで、一連のフローを順番に実行します。

---

### ステップ 1: ユーザー登録

新規ユーザーを登録します。

#### Swagger での操作手順

1. `http://localhost:8000/docs` を開く
2. **`POST /auth/register`** セクションを展開し、「Try it out」をクリック
3. Request body に以下を入力して「Execute」をクリック

```json
{
  "username": "demo_user",
  "password": "demo_pass_123"
}
```

#### 期待するレスポンス

```
HTTP 201 Created
```

```json
{
  "message": "User registered",
  "user": {
    "id": 1,
    "username": "demo_user"
  }
}
```

> **ポイント**: 同じ username で再登録しようとすると `400 Bad Request`（`"Username already registered"`）が返ります。

---

### ステップ 2: ログイン（JWT取得）

登録済みのユーザーでログインし、アクセストークン（JWT）を取得します。

#### Swagger での操作手順

1. **`POST /auth/login`** セクションを展開し、「Try it out」をクリック
2. フォームに以下を入力して「Execute」をクリック

| フィールド | 入力値 |
|-----------|--------|
| `username` | `demo_user` |
| `password` | `demo_pass_123` |

> `Content-Type: application/x-www-form-urlencoded` 形式（OAuth2 標準形式）で送信されます。

#### 期待するレスポンス

```
HTTP 200 OK
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

> **重要**: `access_token` の値をコピーしておきます。次のステップで使用します。

---

### ステップ 3: Swagger への認証情報の登録

取得したトークンを Swagger に登録し、以降の認証必須 API を操作できるようにします。

#### Swagger での操作手順

1. ページ右上の **「Authorize」** ボタン（🔒鍵マーク）をクリック
2. `OAuth2PasswordBearer` の `Value` 欄に、ステップ 2 で取得した `access_token` を貼り付ける
3. 「Authorize」→「Close」の順でクリック

> **確認**: 各エンドポイントの鍵アイコンが施錠状態（🔒）になっていれば登録完了です。

---

### ステップ 4: アイテム投稿

認証済みユーザーとしてアイテムを投稿します。  
投稿完了後、バックグラウンドで AI による本文要約が自動生成されます。

#### Swagger での操作手順

1. **`POST /items`** セクションを展開し、「Try it out」をクリック
2. Request body に以下を入力して「Execute」をクリック

```json
{
  "title": "FastAPI の概要",
  "body": "FastAPI は Python 製の高速な Web フレームワークです。Pydantic による型検証と、OpenAPI 準拠の自動ドキュメント生成を備えています。非同期処理（async/await）をネイティブサポートしており、Node.js や Go に匹敵するパフォーマンスを発揮します。"
}
```

#### 期待するレスポンス

```
HTTP 201 Created
```

```json
{
  "message": "Item created",
  "item": {
    "id": 1,
    "title": "FastAPI の概要",
    "body": "FastAPI は Python 製の高速な Web フレームワーク...",
    "summary": null
  }
}
```

> **ポイント**: `summary` は投稿直後に `null` となります。バックグラウンドタスクで AI 要約が生成されるため、数秒後に確認します（次のステップ）。

---

### ステップ 5: AI 要約の確認

バックグラウンドで生成された AI 要約が `summary` フィールドに保存されているか確認します。

#### Swagger での操作手順

1. **`GET /items`** セクションを展開し、「Try it out」→「Execute」をクリック
2. 数秒後（AI 処理完了後）に再度 Execute を実行

#### 期待するレスポンス（要約生成後）

```
HTTP 200 OK
```

```json
[
  {
    "id": 1,
    "title": "FastAPI の概要",
    "body": "FastAPI は Python 製の高速な Web フレームワークです...",
    "summary": "FastAPI は型検証・自動ドキュメント生成・非同期処理をサポートする Python 製の高速 Web フレームワーク。"
  }
]
```

> **ポイント**: `summary` が `null` のままの場合は、OpenAI API キーの設定か通信状況を確認してください。

---

### ステップ 6: RAG Q&A の実行

FAISS インデックスに登録されたPDF ドキュメントの内容を根拠に、AI が質問に回答します。

#### Swagger での操作手順

1. **`POST /qa/`** セクションを展開し、「Try it out」をクリック
2. Request body に以下を入力して「Execute」をクリック

```json
{
  "question": "このシステムの主な機能は何ですか？"
}
```

#### 期待するレスポンス

```
HTTP 200 OK
```

```json
{
  "answer": "このシステムは、PDF ドキュメントに基づいた質問応答（RAG）、アイテム管理、フィードバック収集、JWT 認証を提供します。",
  "sources": [
    {
      "source": "manual.pdf",
      "page": 1,
      "content_preview": "本システムは RAG（Retrieval-Augmented Generation）を採用し..."
    },
    {
      "source": "manual.pdf",
      "page": 3,
      "content_preview": "FastAPI を使用した REST API として実装されており..."
    }
  ]
}
```

> **ポイント**: `sources` に引用元ファイル名・ページ番号・チャンク冒頭が含まれます。回答の根拠を追跡できます。

---

### ステップ 7: フィードバックの送信

ステップ 4 で作成したアイテム（`id: 1`）に「良い評価」のフィードバックを送信します。

#### Swagger での操作手順

1. **`POST /feedback/`** セクションを展開し、「Try it out」をクリック
2. Request body に以下を入力して「Execute」をクリック

```json
{
  "item_id": 1,
  "rating": "good"
}
```

#### 期待するレスポンス

```
HTTP 200 OK
```

```json
{
  "id": 1,
  "message": "Feedback saved: good"
}
```

> **補足**: 同じアイテムに複数回フィードバックを送信できます。集計時に件数が累積されます。

---

### ステップ 8: フィードバック集計の確認

全フィードバックの統計情報（good 件数・bad 件数・good 率）を確認します。

#### Swagger での操作手順

1. **`GET /feedback/summary`** セクションを展開し、「Try it out」→「Execute」をクリック

#### 期待するレスポンス

```
HTTP 200 OK
```

```json
{
  "good_count": 1,
  "bad_count": 0,
  "rating_rate": 100.0
}
```

> **ポイント**: `rating_rate` は `good_count / (good_count + bad_count) * 100` で計算されます。  
> フィードバックが 0 件の場合は `rating_rate: 0.0` が返ります（ゼロ除算回避済み）。

---

## 異常系シナリオ

意図的に不正なリクエストを送信し、適切なエラーレスポンスが返ることを確認します。

---

### 異常系 A：未認証でのアイテム投稿（401）

JWT トークンなしで認証必須エンドポイントにアクセスした場合の挙動を確認します。

#### 事前準備

Swagger の認証を解除します。

1. ページ右上の「Authorize」ボタンをクリック
2. 「Logout」をクリックして認証情報を削除
3. 「Close」をクリック

#### Swagger での操作手順

1. **`POST /items`** セクションを展開し、「Try it out」をクリック
2. Request body に以下を入力して「Execute」をクリック

```json
{
  "title": "未認証テスト",
  "body": "このリクエストは失敗するはずです。"
}
```

#### 期待するレスポンス

```
HTTP 401 Unauthorized
```

```json
{
  "detail": "Not authenticated"
}
```

> **確認ポイント**: 認証なしでは投稿できないことを確認します。操作後はステップ 3 の手順でトークンを再登録してください。

---

### 異常系 B：不正な feedback 値（422）

`rating` フィールドに `"good"` / `"bad"` 以外の値を送信した場合の挙動を確認します。

#### Swagger での操作手順

1. **`POST /feedback/`** セクションを展開し、「Try it out」をクリック
2. Request body の `rating` に不正な値を入力して「Execute」をクリック

```json
{
  "item_id": 1,
  "rating": "excellent"
}
```

#### 期待するレスポンス

```
HTTP 422 Unprocessable Entity
```

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "rating"],
      "msg": "Value error, rating must be \"good\" or \"bad\"",
      "input": "excellent",
      "ctx": {
        "error": "rating must be \"good\" or \"bad\""
      }
    }
  ]
}
```

> **確認ポイント**: Pydantic のバリデーターが `"good"` / `"bad"` 以外を拒否していることを確認します。  
> `422 Unprocessable Entity` はリクエストの形式は正しいが、値が不正な場合に返ります。

---

### 異常系 C：PDF 外の内容に関する質問

FAISS インデックスに存在しないトピック（ドキュメントに記載のない内容）を質問した場合の挙動を確認します。

#### Swagger での操作手順

1. **`POST /qa/`** セクションを展開し、「Try it out」をクリック
2. ドキュメントと無関係な質問を入力して「Execute」をクリック

```json
{
  "question": "明日の東京の天気を教えてください。"
}
```

#### 期待するレスポンス

```
HTTP 200 OK
```

```json
{
  "answer": "提供されたドキュメントにはその情報が含まれていないため、わかりません。",
  "sources": [
    {
      "source": "manual.pdf",
      "page": 2,
      "content_preview": "（質問と無関係なチャンクが返される場合があります）..."
    }
  ]
}
```

> **確認ポイント**:
> - `qa_prompt_v2.yaml` のルールにより、コンテキスト外の情報には「わかりません」と回答するよう指示されています。
> - ステータスコードは `200 OK` ですが、AI が「回答不能」を明示的に返します。
> - `sources` には FAISS が類似度検索で取得した最近傍チャンクが返りますが、回答には使用されません。

---

## 補足：curl コマンドでの実行例

Swagger を使わずにターミナルから操作する場合のコマンド例です。

```bash
# 1. ユーザー登録
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "demo_user", "password": "demo_pass_123"}'

# 2. ログイン（JWT取得）
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo_user&password=demo_pass_123" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 3. アイテム投稿（JWT付き）
curl -X POST http://localhost:8000/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "FastAPI の概要", "body": "FastAPI は Python 製の高速な Web フレームワークです。"}'

# 4. アイテム一覧取得（AI要約確認）
curl http://localhost:8000/items

# 5. Q&A
curl -X POST http://localhost:8000/qa/ \
  -H "Content-Type: application/json" \
  -d '{"question": "このシステムの主な機能は何ですか？"}'

# 6. フィードバック送信
curl -X POST http://localhost:8000/feedback/ \
  -H "Content-Type: application/json" \
  -d '{"item_id": 1, "rating": "good"}'

# 7. フィードバック集計
curl http://localhost:8000/feedback/summary
```
