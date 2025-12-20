#!/usr/bin/env python3
"""
fetch_pdf.py - 各ソースからPDFを取得するスクリプト

以下のソースからPDFを取得します：

1. 厚労省（最新）: https://www.mhlw.go.jp/kinkyu/151106.html
2. Wayback Machine: 2017年5月〜2018年7月のアーカイブ
3. H-CRISIS: 2020年以降のアーカイブ

使用例:
    # 厚労省の最新PDFを取得
    python fetch_pdf.py --source latest
    
    # Wayback Machineから過去PDFを取得
    python fetch_pdf.py --source wayback
    
    # H-CRISISから取得
    python fetch_pdf.py --source hcrisis
    
    # すべてのソースから取得
    python fetch_pdf.py --source all

保存先:
    archive/pdf/YYYY/YYYY-MM-DD_filename.pdf
"""

import re
import csv
import hashlib
import sys
from pathlib import Path
from datetime import date
import urllib.request
import urllib.error


# =============================================================================
# 設定
# =============================================================================

# 厚労省のメインページURL
MHLW_PAGE_URL = "https://www.mhlw.go.jp/kinkyu/151106.html"

# H-CRISIS（国立保健医療科学院）に保存されているPDF
# URLパターン: /wp-content/uploads/YYYY/MM/YYYYMMDDHHMMSS_content_XXXXXXXXX.pdf
# または: /wp-content/uploads/YYYY/MM/XXXXXXXXX.pdf
HCRISIS_PDFS = [
    {
        "url": "https://h-crisis.niph.go.jp/wp-content/uploads/2020/12/20201201121546_content_000534084.pdf",
        "date": "2020-12-01",
        "period": "R1.11.1-R2.10.30"
    },
    {
        "url": "https://h-crisis.niph.go.jp/wp-content/uploads/2021/06/20210601090821_content_000776466.pdf",
        "date": "2021-06-01",
        "period": "R2.5.1-R3.4.30"
    },
    {
        "url": "https://h-crisis.niph.go.jp/wp-content/uploads/2022/07/20220701111119_content_000958620.pdf",
        "date": "2022-07-01",
        "period": "R3.6.1-R4.5.31"
    },
    {
        "url": "https://h-crisis.niph.go.jp/wp-content/uploads/2022/12/20221201110436_content_001018384.pdf",
        "date": "2022-12-01",
        "period": "R3.11.1-R4.10.31"
    },
    {
        "url": "https://h-crisis.niph.go.jp/wp-content/uploads/2023/11/001150620.pdf",
        "date": "2023-11-30",
        "period": "R4.10.1-R5.9.30"
    },
    {
        "url": "https://h-crisis.niph.go.jp/wp-content/uploads/2024/03/001150620.pdf",
        "date": "2024-03-01",
        "period": "R5.2.1-R6.1.31"
    },
    {
        "url": "https://h-crisis.niph.go.jp/wp-content/uploads/2025/04/001150620.pdf",
        "date": "2025-03-31",
        "period": "R6.3.1-R7.2.28"
    },
    {
        "url": "https://h-crisis.niph.go.jp/wp-content/uploads/2025/06/001483075.pdf",
        "date": "2025-05-30",
        "period": "R6.5.1-R7.4.30"
    }
]

