#!/usr/bin/env python3
"""
extract_companies.py - PDFから企業リストを抽出するスクリプト

厚生労働省「労働基準関係法令違反に係る公表事案」PDFを解析し、
TSV形式の企業リストを出力します。

使用例:
    # PDFから抽出
    python extract_companies.py input.pdf -o output.tsv
    
    # テキストファイルから抽出（デバッグ用）
    python extract_companies.py input.txt --text -o output.tsv

出力カラム:
    - labor_bureau: 労働局名（例: 北海道労働局）
    - company_name: 企業・事業場名称
    - location: 所在地
    - publication_date: 公表日（西暦 YYYY-MM-DD形式）
    - publication_date_original: 公表日（原本表記）
    - violation_law: 違反法条
    - violation_summary: 事案概要
    - reference: 参考事項
    - prosecution_date: 送検日（西暦 YYYY-MM-DD形式）
"""

import re
import sys
from pathlib import Path
import pandas as pd

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


# =============================================================================
# 日付変換
# =============================================================================

def normalize_date(date_str: str) -> str:
    """
    和暦日付を西暦に変換する
    
    Args:
        date_str: 和暦日付文字列（例: "R6.5.21", "H30.12.1"）
    
    Returns:
        西暦日付文字列（例: "2024-05-21"）
    
    Examples:
        >>> normalize_date("R6.5.21")
        '2024-05-21'
        >>> normalize_date("H30.12.1")
        '2018-12-01'
    """
    if not date_str:
        return ""
    
    # 令和（R）: 令和1年 = 2019年
    match = re.match(r'R(\d+)\.(\d+)\.(\d+)', date_str)
    if match:
        year = int(match.group(1)) + 2018
        month = int(match.group(2))
        day = int(match.group(3))
        return f"{year}-{month:02d}-{day:02d}"
    
    # 平成（H）: 平成1年 = 1989年
    match = re.match(r'H(\d+)\.(\d+)\.(\d+)', date_str)
    if match:
        year = int(match.group(1)) + 1988
        month = int(match.group(2))
        day = int(match.group(3))
        return f"{year}-{month:02d}-{day:02d}"
    
    # すでに西暦の場合（2024/5/21 or 2024-5-21）
    match = re.match(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', date_str)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    
    return date_str


def extract_prosecution_date(reference: str) -> str:
    """
    参考事項から送検日を抽出する
    
    Args:
        reference: 参考事項文字列（例: "R7.1.15送検"）
    
    Returns:
        送検日（西暦 YYYY-MM-DD形式）
    
    Examples:
        >>> extract_prosecution_date("R7.1.15送検")
        '2025-01-15'
        >>> extract_prosecution_date("H30.6.5公表")
        ''
    """
    if not reference:
        return ""
    
    # 「R7.1.15送検」のようなパターンを検出
    match = re.search(r'([RH]\d+\.\d+\.\d+)送検', reference)
    if match:
        return normalize_date(match.group(1))
    
    return ""


# =============================================================================
# PDF抽出
# =============================================================================

def extract_from_pdf(pdf_path: Path) -> pd.DataFrame:
    """
    PDFファイルから企業リストを抽出する
    
    Args:
        pdf_path: PDFファイルのパス
    
    Returns:
        企業リストのDataFrame
    """
    if not HAS_PDFPLUMBER:
        print("エラー: pdfplumber が必要です")
        print("インストール: pip install pdfplumber")
        sys.exit(1)
    
    records = []
    current_bureau = None
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # テーブル抽出を試みる
            tables = page.extract_tables()
            
            if tables and len(tables) > 0:
                # テーブルが取得できた場合
                for table in tables:
                    if not table:
                        continue
                    
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        
                        # セルをクリーンアップ（改行を除去）
                        cells = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
                        first_cell = cells[0] if cells else ""
                        
                        # 労働局ヘッダーの検出
                        # 例: "労働基準関係法令違反に係る公表事案\n北海道労働局 最終更新日：..."
                        if '労働局' in first_cell:
                            match = re.search(r'([^\s]+労働局)', first_cell)
                            if match:
                                current_bureau = match.group(1).strip()
                            continue
                        
                        # ヘッダー行をスキップ
                        if '企業・事業場名称' in first_cell or first_cell == '所在地':
                            continue
                        
                        # データ行の解析（6列ある場合）
                        if len(cells) >= 6 and current_bureau:
                            record = parse_table_row(cells, current_bureau)
                            if record:
                                records.append(record)
            else:
                # テーブルがない場合はテキストから抽出
                text = page.extract_text()
                if text:
                    page_records = extract_from_page_text(text, current_bureau)
                    if page_records:
                        records.extend(page_records)
                        # 最後のレコードの労働局を次のページに引き継ぐ
                        if page_records:
                            current_bureau = page_records[-1].get("labor_bureau", current_bureau)
    
    return pd.DataFrame(records)


def parse_table_row(cells: list, labor_bureau: str) -> dict:
    """
    テーブルの行をパースしてレコードを作成する
    
    Args:
        cells: セルのリスト [企業名, 所在地, 公表日, 違反法条, 事案概要, 参考事項]
        labor_bureau: 労働局名
    
    Returns:
        パースされたレコード（辞書）、無効な場合はNone
    """
    company_name = cells[0].strip()
    location = cells[1].strip() if len(cells) > 1 else ""
    pub_date_original = cells[2].strip() if len(cells) > 2 else ""
    violation_law = cells[3].strip() if len(cells) > 3 else ""
    violation_summary = cells[4].strip() if len(cells) > 4 else ""
    reference = cells[5].strip() if len(cells) > 5 else ""
    
    # 空行または無効な行をスキップ
    if not company_name or company_name in ["", "-", "－"]:
        return None
    
    # ヘッダー行をスキップ
    if "企業・事業場" in company_name or company_name == "所在地":
        return None
    
    pub_date = normalize_date(pub_date_original)
    prosecution_date = extract_prosecution_date(reference)
    
    return {
        "labor_bureau": labor_bureau,
        "company_name": company_name,
        "location": location,
        "publication_date": pub_date,
        "publication_date_original": pub_date_original,
        "violation_law": violation_law,
        "violation_summary": violation_summary,
        "reference": reference,
        "prosecution_date": prosecution_date
    }


def extract_from_page_text(text: str, initial_bureau: str = None) -> list:
    """
    ページのテキストから企業リストを抽出する
    
    厚労省PDFは以下のような形式:
    - 日付（H28.10.4等）を含む行に企業名、所在地、送検日が入っている
    - その前後の行に違反法条や事案概要が分散している
    
    Args:
        text: ページのテキスト
        initial_bureau: 初期労働局名
    
    Returns:
        レコードのリスト
    """
    records = []
    current_bureau = initial_bureau
    lines = text.split('\n')
    
    # まず労働局を特定
    for line in lines:
        if '労働局' in line and '最終更新日' in line:
            match = re.match(r'^(.+労働局)', line)
            if match:
                current_bureau = match.group(1).strip()
                break
    
    if not current_bureau:
        return records
    
    # 日付パターン（公表日）
    date_pattern = r'[HR]\d+\.\d+\.\d+'
    
    # 日付を含む行のインデックスを収集
    date_line_indices = []
    for i, line in enumerate(lines):
        if re.search(date_pattern, line):
            # ヘッダー行は除外
            if '企業・事業場名称' not in line and '最終更新日' not in line:
                date_line_indices.append(i)
    
    # 各日付行を処理
    for idx, line_idx in enumerate(date_line_indices):
        line = lines[line_idx]
        
        # 日付を抽出
        dates = re.findall(date_pattern, line)
        if not dates:
            continue
        
        pub_date_original = dates[0]
        reference = f"{dates[-1]}送検" if '送検' in line else ""
        
        # 企業名と所在地を抽出（日付より前の部分）
        first_date_pos = line.find(pub_date_original)
        before_date = line[:first_date_pos].strip()
        
        # 前の行から追加情報を取得（企業名が途中で切れている場合）
        prev_lines_text = ""
        if line_idx > 0:
            # 前の行を確認（日付を含まない行のみ）
            for prev_idx in range(line_idx - 1, max(line_idx - 3, -1), -1):
                prev_line = lines[prev_idx].strip()
                if not re.search(date_pattern, prev_line) and '労働局' not in prev_line and '企業・事業場名称' not in prev_line:
                    # 法律名で始まる行は違反法条なのでスキップ
                    if not prev_line.startswith('労働') and not prev_line.startswith('最低'):
                        prev_lines_text = prev_line + " " + prev_lines_text
        
        full_before_date = (prev_lines_text + " " + before_date).strip()
        
        # 都道府県パターンで所在地を検出
        prefecture_pattern = r'(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県)'
        
        location_match = re.search(prefecture_pattern + r'[^\s]*', full_before_date)
        
        if location_match:
            location = location_match.group(0).strip()
            # 所在地の後の余分なテキストを削除（法律名など）
            location = re.split(r'\s+労働', location)[0]
            
            location_start = full_before_date.find(location_match.group(1))
            company_name = full_before_date[:location_start].strip()
        else:
            # 所在地が見つからない場合
            company_name = full_before_date
            location = ""
        
        # 違反法条と事案概要を収集
        # 前後の行から法律名と事案概要を抽出
        violation_parts = []
        summary_parts = []
        
        # 検索範囲：現在の行の前後
        search_start = max(0, line_idx - 2)
        search_end = min(len(lines), line_idx + 3)
        
        # 次の日付行までを検索範囲とする
        if idx + 1 < len(date_line_indices):
            search_end = min(search_end, date_line_indices[idx + 1])
        
        for search_idx in range(search_start, search_end):
            search_line = lines[search_idx].strip()
            
            # 法律名を含む行
            if re.search(r'(労働安全衛生法|労働基準法|最低賃金法|労働者派遣法)', search_line):
                # 日付部分を除去
                clean_line = re.sub(date_pattern + r'送検', '', search_line)
                clean_line = re.sub(date_pattern, '', clean_line).strip()
                if clean_line:
                    violation_parts.append(clean_line)
            
            # 「もの」で終わる行（事案概要の一部）
            if 'もの' in search_line or 'なかった' in search_line:
                clean_line = re.sub(date_pattern + r'送検', '', search_line)
                clean_line = re.sub(date_pattern, '', clean_line).strip()
                if clean_line and clean_line not in violation_parts:
                    summary_parts.append(clean_line)
        
        # 日付行自体からも違反法条と事案概要を抽出
        after_date = line[first_date_pos + len(pub_date_original):].strip()
        after_date = re.sub(date_pattern + r'送検', '', after_date).strip()
        if after_date:
            if re.search(r'(労働安全衛生法|労働基準法|最低賃金法)', after_date):
                violation_parts.append(after_date)
            elif 'もの' in after_date or 'なかった' in after_date:
                summary_parts.append(after_date)
        
        violation_law = ' '.join(violation_parts)
        violation_summary = ' '.join(summary_parts)
        
        # 重複を除去
        violation_law = ' '.join(dict.fromkeys(violation_law.split()))
        
        # 企業名のクリーンアップ
        company_name = company_name.strip()
        company_name = re.sub(r'\s+', ' ', company_name)
        
        # 企業名から法律名を除去
        company_name = re.sub(r'労働安全衛生法.*$', '', company_name).strip()
        company_name = re.sub(r'最低賃金法.*$', '', company_name).strip()
        
        # 無効なレコードをスキップ
        if not company_name or len(company_name) < 2:
            continue
        if '企業・事業場' in company_name or '所在地' in company_name:
            continue
        
        pub_date = normalize_date(pub_date_original)
        prosecution_date = normalize_date(dates[-1]) if dates else ""
        
        records.append({
            "labor_bureau": current_bureau,
            "company_name": company_name,
            "location": location,
            "publication_date": pub_date,
            "publication_date_original": pub_date_original,
            "violation_law": violation_law,
            "violation_summary": violation_summary,
            "reference": reference,
            "prosecution_date": prosecution_date
        })
    
    return records


def parse_text_record(lines: list, start_idx: int, labor_bureau: str) -> dict:
    """
    テキスト行からレコードを解析する（互換性のため残す）
    """
    return None


def parse_data_row(cells: list, labor_bureau: str) -> dict:
    """
    データ行をパースして辞書に変換する
    
    Args:
        cells: セルのリスト
        labor_bureau: 労働局名
    
    Returns:
        パースされたレコード（辞書）、無効な行の場合はNone
    """
    company_name = cells[0].replace("\n", " ").strip()
    location = cells[1].replace("\n", " ").strip()
    pub_date_original = cells[2].replace("\n", "").strip()
    violation_law = cells[3].replace("\n", " ").strip()
    violation_summary = cells[4].replace("\n", " ").strip()
    reference = cells[5].replace("\n", " ").strip() if len(cells) > 5 else ""
    
    # 空行または無効な行をスキップ
    if not company_name or company_name in ["", "-", "－"]:
        return None
    
    pub_date = normalize_date(pub_date_original)
    prosecution_date = extract_prosecution_date(reference)
    
    return {
        "labor_bureau": labor_bureau,
        "company_name": company_name,
        "location": location,
        "publication_date": pub_date,
        "publication_date_original": pub_date_original,
        "violation_law": violation_law,
        "violation_summary": violation_summary,
        "reference": reference,
        "prosecution_date": prosecution_date
    }


# =============================================================================
# テキスト抽出（デバッグ・テスト用）
# =============================================================================

def extract_from_text(text: str) -> pd.DataFrame:
    """
    テキストから企業リストを抽出する（デバッグ用）
    
    PDFから直接テキストをコピーした場合や、
    テスト用にテキストデータを使用する場合に使用します。
    
    Args:
        text: タブ区切りまたはスペース区切りのテキスト
    
    Returns:
        企業リストのDataFrame
    """
    records = []
    current_bureau = None
    
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 労働局ヘッダーの検出
        if line.endswith("労働局") and len(line) < 15:
            current_bureau = line
            continue
        
        # タブ区切りの場合
        if '\t' in line:
            parts = line.split('\t')
        else:
            # 複数スペースで分割
            parts = re.split(r'\s{2,}', line)
        
        if len(parts) >= 5 and current_bureau:
            company_name = parts[0].strip()
            
            # ヘッダー行をスキップ
            if "企業・事業場" in company_name:
                continue
            
            location = parts[1].strip() if len(parts) > 1 else ""
            pub_date_original = parts[2].strip() if len(parts) > 2 else ""
            violation_law = parts[3].strip() if len(parts) > 3 else ""
            violation_summary = parts[4].strip() if len(parts) > 4 else ""
            reference = parts[5].strip() if len(parts) > 5 else ""
            
            pub_date = normalize_date(pub_date_original)
            prosecution_date = extract_prosecution_date(reference)
            
            records.append({
                "labor_bureau": current_bureau,
                "company_name": company_name,
                "location": location,
                "publication_date": pub_date,
                "publication_date_original": pub_date_original,
                "violation_law": violation_law,
                "violation_summary": violation_summary,
                "reference": reference,
                "prosecution_date": prosecution_date
            })
    
    return pd.DataFrame(records)


# =============================================================================
# メイン処理
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='厚労省PDFから企業リストを抽出してTSVに変換',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s input.pdf                    # PDFから抽出、input.tsv に出力
  %(prog)s input.pdf -o output.tsv      # PDFから抽出、output.tsv に出力
  %(prog)s input.txt --text             # テキストから抽出
        """
    )
    parser.add_argument('input', help='入力ファイル（PDFまたはテキスト）')
    parser.add_argument('-o', '--output', help='出力TSVファイル（省略時は入力ファイル名.tsv）')
    parser.add_argument('--text', action='store_true', help='テキストファイルとして処理')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"エラー: ファイルが見つかりません: {input_path}")
        sys.exit(1)
    
    # 抽出処理
    if args.text or input_path.suffix == '.txt':
        with open(input_path, 'r', encoding='utf-8') as f:
            text = f.read()
        df = extract_from_text(text)
    else:
        df = extract_from_pdf(input_path)
    
    # 出力先の決定
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix('.tsv')
    
    # ディレクトリがなければ作成
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # TSV出力
    df.to_csv(output_path, sep='\t', index=False)
    print(f"抽出完了: {len(df)} 件 → {output_path}")


if __name__ == "__main__":
    main()
