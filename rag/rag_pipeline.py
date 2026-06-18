"""
RAG パイプライン
  1. data/test.pdf を読み込み・テキスト前処理（改行・ノイズ除去）
  2. RecursiveCharacterTextSplitter でチャンク分割（size=500 / overlap=50）
  3. OpenAI 埋め込みモデル（text-embedding-3-small）でベクトル生成
  4. FAISS インデックスを作成・ローカル保存
  5. 類似検索 Top-3 を確認

実行方法:
    python rag/rag_pipeline.py
"""

import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ─────────────────────────────────────────────────────────
# 0. 環境変数の読み込み
# ─────────────────────────────────────────────────────────
# スクリプトの 2 階層上 = プロジェクトルートの .env を読み込む
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# ─────────────────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────────────────
PDF_PATH = ROOT_DIR / "data" / "test.pdf"   # 読み込む PDF ファイルパス
INDEX_DIR = ROOT_DIR / "rag" / "faiss_index"  # FAISS インデックスの保存先

CHUNK_SIZE = 500     # 1 チャンクの最大文字数
CHUNK_OVERLAP = 50   # 隣接チャンク間で重複させる文字数
TOP_K = 3            # 類似検索で取得する上位件数

# 類似検索に使うクエリ（PDF の内容に合わせて変更してください）
SEARCH_QUERY = "このドキュメントの主要なトピックは何ですか？"

# YAML プロンプトファイルパス
QA_PROMPT_YAML = ROOT_DIR / "prompts" / "qa_prompt_v1.yaml"


# ─────────────────────────────────────────────────────────
# YAML ファイル読み込み関数
# ─────────────────────────────────────────────────────────
def load_qa_prompt_yaml(yaml_path: Path) -> dict:
    """
    YAML ファイルから QA プロンプト設定を読み込んで返す。
    ファイルが見つからない場合は None を返す。
    """
    if not yaml_path.exists():
        print(f"[WARNING] プロンプト YAML が見つかりません: {yaml_path}")
        return None
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config.get("prompt", {})
    except Exception as e:
        print(f"[ERROR] YAML 読み込み失敗: {e}")
        return None


# ─────────────────────────────────────────────────────────
# 1. PDF 読み込み・テキスト前処理
# ─────────────────────────────────────────────────────────
def clean_text(text: str) -> str:
    """テキストの前処理: 連続改行・余分なスペース・制御文字を除去する。"""
    # 連続する改行をスペース 1 つに置換
    text = re.sub(r"\n+", " ", text)
    # 連続するスペースを 1 つに圧縮
    text = re.sub(r" {2,}", " ", text)
    # ページ番号や孤立した数字のみの行など、極端に短い断片を除去
    text = re.sub(r"\s{0,3}\d{1,4}\s{0,3}", " ", text) if len(text) < 10 else text
    return text.strip()


def load_and_preprocess(pdf_path: Path) -> list:
    """
    PDF を PyPDFLoader で読み込み、各ページのテキストを前処理して返す。
    ファイルが存在しない場合はエラーメッセージを表示して終了する。
    """
    print(f"[STEP 1] PDF 読み込み: {pdf_path}")

    if not pdf_path.exists():
        print(
            f"  [ERROR] {pdf_path} が見つかりません。\n"
            "  data/ フォルダに test.pdf を配置してから再実行してください。"
        )
        sys.exit(1)

    # PyPDFLoader: ページごとに Document オブジェクトを生成
    loader = PyPDFLoader(str(pdf_path))
    docs = loader.load()
    print(f"  → {len(docs)} ページを取得")

    # 各ページの page_content を前処理
    for doc in docs:
        doc.page_content = clean_text(doc.page_content)

    return docs


# ─────────────────────────────────────────────────────────
# 2. チャンク分割
# ─────────────────────────────────────────────────────────
def split_documents(docs: list) -> list:
    """
    RecursiveCharacterTextSplitter でテキストをチャンクに分割して返す。
    分割後、先頭 5 件のプレビューを表示する。
    """
    print(f"\n[STEP 2] チャンク分割 (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # 日本語テキストを考慮した区切り文字の優先順序
        separators=["\n\n", "\n", "。", "、", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"  → {len(chunks)} チャンクに分割")

    # 先頭 5 件のプレビューを表示（80 文字までを表示）
    preview_count = min(5, len(chunks))
    print(f"  --- チャンクプレビュー (先頭 {preview_count} 件) ---")
    for i in range(preview_count):
        chunk = chunks[i]
        preview = chunk.page_content[:80].replace("\n", " ")
        page = chunk.metadata.get("page", "?")
        print(f"  chunk[{i}] (page={page}): {preview} ...")

    return chunks


# ─────────────────────────────────────────────────────────
# 3. 埋め込み生成 & FAISS インデックス作成・保存
# ─────────────────────────────────────────────────────────
def build_and_save_faiss(chunks: list) -> FAISS:
    """
    OpenAI の埋め込みモデルでベクトルを生成し、FAISS インデックスを
    作成・ローカルに保存する。保存した vectorstore を返す。
    """
    print("\n[STEP 3] 埋め込み生成 & FAISS インデックス作成")

    # text-embedding-3-small: コストパフォーマンスの良い埋め込みモデル
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # チャンクリストから一括でベクトル生成 → FAISS インデックスを構築
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # インデックスをローカルに保存（allow_dangerous_deserialization は読み込み時に必要）
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(INDEX_DIR))
    print(f"  → インデックスを保存: {INDEX_DIR}")

    return vectorstore