# Wayback Machine のアーカイブ（CDX APIで取得した結果）
# 2017年5月〜2018年7月の16バージョン
WAYBACK_PDFS = [
    {"timestamp": "20170510130509", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20170601175704", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20170629074816", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20170803143610", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20170825030103", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20170901051945", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20171007124050", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20171118150048", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20171228054905", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20180131040742", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20180302010953", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20180402212926", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20180507075929", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20180604070156", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20180701014448", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
    {"timestamp": "20180726081611", "original": "http://www.mhlw.go.jp/kinkyu/dl/170510-01.pdf"},
]


# =============================================================================
# ユーティリティ
# =============================================================================

def get_file_hash(filepath: Path) -> str:
    """
    ファイルのSHA256ハッシュを計算する
    
    Args:
        filepath: ファイルパス
    
    Returns:
        SHA256ハッシュ（16進数文字列）
    """
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def download_file(url: str, dest: Path, headers: dict = None) -> bool:
    """
    URLからファイルをダウンロードする
    
    Args:
        url: ダウンロード元URL
        dest: 保存先パス
        headers: HTTPヘッダー（オプション）
    
    Returns:
        成功したらTrue
    """
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (compatible; labor-violation-archive/1.0)')
        
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(dest, 'wb') as f:
                f.write(response.read())
        return True
        
    except urllib.error.HTTPError as e:
        print(f"  HTTPエラー: {e.code} {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"  URLエラー: {e.reason}")
        return False
    except Exception as e:
        print(f"  エラー: {e}")
        return False


def update_metadata(metadata_path: Path, entry: dict):
    """
    メタデータファイル（TSV）にエントリを追記する
    
    Args:
        metadata_path: metadata.tsv のパス
        entry: 追記するエントリ（辞書）
    """
    fieldnames = ["date", "url", "filename", "sha256", "source", "period"]
    
    file_exists = metadata_path.exists()
    
    with open(metadata_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
        
        if not file_exists:
            writer.writeheader()
        
        row = {k: entry.get(k, "") for k in fieldnames}
        writer.writerow(row)


# =============================================================================
# 厚労省（最新）
# =============================================================================

def fetch_latest_pdf(archive_dir: Path, metadata_path: Path) -> dict:
    """
    厚労省のメインページから最新のPDFを取得する
    
    Args:
        archive_dir: 保存先ディレクトリ
        metadata_path: メタデータファイルのパス
    
    Returns:
        結果の辞書
    """
    print("厚労省のページからPDFリンクを取得中...")
    
    try:
        req = urllib.request.Request(MHLW_PAGE_URL)
        req.add_header('User-Agent', 'Mozilla/5.0')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  ページ取得エラー: {e}")
        return {"status": "failed", "error": str(e)}
    
    # PDFリンクを抽出
    # 例: href="/content/001527991.pdf"
    pdf_pattern = r'href="(/content/\d+\.pdf)"'
    match = re.search(pdf_pattern, html)
    
    if not match:
        print("  PDFリンクが見つかりません")
        return {"status": "failed", "error": "PDF link not found"}
    
    pdf_path = match.group(1)
    pdf_url = f"https://www.mhlw.go.jp{pdf_path}"
    
    print(f"  発見: {pdf_url}")
    
    # ファイル名を生成
    today = date.today().isoformat()
    year = today[:4]
    original_filename = Path(pdf_path).name
    filename = f"{today}_{original_filename}"
    
    year_dir = archive_dir / year
    year_dir.mkdir(parents=True, exist_ok=True)
    dest_path = year_dir / filename
    
    # すでに取得済みかチェック
    if dest_path.exists():
        print(f"  すでに取得済み: {dest_path}")
        return {"url": pdf_url, "path": str(dest_path), "status": "exists"}
    
    # ダウンロード
    print(f"  ダウンロード中...")
    if download_file(pdf_url, dest_path):
        file_hash = get_file_hash(dest_path)
        
        update_metadata(metadata_path, {
            "date": today,
            "url": pdf_url,
            "filename": filename,
            "sha256": file_hash,
            "source": "mhlw"
        })
        
        print(f"  保存: {dest_path}")
        return {"url": pdf_url, "path": str(dest_path), "hash": file_hash, "status": "downloaded"}
    
    return {"url": pdf_url, "status": "failed"}


# =============================================================================
# Wayback Machine
# =============================================================================

def fetch_wayback_pdfs(archive_dir: Path, metadata_path: Path) -> list:
    """
    Wayback MachineからPDFを取得する
    
    Args:
        archive_dir: 保存先ディレクトリ
        metadata_path: メタデータファイルのパス
    
    Returns:
        結果のリスト
    """
    results = []
    
    print(f"Wayback Machine から {len(WAYBACK_PDFS)} ファイルを取得...")
    print()
    
    for i, entry in enumerate(WAYBACK_PDFS, 1):
        timestamp = entry["timestamp"]
        original = entry["original"]
        
        # Wayback URL（if_ を付けるとリダイレクトせず直接取得）
        wayback_url = f"https://web.archive.org/web/{timestamp}if_/{original}"
        
        # 日付を抽出
        date_str = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
        year = timestamp[:4]
        
        filename = f"{date_str}_170510-01.pdf"
        year_dir = archive_dir / year
        year_dir.mkdir(parents=True, exist_ok=True)
        dest_path = year_dir / filename
        
        print(f"[{i}/{len(WAYBACK_PDFS)}] {date_str}")
        
        if dest_path.exists():
            print(f"  すでに取得済み")
            results.append({"url": wayback_url, "path": str(dest_path), "status": "exists"})
            continue
        
        print(f"  ダウンロード中...")
        if download_file(wayback_url, dest_path):
            file_hash = get_file_hash(dest_path)
            
            update_metadata(metadata_path, {
                "date": date_str,
                "url": wayback_url,
                "filename": filename,
                "sha256": file_hash,
                "source": "wayback"
            })
            
            print(f"  保存: {dest_path}")
            results.append({"url": wayback_url, "path": str(dest_path), "status": "downloaded"})
        else:
            results.append({"url": wayback_url, "status": "failed"})
        
        print()
    
    return results


# =============================================================================
# H-CRISIS
# =============================================================================

def fetch_hcrisis_pdfs(archive_dir: Path, metadata_path: Path) -> list:
    """
    H-CRISIS（国立保健医療科学院）からPDFを取得する
    
    Args:
        archive_dir: 保存先ディレクトリ
        metadata_path: メタデータファイルのパス
    
    Returns:
        結果のリスト
    """
    results = []
    
    print(f"H-CRISIS から {len(HCRISIS_PDFS)} ファイルを取得...")
    print()
    
    for i, entry in enumerate(HCRISIS_PDFS, 1):
        url = entry["url"]
        date_str = entry["date"]
        period = entry.get("period", "")
        year = date_str[:4]
        
        original_filename = Path(url).name
        filename = f"{date_str}_{original_filename}"
        year_dir = archive_dir / year
        year_dir.mkdir(parents=True, exist_ok=True)
        dest_path = year_dir / filename
        
        print(f"[{i}/{len(HCRISIS_PDFS)}] {date_str} ({period})")
        
        if dest_path.exists():
            print(f"  すでに取得済み")
            results.append({"url": url, "path": str(dest_path), "status": "exists"})
            continue
        
        print(f"  ダウンロード中...")
        if download_file(url, dest_path):
            file_hash = get_file_hash(dest_path)
            
            update_metadata(metadata_path, {
                "date": date_str,
                "url": url,
                "filename": filename,
                "sha256": file_hash,
                "source": "hcrisis",
                "period": period
            })
            
            print(f"  保存: {dest_path}")
            results.append({"url": url, "path": str(dest_path), "status": "downloaded"})
        else:
            results.append({"url": url, "status": "failed"})
        
        print()
    
    return results


# =============================================================================
# メイン処理
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='各ソースからPDFを取得する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ソース:
  latest   厚労省の最新PDF
  wayback  Wayback Machine（2017年5月〜2018年7月）
  hcrisis  H-CRISIS（2020年以降）
  all      すべてのソース

使用例:
  %(prog)s --source latest     # 最新のみ
  %(prog)s --source wayback    # 過去PDFのみ
  %(prog)s --source all        # すべて取得
        """
    )
    parser.add_argument('--archive-dir', default='archive/pdf',
                        help='保存先ディレクトリ（デフォルト: archive/pdf）')
    parser.add_argument('--metadata', default='archive/metadata.tsv',
                        help='メタデータファイル（デフォルト: archive/metadata.tsv）')
    parser.add_argument('--source', choices=['latest', 'wayback', 'hcrisis', 'all'],
                        default='latest', help='取得元（デフォルト: latest）')
    
    args = parser.parse_args()
    
    archive_dir = Path(args.archive_dir)
    metadata_path = Path(args.metadata)
    
    archive_dir.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("労働基準関係法令違反 公表事案 PDF取得")
    print("=" * 60)
    print()
    
    # 厚労省（最新）
    if args.source in ['latest', 'all']:
        print("【厚労省 - 最新PDF】")
        print("-" * 40)
        result = fetch_latest_pdf(archive_dir, metadata_path)
        print()
    
    # Wayback Machine
    if args.source in ['wayback', 'all']:
        print("【Wayback Machine - 2017〜2018年】")
        print("-" * 40)
        results = fetch_wayback_pdfs(archive_dir, metadata_path)
        success = len([r for r in results if r['status'] != 'failed'])
        print(f"結果: {success}/{len(results)} 成功")
        print()
    
    # H-CRISIS
    if args.source in ['hcrisis', 'all']:
        print("【H-CRISIS - 2020年以降】")
        print("-" * 40)
        results = fetch_hcrisis_pdfs(archive_dir, metadata_path)
        success = len([r for r in results if r['status'] != 'failed'])
        print(f"結果: {success}/{len(results)} 成功")
        print()
    
    print("=" * 60)
    print("完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
