"""
日次トークン使用状況レポート

logs/token_usage.csv を読み込み、以下の統計情報を表示します：
  - 操作別の集計（呼び出し回数、平均入力トークン、平均出力トークン、合計トークン）
  - 日付別の合計トークン
  - 料金換算（gpt-4o-mini の料金に基づく）
  - 日次コスト・週次コスト（直近7日間）
  - 上位コスト要因
  - 異常検知（1リクエストあたりのトークンが平均の3倍を超えるケース）

実行方法:
    python scripts/daily_report.py
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import statistics


# ─────────────────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────────────────
# プロジェクトルート（このスクリプトの2階層上）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ログファイルパス
LOG_FILE = PROJECT_ROOT / "logs" / "token_usage.csv"

# gpt-4o-mini の料金（1M トークンあたり）
PRICE_INPUT_PER_1M = 0.15  # USD per 1M input tokens
PRICE_OUTPUT_PER_1M = 0.60  # USD per 1M output tokens


# ─────────────────────────────────────────────────────────
# ユーティリティ関数
# ─────────────────────────────────────────────────────────
def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """
    トークン数を料金に換算する

    Args:
        input_tokens (int): 入力トークン数
        output_tokens (int): 出力トークン数

    Returns:
        float: 計算された料金（USD）
    """
    input_cost = (input_tokens / 1_000_000) * PRICE_INPUT_PER_1M
    output_cost = (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
    return input_cost + output_cost


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    ISO形式のタイムスタンプ文字列をdatetime オブジェクトに変換する

    Args:
        timestamp_str (str): ISO形式のタイムスタンプ（例：2026-06-22T10:30:45.123456）

    Returns:
        datetime: パースされた datetime オブジェクト
    """
    try:
        return datetime.fromisoformat(timestamp_str)
    except ValueError:
        # パース失敗時はNoneを返す
        return None


def get_date_string(dt: datetime) -> str:
    """
    datetime オブジェクトを日付文字列（YYYY-MM-DD）に変換する

    Args:
        dt (datetime): datetime オブジェクト

    Returns:
        str: 日付文字列
    """
    return dt.strftime("%Y-%m-%d")


# ─────────────────────────────────────────────────────────
# レポート関数
# ─────────────────────────────────────────────────────────
def load_and_analyze_logs() -> dict:
    """
    token_usage.csv を読み込み、データを解析する

    Returns:
        dict: 解析結果を含む辞書
            - records: 全レコードのリスト
            - operation_stats: 操作別の統計情報
            - daily_stats: 日付別の統計情報
            - all_total_tokens: 全トークンの平均（異常検知用）
    """
    # CSVファイルの存在確認
    if not LOG_FILE.exists():
        print(f"[ERROR] ログファイルが見つかりません: {LOG_FILE}")
        print("  token_usage.csv が存在しません。API を呼び出してログを生成してください。")
        exit(1)

    # ─────────────────────────────────────────────────────
    # ステップ 1: CSV を読み込む
    # ─────────────────────────────────────────────────────
    records = []
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                record = {
                    'timestamp': parse_timestamp(row['timestamp']),
                    'request_id': row['request_id'],
                    'operation': row['operation'],
                    'model': row['model'],
                    'input_tokens': int(row['input_tokens']),
                    'output_tokens': int(row['output_tokens']),
                    'total_tokens': int(row['total_tokens']),
                }
                # タイムスタンプのパースに成功した場合のみ記録
                if record['timestamp'] is not None:
                    records.append(record)
            except (ValueError, KeyError) as e:
                # データ行のパースに失敗した場合はスキップ
                print(f"[WARNING] レコード解析スキップ: {e}")
                continue

    if not records:
        print("[ERROR] 解析可能なレコードがありません。")
        exit(1)

    print(f"[INFO] {len(records)} 件のレコードを読み込みました\n")

    # ─────────────────────────────────────────────────────
    # ステップ 2: 操作別の統計情報を集計
    # ─────────────────────────────────────────────────────
    operation_stats = defaultdict(lambda: {
        'count': 0,
        'input_tokens_list': [],
        'output_tokens_list': [],
        'total_tokens': 0,
        'cost': 0.0
    })

    for record in records:
        op = record['operation']
        operation_stats[op]['count'] += 1
        operation_stats[op]['input_tokens_list'].append(record['input_tokens'])
        operation_stats[op]['output_tokens_list'].append(record['output_tokens'])
        operation_stats[op]['total_tokens'] += record['total_tokens']
        operation_stats[op]['cost'] += calculate_cost(
            record['input_tokens'],
            record['output_tokens']
        )

    # ─────────────────────────────────────────────────────
    # ステップ 3: 日付別の統計情報を集計
    # ─────────────────────────────────────────────────────
    daily_stats = defaultdict(lambda: {
        'total_tokens': 0,
        'cost': 0.0,
        'count': 0
    })

    for record in records:
        date_key = get_date_string(record['timestamp'])
        daily_stats[date_key]['total_tokens'] += record['total_tokens']
        daily_stats[date_key]['cost'] += calculate_cost(
            record['input_tokens'],
            record['output_tokens']
        )
        daily_stats[date_key]['count'] += 1

    # ─────────────────────────────────────────────────────
    # ステップ 4: 平均トークン数を計算（異常検知用）
    # ─────────────────────────────────────────────────────
    all_total_tokens = [r['total_tokens'] for r in records]
    avg_total_tokens = statistics.mean(all_total_tokens)

    return {
        'records': records,
        'operation_stats': dict(operation_stats),
        'daily_stats': dict(daily_stats),
        'all_total_tokens': all_total_tokens,
        'avg_total_tokens': avg_total_tokens
    }


