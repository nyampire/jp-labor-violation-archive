#!/usr/bin/env python3
"""
add_data_gap_flag.py - 既存のappearances.tsvにcrossed_data_gapフラグを追加する

データ欠損期間（2018年8月〜2020年11月）をまたぐレコードを検出し、
フラグを付けます。

使用例:
    python scripts/add_data_gap_flag.py
"""

import pandas as pd
from pathlib import Path

# データ欠損期間の定義
DATA_GAP_START = "2018-08-01"
DATA_GAP_END = "2020-11-30"


def crosses_data_gap(first_date: str, last_date: str) -> bool:
    """データ欠損期間をまたぐかどうかをチェック"""
    if not first_date or not last_date:
        return False
    try:
        return first_date <= DATA_GAP_START and last_date >= DATA_GAP_END
    except:
        return False


def main():
    appearances_path = Path("timeline/appearances.tsv")
    
    if not appearances_path.exists():
        print(f"エラー: ファイルが見つかりません: {appearances_path}")
        return
    
    # データ読み込み
    df = pd.read_csv(appearances_path, sep='\t', dtype=str).fillna("")
    
    print(f"総レコード数: {len(df)}")
    
    # crossed_data_gap カラムを追加（存在しない場合）
    if "crossed_data_gap" not in df.columns:
        df["crossed_data_gap"] = ""
    
    # 各レコードをチェック
    flagged_count = 0
    for idx, row in df.iterrows():
        first = row.get("first_appeared", "")
        last = row.get("last_appeared", "")
        
        if crosses_data_gap(first, last):
            df.at[idx, "crossed_data_gap"] = "true"
            flagged_count += 1
    
    # 保存
    df.to_csv(appearances_path, sep='\t', index=False)
    
    print(f"フラグを追加: {flagged_count} 件")
    print(f"保存完了: {appearances_path}")


if __name__ == "__main__":
    main()
