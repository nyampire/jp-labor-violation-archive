#!/usr/bin/env python3
"""
cleanup_tsv.py - appearances.tsv のデータをクリーンアップするスクリプト

問題のあるレコードを検出・修正します：
- 不正な日付形式
- 空の必須フィールド
- 重複レコード

使用例:
    python scripts/cleanup_tsv.py                    # 問題を検出して表示
    python scripts/cleanup_tsv.py --fix              # 問題を修正
    python scripts/cleanup_tsv.py --fix --backup     # バックアップを作成して修正
"""

import re
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd


def is_valid_date(date_str: str) -> bool:
    """
    日付が有効なYYYY-MM-DD形式かチェック
    """
    if not date_str or pd.isna(date_str):
        return True  # 空は許容（last_appearedなど）
    
    if not isinstance(date_str, str):
        return False
    
    # YYYY-MM-DD形式をチェック
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return False
    
    # 実際に有効な日付かチェック
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def is_valid_year(date_str: str) -> bool:
    """
    日付の年が妥当な範囲（2010-2030）かチェック
    """
    if not date_str or pd.isna(date_str):
        return True
    
    if not isinstance(date_str, str):
        return False
    
    match = re.match(r'^(\d{4})-', date_str)
    if match:
        year = int(match.group(1))
        return 2010 <= year <= 2030
    
    return False


def detect_issues(df: pd.DataFrame) -> list:
    """
    データの問題を検出する
    
    Returns:
        問題のリスト [(index, column, value, issue_type), ...]
    """
    issues = []
    
    for idx, row in df.iterrows():
        # 1. first_appeared の検証
        first_appeared = str(row.get('first_appeared', ''))
        if first_appeared and first_appeared != 'nan':
            if not is_valid_date(first_appeared):
                issues.append((idx, 'first_appeared', first_appeared, 'invalid_date_format'))
            elif not is_valid_year(first_appeared):
                issues.append((idx, 'first_appeared', first_appeared, 'invalid_year'))
        
        # 2. last_appeared の検証
        last_appeared = str(row.get('last_appeared', ''))
        if last_appeared and last_appeared != 'nan' and last_appeared != '':
            if not is_valid_date(last_appeared):
                issues.append((idx, 'last_appeared', last_appeared, 'invalid_date_format'))
            elif not is_valid_year(last_appeared):
                issues.append((idx, 'last_appeared', last_appeared, 'invalid_year'))
        
        # 3. publication_date の検証（current.tsvの場合）
        pub_date = str(row.get('publication_date', ''))
        if pub_date and pub_date != 'nan':
            if not is_valid_date(pub_date):
                issues.append((idx, 'publication_date', pub_date, 'invalid_date_format'))
            elif not is_valid_year(pub_date):
                issues.append((idx, 'publication_date', pub_date, 'invalid_year'))
        
        # 4. company_name が空
        company_name = str(row.get('company_name', ''))
        if not company_name or company_name == 'nan' or len(company_name.strip()) < 2:
            issues.append((idx, 'company_name', company_name, 'empty_or_invalid'))
        
        # 5. status の検証
        status = str(row.get('status', ''))
        if status and status != 'nan' and status not in ['active', 'removed', '']:
            issues.append((idx, 'status', status, 'invalid_status'))
    
    return issues


def try_fix_date(date_str: str, original_date_str: str = None) -> str:
    """
    不正な日付の修正を試みる
    
    Args:
        date_str: 修正対象の日付文字列
        original_date_str: 元の和暦日付（あれば）
    
    Returns:
        修正された日付、または空文字列
    """
    if not date_str or pd.isna(date_str):
        return ""
    
    date_str = str(date_str).strip()
    
    # すでに有効な形式
    if is_valid_date(date_str) and is_valid_year(date_str):
        return date_str
    
    # 1. Excelシリアル値（5桁の数字）の変換
    if re.match(r'^\d{5}$', date_str):
        try:
            serial = int(date_str)
            # Excelの基準日: 1899-12-30
            from datetime import timedelta
            base_date = datetime(1899, 12, 30)
            result_date = base_date + timedelta(days=serial)
            if 2010 <= result_date.year <= 2030:
                return result_date.strftime('%Y-%m-%d')
        except:
            pass
    
    # 2. 和暦パターンを探して変換を試みる
    # スペースや余分な文字を除去してからパターンマッチ
    # H29.3. 9 → H29.3.9
    # 市町R4.2.21 → R4.2.21
    # ー R4.7.6 → R4.7.6
    # 町 R5.10.19 → R5.10.19
    
    # 余分な文字を除去して和暦パターンを抽出
    cleaned = re.sub(r'\s+', '', date_str)  # スペース除去
    wareki_match = re.search(r'[HR](\d+)\.(\d+)\.(\d+)', cleaned)
    
    if wareki_match:
        era = cleaned[wareki_match.start()]
        year = int(wareki_match.group(1))
        month = int(wareki_match.group(2))
        day = int(wareki_match.group(3))
        
        if era == 'H':
            western_year = year + 1988
        else:  # R
            western_year = year + 2018
        
        if 2010 <= western_year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
            try:
                # 実際に有効な日付か確認
                datetime(western_year, month, day)
                return f"{western_year}-{month:02d}-{day:02d}"
            except ValueError:
                pass
    
    # 3. YYYY-MM-DD形式だが年が不正な場合
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        year = int(match.group(1))
        # 明らかに不正な年は削除
        if year < 2010 or year > 2030:
            return ""
    
    return ""