def print_operation_summary(analysis_data: dict) -> None:
    """
    操作別の集計情報を表示する

    Args:
        analysis_data (dict): 解析結果
    """
    print("=" * 80)
    print("【操作別集計】")
    print("=" * 80)
    print(f"{'Operation':<15} {'Count':<8} {'Avg Input':<12} {'Avg Output':<12} {'Total':<12} {'Cost (USD)':<12}")
    print("-" * 80)

    for operation, stats in sorted(analysis_data['operation_stats'].items()):
        count = stats['count']
        avg_input = statistics.mean(stats['input_tokens_list']) if stats['input_tokens_list'] else 0
        avg_output = statistics.mean(stats['output_tokens_list']) if stats['output_tokens_list'] else 0
        total_tokens = stats['total_tokens']
        cost = stats['cost']

        print(
            f"{operation:<15} {count:<8} {avg_input:<12.1f} {avg_output:<12.1f} {total_tokens:<12} ${cost:<11.4f}"
        )

    print()


def print_daily_summary(analysis_data: dict) -> None:
    """
    日付別の集計情報を表示する

    Args:
        analysis_data (dict): 解析結果
    """
    print("=" * 80)
    print("【日付別集計】")
    print("=" * 80)
    print(f"{'Date':<15} {'Count':<8} {'Total Tokens':<15} {'Cost (USD)':<12}")
    print("-" * 80)

    for date_str in sorted(analysis_data['daily_stats'].keys()):
        stats = analysis_data['daily_stats'][date_str]
        count = stats['count']
        total_tokens = stats['total_tokens']
        cost = stats['cost']

        print(
            f"{date_str:<15} {count:<8} {total_tokens:<15} ${cost:<11.4f}"
        )

    print()