# ─────────────────────────────────────────────────────────
# 4. 類似検索 Top-K
# ─────────────────────────────────────────────────────────
def similarity_search(vectorstore: FAISS, query: str, k: int = TOP_K) -> None:
    """
    FAISS インデックスに対してクエリを投げ、類似度上位 k 件を表示する。
    """
    print(f"\n[STEP 4] 類似検索 Top-{k}")
    print(f"  クエリ: 「{query}」\n")

    results = vectorstore.similarity_search(query, k=k)

    for rank, doc in enumerate(results, start=1):
        source = doc.metadata.get("source", "不明")
        page = doc.metadata.get("page", "?")
        # 結果テキストは 200 文字までを表示
        preview = doc.page_content[:200].replace("\n", " ")
        print(f"  ── Rank {rank} (source={Path(source).name}, page={page}) ──")
        print(f"  {preview}\n")


# ─────────────────────────────────────────────────────────
# 5. 保存済み FAISS インデックスの読み込み
# ─────────────────────────────────────────────────────────
def load_faiss_index() -> FAISS:
    """
    ローカルに保存されている FAISS インデックスを読み込んで返す。
    インデックスが見つからない場合はエラーを出力して None を返す。
    """
    if not INDEX_DIR.exists():
        print(f"[ERROR] FAISS インデックスが見つかりません: {INDEX_DIR}")
        print("  先に python rag/rag_pipeline.py を実行してインデックスを作成してください。")
        return None

    # 埋め込みモデルを指定して FAISS インデックスを読み込む
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.load_local(
        str(INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True
    )
    return vectorstore


# ─────────────────────────────────────────────────────────
# 6. RAG での回答生成（引用元情報付き）
# ─────────────────────────────────────────────────────────
def rag_with_sources(query: str, k: int = 3) -> dict:
    """
    質問に対して RAG により回答を生成し、引用元の chunk 情報を含めて返す。
    プロンプトテンプレートは YAML ファイルから読み込む。

    Args:
        query: ユーザーからの質問
        k: 類似検索で取得するチャンク数（デフォルト 3）

    Returns:
        {
            "answer": "生成された回答テキスト",
            "sources": [
                {
                    "source": "ファイル名",
                    "page": ページ番号,
                    "content_preview": "内容の冒頭（最初 200 文字）"
                },
                ...
            ]
        }
    """
    # ステップ 1: FAISS インデックスを読み込む
    vectorstore = load_faiss_index()
    if vectorstore is None:
        return {
            "answer": "エラー: FAISS インデックスが利用できません。",
            "sources": []
        }

    # ステップ 2: 類似検索で関連チャンクを取得
    retrieved_docs = vectorstore.similarity_search(query, k=k)

    # ステップ 3: コンテキストを組立（複数チャンクのテキストを統合）
    context_text = "\n\n".join(
        [doc.page_content for doc in retrieved_docs]
    )

    # ステップ 4: YAML からプロンプトテンプレートを読み込む
    # YAML が見つからない場合は、デフォルトのプロンプトを使用
    prompt_config = load_qa_prompt_yaml(QA_PROMPT_YAML)
    
    if prompt_config:
        # YAML からテンプレートと LLM パラメータを取得
        template = prompt_config.get("template", "")
        llm_config = prompt_config.get("llm_config", {})
        model = llm_config.get("model", "gpt-4o-mini")
        temperature = llm_config.get("temperature", 0.3)
        max_tokens = llm_config.get("max_tokens", 1000)
    else:
        # フォールバック: デフォルトプロンプト
        template = """あなたは PDF ドキュメント内容に基づいて質問に答える AI アシスタントです。

【ルール】
- 以下の「コンテキスト」の内容のみを根拠に答えてください
- コンテキストに含まれていない情報は答えないでください
- 「わかりません」や「記載されていません」と明確に答えてください

【コンテキスト】
{context}

【質問】
{question}

【回答】
"""
        model = "gpt-4o-mini"
        temperature = 0.3
        max_tokens = 1000

    # プロンプトテンプレートを作成
    prompt_template = PromptTemplate(
        input_variables=["context", "question"],
        template=template
    )

    # LLM の初期化（YAML 設定に基づく）
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )

    # LangChain パイプライン: prompt → llm → output_parser
    chain = prompt_template | llm | StrOutputParser()

    # LLM に質問を投げて回答を生成
    answer = chain.invoke({
        "context": context_text,
        "question": query
    })

    # ステップ 5: 引用元情報を整理（source, page, 内容プレビュー）
    sources = []
    for doc in retrieved_docs:
        source_name = Path(doc.metadata.get("source", "不明")).name
        page_num = doc.metadata.get("page", "?")
        content_preview = doc.page_content[:200].replace("\n", " ")

        sources.append({
            "source": source_name,
            "page": page_num,
            "content_preview": content_preview
        })

    return {
        "answer": answer,
        "sources": sources
    }


# ─────────────────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 60)
    print("  RAG パイプライン開始")
    print("=" * 60)

    # STEP 1: PDF 読み込み・前処理
    docs = load_and_preprocess(PDF_PATH)

    # STEP 2: チャンク分割・プレビュー表示
    chunks = split_documents(docs)

    # STEP 3: 埋め込み生成 → FAISS インデックス作成・保存
    vectorstore = build_and_save_faiss(chunks)

    # STEP 4: 類似検索 Top-3 確認
    similarity_search(vectorstore, SEARCH_QUERY)

    print("=" * 60)
    print("  RAG パイプライン完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
