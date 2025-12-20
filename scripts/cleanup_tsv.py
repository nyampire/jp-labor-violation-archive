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
        # ===========================================
        # 1. 日付フィールドの検証
        # ===========================================
        
        # first_appeared
        first_appeared = str(row.get('first_appeared', ''))
        if first_appeared and first_appeared != 'nan':
            if not is_valid_date(first_appeared):
                issues.append((idx, 'first_appeared', first_appeared, 'invalid_date_format'))
            elif not is_valid_year(first_appeared):
                issues.append((idx, 'first_appeared', first_appeared, 'invalid_year'))
        
        # last_appeared
        last_appeared = str(row.get('last_appeared', ''))
        if last_appeared and last_appeared != 'nan' and last_appeared != '':
            if not is_valid_date(last_appeared):
                issues.append((idx, 'last_appeared', last_appeared, 'invalid_date_format'))
            elif not is_valid_year(last_appeared):
                issues.append((idx, 'last_appeared', last_appeared, 'invalid_year'))
        
        # publication_date（current.tsvの場合）
        pub_date = str(row.get('publication_date', ''))
        if pub_date and pub_date != 'nan':
            if not is_valid_date(pub_date):
                issues.append((idx, 'publication_date', pub_date, 'invalid_date_format'))
            elif not is_valid_year(pub_date):
                issues.append((idx, 'publication_date', pub_date, 'invalid_year'))
        
        # prosecution_date
        pros_date = str(row.get('prosecution_date', ''))
        if pros_date and pros_date != 'nan' and pros_date != '':
            if not is_valid_date(pros_date):
                issues.append((idx, 'prosecution_date', pros_date, 'invalid_date_format'))
            elif not is_valid_year(pros_date):
                issues.append((idx, 'prosecution_date', pros_date, 'invalid_year'))
        
        # ===========================================
        # 2. 日付の整合性チェック
        # ===========================================
        
        # last_appearedが空でない場合のみ順序をチェック
        # （空の場合はアクティブなレコードなので正常）
        if is_valid_date(first_appeared) and last_appeared and last_appeared != '' and is_valid_date(last_appeared):
            if first_appeared > last_appeared:
                issues.append((idx, 'first_appeared/last_appeared', 
                              f'{first_appeared} > {last_appeared}', 'date_order_invalid'))
        
        # ===========================================
        # 3. 企業名の検証
        # ===========================================
        
        company_name = str(row.get('company_name', ''))
        
        # 空または短すぎる
        if not company_name or company_name == 'nan' or len(company_name.strip()) < 2:
            issues.append((idx, 'company_name', company_name, 'empty_or_too_short'))
        else:
            # 法律名が混入している
            if re.search(r'^(労働安全衛生法|労働基準法|最低賃金法|労働者派遣法)', company_name):
                issues.append((idx, 'company_name', company_name[:50], 'contains_law_name'))
            
            # 日付が混入している
            if re.search(r'[HR]\d+\.\d+\.\d+', company_name):
                issues.append((idx, 'company_name', company_name[:50], 'contains_date'))
            
            # 異常に長い（100文字以上）
            if len(company_name) > 100:
                issues.append((idx, 'company_name', company_name[:50] + '...', 'too_long'))
            
            # 数字のみ
            if re.match(r'^\d+$', company_name.strip()):
                issues.append((idx, 'company_name', company_name, 'numeric_only'))
        
        # ===========================================
        # 4. 所在地の検証
        # ===========================================
        
        location = str(row.get('location', ''))
        
        if location and location != 'nan':
            # 都道府県名が含まれているかチェック
            prefectures = r'(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県)'
            
            if not re.search(prefectures, location):
                # 都道府県名がない場合は警告（エラーではない）
                if len(location) > 2 and not re.match(r'^[\d\s\-]+$', location):
                    issues.append((idx, 'location', location[:50], 'no_prefecture'))
            
            # 法律名が混入している
            if re.search(r'(労働安全衛生法|労働基準法|最低賃金法)', location):
                issues.append((idx, 'location', location[:50], 'contains_law_name'))
            
            # 異常に長い
            if len(location) > 50:
                issues.append((idx, 'location', location[:50] + '...', 'too_long'))
            
            # 文字化けの可能性（カタカナとひらがなと漢字が混在して意味不明）
            # ただし、スペースが混入しているだけの場合は別扱い
            if re.search(r'[ァ-ヶ].*[ァ-ヶ].*[ァ-ヶ]', location) and len(location) > 10:
                # 3つ以上のカタカナが散在している場合は文字化けの可能性
                # ただし、都道府県名を含んでいれば軽微な問題として扱う
                if re.search(prefectures, location):
                    # スペースが含まれている場合は軽微な問題
                    if ' ' in location or '　' in location:
                        issues.append((idx, 'location', location[:50], 'contains_space'))
                else:
                    # 都道府県名もなく、カタカナが散在している場合は重大な文字化け
                    issues.append((idx, 'location', location[:50], 'corrupted'))
            elif ' ' in location or '　' in location:
                # スペースが含まれている（軽微な問題）
                issues.append((idx, 'location', location[:50], 'contains_space'))
        
        # ===========================================
        # 5. 労働局の検証
        # ===========================================
        
        labor_bureau = str(row.get('labor_bureau', ''))
        
        if labor_bureau and labor_bureau != 'nan':
            if not labor_bureau.endswith('労働局'):
                issues.append((idx, 'labor_bureau', labor_bureau, 'invalid_format'))
            
            # 既知の労働局リスト
            valid_bureaus = [
                '北海道労働局', '青森労働局', '岩手労働局', '宮城労働局', '秋田労働局',
                '山形労働局', '福島労働局', '茨城労働局', '栃木労働局', '群馬労働局',
                '埼玉労働局', '千葉労働局', '東京労働局', '神奈川労働局', '新潟労働局',
                '富山労働局', '石川労働局', '福井労働局', '山梨労働局', '長野労働局',
                '岐阜労働局', '静岡労働局', '愛知労働局', '三重労働局', '滋賀労働局',
                '京都労働局', '大阪労働局', '兵庫労働局', '奈良労働局', '和歌山労働局',
                '鳥取労働局', '島根労働局', '岡山労働局', '広島労働局', '山口労働局',
                '徳島労働局', '香川労働局', '愛媛労働局', '高知労働局', '福岡労働局',
                '佐賀労働局', '長崎労働局', '熊本労働局', '大分労働局', '宮崎労働局',
                '鹿児島労働局', '沖縄労働局'
            ]
            if labor_bureau not in valid_bureaus and labor_bureau.endswith('労働局'):
                issues.append((idx, 'labor_bureau', labor_bureau, 'unknown_bureau'))
        else:
            issues.append((idx, 'labor_bureau', labor_bureau, 'empty'))
        
        # ===========================================
        # 6. 違反法条の検証
        # ===========================================
        
        violation_law = str(row.get('violation_law', ''))
        
        if violation_law and violation_law != 'nan':
            # 法律名が含まれているかチェック
            law_patterns = r'(労働安全衛生法|労働基準法|最低賃金法|労働者派遣法|じん肺法|作業環境測定法)'
            if not re.search(law_patterns, violation_law):
                # 規則名のみの場合もある
                rule_patterns = r'(規則|施行令|安全規則)'
                if not re.search(rule_patterns, violation_law):
                    issues.append((idx, 'violation_law', violation_law[:50], 'no_law_name'))
            
            # 企業名が混入している可能性
            if re.search(r'(株式会社|（株）|（有）|合同会社|有限会社)', violation_law):
                issues.append((idx, 'violation_law', violation_law[:50], 'contains_company_name'))
        
        # ===========================================
        # 7. status の検証
        # ===========================================
        
        status = str(row.get('status', ''))
        if status and status != 'nan' and status not in ['active', 'removed', '']:
            issues.append((idx, 'status', status, 'invalid_status'))
        
        # ===========================================
        # 8. duration_days の検証
        # ===========================================
        
        duration = str(row.get('duration_days', ''))
        if duration and duration != 'nan' and duration != '':
            try:
                d = int(float(duration))
                if d < 0:
                    issues.append((idx, 'duration_days', duration, 'negative_value'))
                elif d > 3650:  # 10年以上
                    issues.append((idx, 'duration_days', duration, 'too_large'))
            except ValueError:
                issues.append((idx, 'duration_days', duration, 'not_numeric'))
        
        # ===========================================
        # 9. 参考事項の検証
        # ===========================================
        
        reference = str(row.get('reference', ''))
        if reference and reference != 'nan':
            # 送検日が含まれているか
            if '送検' in reference:
                # 日付パターンがあるか
                if not re.search(r'[HR]\d+\.\d+\.\d+', reference):
                    issues.append((idx, 'reference', reference[:50], 'no_date_in_reference'))
    
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
    fixed_count = 0
    
    # 既知の文字化けパターンと正しい文字列のマッピング
    KNOWN_CORRUPTED_PATTERNS = {
        '中愛部知エ県リ愛ア西セ市ンタ': '愛知県愛西市中部エリアセンタ',
        # 他のパターンが見つかったら追加
    }
    
    for idx, column, value, issue_type in issues:
        # 日付の修正
        if issue_type in ['invalid_date_format', 'invalid_year']:
            original = df.at[idx, f'{column}_original'] if f'{column}_original' in df.columns else None
            fixed = try_fix_date(value, original)
            
            if fixed:
                print(f"  修正: 行{idx} {column}: '{value}' → '{fixed}'")
                df.at[idx, column] = fixed
                fixed_count += 1
            else:
                print(f"  削除対象: 行{idx} {column}: '{value}' (修正不可)")
                rows_to_drop.add(idx)
        
        # 日付の順序が不正
        elif issue_type == 'date_order_invalid':
            print(f"  削除対象: 行{idx} 日付順序が不正: {value}")
            rows_to_drop.add(idx)
        
        # 企業名が空または短すぎる
        elif issue_type == 'empty_or_too_short':
            print(f"  削除対象: 行{idx} company_name が空または短すぎる")
            rows_to_drop.add(idx)
        
        # 企業名に法律名が混入
        elif issue_type == 'contains_law_name' and column == 'company_name':
            print(f"  削除対象: 行{idx} company_name に法律名が混入: '{value}'")
            rows_to_drop.add(idx)
        
        # 企業名に日付が混入
        elif issue_type == 'contains_date' and column == 'company_name':
            print(f"  削除対象: 行{idx} company_name に日付が混入: '{value}'")
            rows_to_drop.add(idx)
        
        # 数字のみの企業名
        elif issue_type == 'numeric_only':
            print(f"  削除対象: 行{idx} company_name が数字のみ: '{value}'")
            rows_to_drop.add(idx)
        
        # statusの修正
        elif issue_type == 'invalid_status':
            print(f"  修正: 行{idx} status: '{value}' → 'active'")
            df.at[idx, 'status'] = 'active'
            fixed_count += 1
        
        # 労働局が空
        elif issue_type == 'empty' and column == 'labor_bureau':
            print(f"  削除対象: 行{idx} labor_bureau が空")
            rows_to_drop.add(idx)
        
        # duration_daysの修正
        elif issue_type == 'negative_value':
            print(f"  修正: 行{idx} duration_days: '{value}' → ''")
            df.at[idx, 'duration_days'] = ''
            fixed_count += 1
        
        elif issue_type == 'not_numeric' and column == 'duration_days':
            print(f"  修正: 行{idx} duration_days: '{value}' → ''")
            df.at[idx, 'duration_days'] = ''
            fixed_count += 1
        
        # violation_lawに企業名が混入
        elif issue_type == 'contains_company_name' and column == 'violation_law':
            print(f"  警告: 行{idx} violation_law に企業名らしき文字列: '{value}'")
            # 自動修正は難しいので警告のみ
        
        # 所在地にスペースが混入（自動修正）
        elif issue_type == 'contains_space' and column == 'location':
            original = df.at[idx, 'location']
            fixed = re.sub(r'[\s　]+', '', str(original))  # 全角・半角スペースを除去
            print(f"  修正: 行{idx} location: '{original}' → '{fixed}'")
            df.at[idx, 'location'] = fixed
            fixed_count += 1
        
        # 所在地の重大な文字化け（既知のパターンは修正、それ以外は保持）
        elif issue_type == 'corrupted' and column == 'location':
            original = str(df.at[idx, 'location'])
            if original in KNOWN_CORRUPTED_PATTERNS:
                fixed = KNOWN_CORRUPTED_PATTERNS[original]
                print(f"  修正: 行{idx} location: '{original}' → '{fixed}'")
                df.at[idx, 'location'] = fixed
                fixed_count += 1
            else:
                print(f"  警告: 行{idx} location が文字化けの可能性（そのまま保持）: '{value}'")
    
    # 問題のある行を削除
    if rows_to_drop:
        print(f"\n  {len(rows_to_drop)} 行を削除します")
        df = df.drop(index=list(rows_to_drop))
        df = df.reset_index(drop=True)
    
    print(f"\n  修正: {fixed_count} 件, 削除: {len(rows_to_drop)} 件")
    
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
    parser.add_argument('--warnings', action='store_true',
                        help='警告も表示する（デフォルトはエラーのみ）')
    parser.add_argument('--all', action='store_true',
                        help='全ての問題を詳細表示する')
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
    
    # 問題を重大度で分類
    SEVERITY = {
        # エラー（修正が必要）
        'invalid_date_format': 'ERROR',
        'invalid_year': 'ERROR',
        'date_order_invalid': 'ERROR',
        'empty_or_too_short': 'ERROR',
        'contains_law_name': 'ERROR',
        'contains_date': 'ERROR',
        'numeric_only': 'ERROR',
        'invalid_status': 'ERROR',
        'negative_value': 'ERROR',
        'not_numeric': 'ERROR',
        'empty': 'ERROR',
        'contains_company_name': 'ERROR',
        
        # 警告（確認推奨）
        'too_long': 'WARN',
        'no_prefecture': 'WARN',
        'invalid_format': 'WARN',
        'unknown_bureau': 'WARN',
        'no_law_name': 'WARN',
        'too_large': 'WARN',
        'no_date_in_reference': 'WARN',
        'contains_space': 'ERROR',  # スペース混入は自動修正可能
        'corrupted': 'WARN',  # 文字化けは警告のみ（データ保持）
    }
    
    errors = [(i, c, v, t) for i, c, v, t in issues if SEVERITY.get(t, 'ERROR') == 'ERROR']
    warnings = [(i, c, v, t) for i, c, v, t in issues if SEVERITY.get(t, 'ERROR') == 'WARN']
    
    print(f"検出された問題: {len(issues)} 件")
    print(f"  - エラー: {len(errors)} 件")
    print(f"  - 警告: {len(warnings)} 件")
    print("-" * 60)
    
    # 問題をタイプ別に集計
    by_type = {}
    for idx, column, value, issue_type in issues:
        key = f"{column}:{issue_type}"
        if key not in by_type:
            by_type[key] = []
        by_type[key].append((idx, value))
    
    # エラーを表示
    print("\n【エラー】（修正が必要）")
    error_types = {k: v for k, v in by_type.items() if SEVERITY.get(k.split(':')[1], 'ERROR') == 'ERROR'}
    if error_types:
        for key, items in sorted(error_types.items()):
            print(f"\n  {key}: {len(items)} 件")
            display_count = len(items) if args.all else min(5, len(items))
            for idx, value in items[:display_count]:
                print(f"    行{idx}: '{value}'")
            if len(items) > display_count:
                print(f"    ... 他 {len(items) - display_count} 件")
    else:
        print("  なし")
    
    # 警告を表示（--warnings または --all の場合）
    if args.warnings or args.all:
        print("\n【警告】（確認推奨）")
        warn_types = {k: v for k, v in by_type.items() if SEVERITY.get(k.split(':')[1], 'ERROR') == 'WARN'}
        if warn_types:
            for key, items in sorted(warn_types.items()):
                print(f"\n  {key}: {len(items)} 件")
                display_count = len(items) if args.all else min(3, len(items))
                for idx, value in items[:display_count]:
                    print(f"    行{idx}: '{value}'")
                if len(items) > display_count:
                    print(f"    ... 他 {len(items) - display_count} 件")
        else:
            print("  なし")
    
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
