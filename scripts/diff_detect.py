#!/usr/bin/env python3
"""
diff_detect.py - 企業リストの差分を検出し、掲載期間を追跡するスクリプト

新しい企業リスト（current.tsv）と既存の掲載履歴（appearances.tsv）を比較し、
以下を検出・記録します：

- 新規掲載: first_appeared を記録
- 掲載終了: last_appeared と duration_days を記録
- 変更ログ: changes.tsv に追記

使用例:
    # 基本的な使い方
    python diff_detect.py timeline/current.tsv
    
    # 特定の日付を指定（過去データを処理するとき）
    python diff_detect.py timeline/current.tsv -d 2024-06-01
    
    # ファイルパスを指定
    python diff_detect.py data.tsv -a timeline/appearances.tsv -c timeline/changes.tsv
"""

import sys
from pathlib import Path
from datetime import datetime, date
import pandas as pd


# =============================================================================
# データ読み込み
# =============================================================================

def load_appearances(filepath: Path) -> pd.DataFrame:
    """
    既存の appearances.tsv を読み込む
    
    ファイルが存在しない場合は空のDataFrameを返す（初回実行時）
    
    Args:
        filepath: appearances.tsv のパス
    
    Returns:
        掲載履歴のDataFrame
    """
    if filepath.exists():
        return pd.read_csv(filepath, sep='\t', dtype=str).fillna("")
    else:
        # 初回実行時は空のDataFrameを返す
        return pd.DataFrame(columns=[
            "company_name", "location", "labor_bureau",
            "first_appeared", "last_appeared", "duration_days",
            "violation_law", "violation_summary", "prosecution_date", "status"
        ])


def load_current_list(filepath: Path) -> pd.DataFrame:
    """
    最新の企業リスト（extract_companies.py の出力）を読み込む
    
    Args:
        filepath: current.tsv のパス
    
    Returns:
        企業リストのDataFrame
    """
    return pd.read_csv(filepath, sep='\t', dtype=str).fillna("")


# =============================================================================
# 企業識別
# =============================================================================

def create_company_key(row: pd.Series) -> str:
    """
    企業を一意に識別するキーを生成する
    
    同じ企業でも異なる違反で複数回掲載される可能性があるため、
    企業名 + 所在地 + 違反法条 の組み合わせで識別する。
    
    Args:
        row: DataFrameの行
    
    Returns:
        一意識別キー（文字列）
    
    Examples:
        >>> row = pd.Series({"company_name": "（株）ABC", "location": "東京都", "violation_law": "労基法32条"})
        >>> create_company_key(row)
        '（株）ABC|東京都|労基法32条'
    """
    return f"{row.get('company_name', '')}|{row.get('location', '')}|{row.get('violation_law', '')}"


# =============================================================================
# 差分検出
# =============================================================================

def detect_changes(appearances: pd.DataFrame, current: pd.DataFrame, update_date: str) -> tuple:
    """
    新旧データを比較し、追加・削除を検出する
    
    Args:
        appearances: 既存の掲載履歴
        current: 最新の企業リスト
        update_date: 更新日（YYYY-MM-DD形式）
    
    Returns:
        (更新後のappearances, 変更情報の辞書)
    """
    
    # 既存データのキーセットを作成
    existing_keys = set()
    key_to_idx = {}  # キー → DataFrameのインデックス
    
    for idx, row in appearances.iterrows():
        key = create_company_key(row)
        existing_keys.add(key)
        key_to_idx[key] = idx
    
    # 最新データのキーセットを作成
    current_keys = set()
    current_data = {}  # キー → 行データ
    
    for _, row in current.iterrows():
        key = create_company_key(row)
        current_keys.add(key)
        current_data[key] = row
    
    # ----- 新規追加の検出 -----
    new_keys = current_keys - existing_keys
    new_records = []
    
    for key in new_keys:
        row = current_data[key]
        new_records.append({
            "company_name": row.get("company_name", ""),
            "location": row.get("location", ""),
            "labor_bureau": row.get("labor_bureau", ""),
            "first_appeared": row.get("publication_date", "") or update_date,
            "last_appeared": "",
            "duration_days": "",
            "violation_law": row.get("violation_law", ""),
            "violation_summary": row.get("violation_summary", ""),
            "prosecution_date": row.get("prosecution_date", ""),
            "status": "active"
        })
    
    # ----- 削除の検出 -----
    removed_keys = existing_keys - current_keys
    
    for key in removed_keys:
        if key in key_to_idx:
            idx = key_to_idx[key]
            
            # すでに removed の場合はスキップ
            if appearances.at[idx, "status"] == "active":
                appearances.at[idx, "status"] = "removed"
                appearances.at[idx, "last_appeared"] = update_date
                
                # 掲載期間を計算
                first = appearances.at[idx, "first_appeared"]
                if first:
                    try:
                        first_date = datetime.strptime(first, "%Y-%m-%d").date()
                        last_date = datetime.strptime(update_date, "%Y-%m-%d").date()
                        duration = (last_date - first_date).days
                        appearances.at[idx, "duration_days"] = str(duration)
                    except ValueError:
                        pass
    
    # 新規レコードを追加
    if new_records:
        new_df = pd.DataFrame(new_records)
        appearances = pd.concat([appearances, new_df], ignore_index=True)
    
    # 変更情報
    changes = {
        "added": len(new_keys),
        "removed": len(removed_keys),
        "date": update_date
    }
    
    return appearances, changes


