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
            tables = page.extract_tables()
            
            for table in tables:
                if not table:
                    continue
                
                for row in table:
                    if not row or len(row) < 2:
                        continue
                    
                    # セルをクリーンアップ
                    cells = [str(c).strip() if c else "" for c in row]
                    first_cell = cells[0] if cells else ""
                    
                    # 労働局ヘッダーの検出
                    # 例: "北海道労働局", "東京労働局"
                    if "労働局" in first_cell and len(first_cell) < 20:
                        current_bureau = first_cell.replace("\n", "")
                        continue
                    
                    # ヘッダー行をスキップ
                    if "企業・事業場名称" in first_cell or "公表日" in first_cell:
                        continue
                    
                    # データ行の解析（6列以上ある場合）
                    if len(cells) >= 6 and current_bureau:
                        record = parse_data_row(cells, current_bureau)
                        if record:
                            records.append(record)
    
    return pd.DataFrame(records)


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