def print_daily_and_weekly_cost(analysis_data: dict) -> None:
    """
    日次コスト・週次コストを表示する

    Args:
        analysis_data (dict): 解析結果
    """
    print("=" * 80)
    print("【コスト集計】")
    print("=" * 80)

    # 最新日付を取得
    dates = sorted(analysis_data['daily_stats'].keys())
    if not dates:
        print("[ERROR] レコードがありません")
        return

    latest_date = datetime.strptime(dates[-1], "%Y-%m-%d")

    # 日次コスト（最新日付）
    latest_date_str = get_date_string(latest_date)
    daily_cost = analysis_data['daily_stats'].get(latest_date_str, {}).get('cost', 0.0)
    daily_tokens = analysis_data['daily_stats'].get(latest_date_str, {}).get('total_tokens', 0)

    print(f"【今日（{latest_date_str}）のコスト】")
    print(f"  合計トークン: {daily_tokens:,}")
    print(f"  合計コスト: ${daily_cost:.4f}\n")

    # 週次コスト（直近7日間）
    weekly_cost = 0.0
    weekly_tokens = 0
    week_start_date = latest_date - timedelta(days=6)

    print(f"【週次コスト（{week_start_date.strftime('%Y-%m-%d')} ～ {latest_date_str}）】")
    for date_str in sorted(analysis_data['daily_stats'].keys()):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        if week_start_date <= date_obj <= latest_date:
            daily_stats = analysis_data['daily_stats'][date_str]
            weekly_cost += daily_stats['cost']
            weekly_tokens += daily_stats['total_tokens']

    print(f"  合計トークン: {weekly_tokens:,}")
    print(f"  合計コスト: ${weekly_cost:.4f}\n")


def print_top_cost_drivers(analysis_data: dict, top_n: int = 3) -> None:
    """
    上位コスト要因（トークン消費が多いoperation）を表示する

    Args:
        analysis_data (dict): 解析結果
        top_n (int): 表示する上位件数
    """
    print("=" * 80)
    print(f"【上位コスト要因（Top {top_n}）】")
    print("=" * 80)

    # operationをコストでソート
    sorted_operations = sorted(
        analysis_data['operation_stats'].items(),
        key=lambda x: x[1]['cost'],
        reverse=True
    )

    for rank, (operation, stats) in enumerate(sorted_operations[:top_n], start=1):
        percentage = (stats['total_tokens'] / sum(s['total_tokens'] for s in analysis_data['operation_stats'].values())) * 100
        print(
            f"{rank}. {operation:<15} "
            f"Tokens: {stats['total_tokens']:>10,} "
            f"({percentage:>5.1f}%) "
            f"Cost: ${stats['cost']:>8.4f}"
        )

    print()


def print_anomalies(analysis_data: dict, threshold_multiplier: float = 3.0) -> None:
    """
    異常検知：1リクエストあたりのtotal_tokensが平均の threshold_multiplier 倍を超えるリクエストを表示する

    Args:
        analysis_data (dict): 解析結果
        threshold_multiplier (float): 異常の倍数閾値（デフォルト：3倍）
    """
    print("=" * 80)
    print(f"【異常検知】平均の {threshold_multiplier} 倍以上のトークン使用リクエスト")
    print("=" * 80)

    avg_tokens = analysis_data['avg_total_tokens']
    threshold = avg_tokens * threshold_multiplier

    anomalies = [r for r in analysis_data['records'] if r['total_tokens'] > threshold]

    if not anomalies:
        print(f"  平均トークン数: {avg_tokens:.1f}")
        print(f"  異常の閾値: {threshold:.1f}")
        print("  異常なリクエストはありません\n")
        return

    print(f"  平均トークン数: {avg_tokens:.1f}")
    print(f"  異常の閾値: {threshold:.1f}")
    print(f"  異常リクエスト数: {len(anomalies)}\n")
    print(f"{'Timestamp':<27} {'Operation':<12} {'Total Tokens':<15} {'Ratio':<8}")
    print("-" * 80)

    for record in sorted(anomalies, key=lambda x: x['total_tokens'], reverse=True)[:10]:
        timestamp = record['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
        total = record['total_tokens']
        ratio = total / avg_tokens
        print(
            f"{timestamp:<27} {record['operation']:<12} {total:<15} {ratio:.1f}x"
        )

    print()


# ─────────────────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────────────────
def main() -> None:
    print("\n")
    print("=" * 80)
    print("  日次トークン使用状況レポート")
    print("=" * 80)
    print()

    # データを読み込み・解析
    analysis_data = load_and_analyze_logs()

    # 各種統計情報を表示
    print_operation_summary(analysis_data)
    print_daily_summary(analysis_data)
    print_daily_and_weekly_cost(analysis_data)
    print_top_cost_drivers(analysis_data, top_n=3)
    print_anomalies(analysis_data, threshold_multiplier=3.0)

    print("=" * 80)
    print("  レポート終了")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