# =============================================================================
# 変更ログ
# =============================================================================

def append_changes_log(log_path: Path, changes: dict, total_active: int):
    """
    変更ログファイルに追記する
    
    Args:
        log_path: changes.tsv のパス
        changes: 変更情報の辞書
        total_active: 現在アクティブな件数
    """
    log_entry = pd.DataFrame([{
        "date": changes["date"],
        "added": changes["added"],
        "removed": changes["removed"],
        "total_active": total_active
    }])
    
    if log_path.exists():
        existing_log = pd.read_csv(log_path, sep='\t')
        log = pd.concat([existing_log, log_entry], ignore_index=True)
    else:
        log = log_entry
    
    log.to_csv(log_path, sep='\t', index=False)


# =============================================================================
# メイン処理
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='企業リストの差分を検出し、掲載期間を追跡する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s timeline/current.tsv                    # 基本的な使い方
  %(prog)s timeline/current.tsv -d 2024-06-01      # 日付を指定
  %(prog)s data.tsv -a my_appearances.tsv          # ファイルパスを指定
        """
    )
    parser.add_argument('current_list', help='最新の企業リストTSV（extract_companies.py の出力）')
    parser.add_argument('-a', '--appearances', default='timeline/appearances.tsv',
                        help='appearances.tsv のパス（デフォルト: timeline/appearances.tsv）')
    parser.add_argument('-d', '--date', default=None,
                        help='更新日（YYYY-MM-DD形式、省略時は今日）')
    parser.add_argument('-c', '--changes-log', default='timeline/changes.tsv',
                        help='変更ログのパス（デフォルト: timeline/changes.tsv）')
    
    args = parser.parse_args()
    
    # 更新日
    update_date = args.date or date.today().isoformat()
    
    # パスの準備
    appearances_path = Path(args.appearances)
    current_path = Path(args.current_list)
    changes_log_path = Path(args.changes_log)
    
    # 入力ファイルの存在確認
    if not current_path.exists():
        print(f"エラー: ファイルが見つかりません: {current_path}")
        sys.exit(1)
    
    # ディレクトリがなければ作成
    appearances_path.parent.mkdir(parents=True, exist_ok=True)
    changes_log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # データ読み込み
    appearances = load_appearances(appearances_path)
    current = load_current_list(current_path)
    
    print(f"更新日: {update_date}")
    print(f"既存の掲載履歴: {len(appearances)} 件")
    print(f"最新の企業リスト: {len(current)} 件")
    print()
    
    # 差分検出
    appearances, changes = detect_changes(appearances, current, update_date)
    
    # 現在アクティブな件数
    total_active = len(appearances[appearances["status"] == "active"])
    
    # 保存
    appearances.to_csv(appearances_path, sep='\t', index=False)
    append_changes_log(changes_log_path, changes, total_active)
    
    # 結果表示
    print(f"更新完了:")
    print(f"  新規追加: {changes['added']} 件")
    print(f"  掲載終了: {changes['removed']} 件")
    print(f"  現在アクティブ: {total_active} 件")
    print()
    print(f"出力:")
    print(f"  {appearances_path}")
    print(f"  {changes_log_path}")


if __name__ == "__main__":
    main()