def fix_issues(df: pd.DataFrame, issues: list) -> pd.DataFrame:
    """
    検出された問題を修正する
    """
    df = df.copy()
    rows_to_drop = set()
    
    for idx, column, value, issue_type in issues:
        if issue_type in ['invalid_date_format', 'invalid_year']:
            # 日付の修正を試みる
            original = df.at[idx, f'{column}_original'] if f'{column}_original' in df.columns else None
            fixed = try_fix_date(value, original)
            
            if fixed:
                print(f"  修正: 行{idx} {column}: '{value}' → '{fixed}'")
                df.at[idx, column] = fixed
            else:
                print(f"  削除対象: 行{idx} {column}: '{value}' (修正不可)")
                rows_to_drop.add(idx)
        
        elif issue_type == 'empty_or_invalid':
            print(f"  削除対象: 行{idx} company_name が空または無効")
            rows_to_drop.add(idx)
        
        elif issue_type == 'invalid_status':
            print(f"  修正: 行{idx} status: '{value}' → 'active'")
            df.at[idx, 'status'] = 'active'
    
    # 問題のある行を削除
    if rows_to_drop:
        print(f"\n  {len(rows_to_drop)} 行を削除します")
        df = df.drop(index=list(rows_to_drop))
        df = df.reset_index(drop=True)
    
    return df


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='appearances.tsv のデータをクリーンアップする',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('input', nargs='?', default='timeline/appearances.tsv',
                        help='入力TSVファイル（デフォルト: timeline/appearances.tsv）')
    parser.add_argument('--fix', action='store_true',
                        help='問題を修正する（指定しない場合は検出のみ）')
    parser.add_argument('--backup', action='store_true',
                        help='修正前にバックアップを作成')
    parser.add_argument('-o', '--output',
                        help='出力ファイル（省略時は入力ファイルを上書き）')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"エラー: ファイルが見つかりません: {input_path}")
        sys.exit(1)
    
    print(f"ファイル: {input_path}")
    print()
    
    # データ読み込み
    df = pd.read_csv(input_path, sep='\t', dtype=str).fillna("")
    print(f"総レコード数: {len(df)}")
    print()
    
    # 問題検出
    issues = detect_issues(df)
    
    if not issues:
        print("問題は検出されませんでした。")
        return
    
    print(f"検出された問題: {len(issues)} 件")
    print("-" * 60)
    
    # 問題をタイプ別に集計
    by_type = {}
    for idx, column, value, issue_type in issues:
        key = f"{column}:{issue_type}"
        if key not in by_type:
            by_type[key] = []
        by_type[key].append((idx, value))
    
    for key, items in by_type.items():
        print(f"\n{key}: {len(items)} 件")
        for idx, value in items[:5]:  # 最初の5件を表示
            print(f"  行{idx}: '{value}'")
        if len(items) > 5:
            print(f"  ... 他 {len(items) - 5} 件")
    
    print()
    
    if not args.fix:
        print("修正するには --fix オプションを指定してください")
        return
    
    # バックアップ
    if args.backup:
        from datetime import datetime
        backup_path = input_path.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.tsv')
        df.to_csv(backup_path, sep='\t', index=False)
        print(f"バックアップ作成: {backup_path}")
    
    print()
    print("修正中...")
    print("-" * 60)
    
    # 修正実行
    df_fixed = fix_issues(df, issues)
    
    # 保存
    output_path = Path(args.output) if args.output else input_path
    df_fixed.to_csv(output_path, sep='\t', index=False)
    
    print()
    print(f"保存完了: {output_path}")
    print(f"修正後のレコード数: {len(df_fixed)}")
    
    # 再検証
    remaining_issues = detect_issues(df_fixed)
    if remaining_issues:
        print(f"\n警告: まだ {len(remaining_issues)} 件の問題が残っています")
    else:
        print("\nすべての問題が解決されました。")


if __name__ == "__main__":
    main()
