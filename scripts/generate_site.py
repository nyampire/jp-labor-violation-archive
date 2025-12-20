#!/usr/bin/env python3
"""
generate_site.py - GitHub Pages用の静的サイトを生成するスクリプト

appearances.tsv と changes.tsv から以下を生成します：

- docs/index.html: トップページ（統計サマリー）
- docs/data/appearances.json: 全企業データ
- docs/data/statistics.json: 統計データ
- docs/assets/style.css: スタイルシート
- docs/assets/app.js: JavaScript

使用例:
    python generate_site.py
    python generate_site.py --docs public  # 出力先を変更
"""

import json
from pathlib import Path
from datetime import datetime
import pandas as pd


# =============================================================================
# データ読み込み
# =============================================================================

def load_appearances(filepath: Path) -> pd.DataFrame:
    """appearances.tsv を読み込む"""
    if filepath.exists():
        return pd.read_csv(filepath, sep='\t', dtype=str).fillna("")
    return pd.DataFrame()


def load_changes(filepath: Path) -> pd.DataFrame:
    """changes.tsv を読み込む"""
    if filepath.exists():
        return pd.read_csv(filepath, sep='\t')
    return pd.DataFrame()


# =============================================================================
# 統計データ生成
# =============================================================================

def generate_statistics(appearances: pd.DataFrame, changes: pd.DataFrame) -> dict:
    """
    統計データを生成する
    
    Args:
        appearances: 掲載履歴データ
        changes: 変更ログ
    
    Returns:
        統計データの辞書
    """
    stats = {
        "generated_at": datetime.now().isoformat(),
        "total_records": len(appearances),
        "active_count": 0,
        "removed_count": 0,
        "by_bureau": {},
        "by_year": {},
        "avg_duration_days": None,
        "recent_changes": []
    }
    
    if appearances.empty:
        return stats
    
    # ステータス別カウント
    if 'status' in appearances.columns:
        status_counts = appearances['status'].value_counts().to_dict()
        stats["active_count"] = status_counts.get("active", 0)
        stats["removed_count"] = status_counts.get("removed", 0)
    
    # 労働局別カウント
    if 'labor_bureau' in appearances.columns:
        bureau_counts = appearances['labor_bureau'].value_counts().to_dict()
        stats["by_bureau"] = bureau_counts
    
    # 年別カウント（初回掲載年）
    if 'first_appeared' in appearances.columns:
        appearances_copy = appearances.copy()
        appearances_copy['year'] = appearances_copy['first_appeared'].str[:4]
        year_counts = appearances_copy['year'].value_counts().sort_index().to_dict()
        stats["by_year"] = {k: v for k, v in year_counts.items() if k and k != 'nan' and k != ''}
    
    # 平均掲載期間
    if 'duration_days' in appearances.columns:
        durations = pd.to_numeric(appearances['duration_days'], errors='coerce')
        if durations.notna().any():
            stats["avg_duration_days"] = round(durations.mean(), 1)
    
    # 最近の変更
    if not changes.empty:
        recent = changes.tail(10).to_dict('records')
        stats["recent_changes"] = recent
    
    return stats


# =============================================================================
# HTML/CSS/JS 生成
# =============================================================================

def generate_index_html(docs_dir: Path, stats: dict):
    """index.html を生成する"""
    
    # 労働局別データをJSON文字列に変換（JavaScriptで使用）
    bureau_json = json.dumps(stats["by_bureau"], ensure_ascii=False)
    year_json = json.dumps(stats["by_year"], ensure_ascii=False)
    
    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>労働基準関係法令違反 公表事案アーカイブ</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <header>
        <h1>労働基準関係法令違反 公表事案アーカイブ</h1>
        <p>厚生労働省が公表する労働基準関係法令違反事案の時系列アーカイブ</p>
    </header>
    
    <main>
        <section class="stats-summary">
            <h2>統計サマリー</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <span class="stat-value">{stats['total_records']:,}</span>
                    <span class="stat-label">総記録数</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{stats['active_count']:,}</span>
                    <span class="stat-label">現在掲載中</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{stats['removed_count']:,}</span>
                    <span class="stat-label">掲載終了</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{stats['avg_duration_days'] if stats['avg_duration_days'] else '-'}</span>
                    <span class="stat-label">平均掲載日数</span>
                </div>
            </div>
        </section>
        
        <section class="data-section">
            <h2>年別推移</h2>
            <div id="year-chart" class="chart-container">
                <p class="no-data">データがありません</p>
            </div>
        </section>
        
        <section class="data-links">
            <h2>データファイル</h2>
            <ul>
                <li><a href="data/appearances.json">appearances.json</a> - 全企業の掲載履歴</li>
                <li><a href="data/statistics.json">statistics.json</a> - 統計データ</li>
            </ul>
            <p class="note">※ GitHubリポジトリからTSV形式でもダウンロードできます</p>
        </section>
        
        <section class="about">
            <h2>このプロジェクトについて</h2>
            <p>
                厚生労働省が公開する「労働基準関係法令違反に係る公表事案」のPDFをアーカイブし、
                時系列での掲載状況を追跡するプロジェクトです。
            </p>
            <p>
                厚労省の公表データは毎月更新され、一定期間後に削除されるため、
                過去のデータを参照することが困難です。このリポジトリでは、PDFの原本保存と
                掲載期間の追跡を行っています。
            </p>
            
            <h3>データソース</h3>
            <ul>
                <li><a href="https://www.mhlw.go.jp/kinkyu/151106.html" target="_blank" rel="noopener">厚生労働省 - 長時間労働削減に向けた取組</a></li>
                <li><a href="https://h-crisis.niph.go.jp/" target="_blank" rel="noopener">H-CRISIS（国立保健医療科学院）</a></li>
                <li><a href="https://web.archive.org/" target="_blank" rel="noopener">Internet Archive Wayback Machine</a></li>
            </ul>
            
            <h3>データ取得可能期間</h3>
            <table class="coverage-table">
                <tr><th>期間</th><th>ソース</th><th>状況</th></tr>
                <tr><td>2017年5月〜2018年7月</td><td>Wayback Machine</td><td>✅</td></tr>
                <tr><td>2018年8月〜2020年11月</td><td>-</td><td>❌ データ欠損期間</td></tr>
                <tr><td>2020年12月〜現在</td><td>H-CRISIS / 厚労省</td><td>✅</td></tr>
            </table>
            
            <div class="data-gap-notice">
                <h4>⚠️ データ欠損期間について</h4>
                <p>
                    2018年8月〜2020年11月の期間は、PDFデータが取得できていないため、この期間をまたぐレコードの情報は不正確な可能性があります。
                </p>
                <ul>
                    <li><strong>掲載終了日（last_appeared）</strong>: 実際より遅い日付になっている可能性</li>
                    <li><strong>掲載日数（duration_days）</strong>: 実際より長くなっている可能性</li>
                </ul>
                <p>
                    該当するレコードには <code>crossed_data_gap=true</code> フラグが付いています。
                </p>
            </div>
        </section>
    </main>
    
    <footer>
        <p>最終更新: {stats['generated_at'][:10]}</p>
        <p><a href="https://github.com/nyampire/jp-labor-violation-archive" target="_blank" rel="noopener">GitHub リポジトリ</a></p>
    </footer>
    
    <script>
        const bureauData = {bureau_json};
        const yearData = {year_json};
    </script>
    <script src="assets/app.js"></script>
</body>
</html>
'''
    
    with open(docs_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(html)


def generate_css(docs_dir: Path):
    """style.css を生成する"""
    
    css = '''/* 労働基準関係法令違反 公表事案アーカイブ - スタイルシート */

:root {
    --primary-color: #1e40af;
    --primary-light: #3b82f6;
    --bg-color: #f8fafc;
    --card-bg: #ffffff;
    --text-color: #1e293b;
    --text-muted: #64748b;
    --border-color: #e2e8f0;
    --success-color: #22c55e;
    --warning-color: #f59e0b;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
                 "Hiragino Sans", "Noto Sans JP", sans-serif;
    background-color: var(--bg-color);
    color: var(--text-color);
    line-height: 1.7;
}

/* ヘッダー */
header {
    background: linear-gradient(135deg, var(--primary-color), var(--primary-light));
    color: white;
    padding: 3rem 2rem;
    text-align: center;
}

header h1 {
    font-size: 1.75rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
}

header p {
    opacity: 0.9;
    font-size: 1rem;
}

/* メインコンテンツ */
main {
    max-width: 1000px;
    margin: 0 auto;
    padding: 2rem;
}

section {
    background: var(--card-bg);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--primary-color);
    border-bottom: 2px solid var(--border-color);
    padding-bottom: 0.5rem;
}

h3 {
    font-size: 1rem;
    font-weight: 600;
    margin: 1.5rem 0 0.75rem;
    color: var(--text-color);
}

/* 統計グリッド */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
}

.stat-card {
    background: var(--bg-color);
    padding: 1.25rem 1rem;
    border-radius: 8px;
    text-align: center;
    border: 1px solid var(--border-color);
}

.stat-value {
    display: block;
    font-size: 2rem;
    font-weight: 700;
    color: var(--primary-color);
    line-height: 1.2;
}

.stat-label {
    display: block;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
}

/* チャート */
.chart-container {
    min-height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.no-data {
    color: var(--text-muted);
}

.bar-chart {
    width: 100%;
}

.bar-row {
    display: flex;
    align-items: center;
    margin-bottom: 0.5rem;
}

.bar-label {
    width: 60px;
    font-size: 0.85rem;
    color: var(--text-muted);
}

.bar-container {
    flex: 1;
    height: 24px;
    background: var(--bg-color);
    border-radius: 4px;
    overflow: hidden;
}

.bar {
    height: 100%;
    background: var(--primary-light);
    border-radius: 4px;
    transition: width 0.3s ease;
}

.bar-value {
    width: 50px;
    text-align: right;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-left: 0.5rem;
}

/* リスト・テーブル */
ul {
    margin-left: 1.5rem;
}

li {
    margin-bottom: 0.5rem;
}

a {
    color: var(--primary-light);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

.note {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 0.75rem;
}

.coverage-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 0.75rem;
    font-size: 0.9rem;
}

.coverage-table th,
.coverage-table td {
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.coverage-table th {
    background: var(--bg-color);
    font-weight: 600;
}

/* データ欠損期間の注意書き */
.data-gap-notice {
    background: #fef3c7;
    border: 1px solid #f59e0b;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-top: 1.5rem;
}

.data-gap-notice h4 {
    font-size: 1rem;
    font-weight: 600;
    color: #92400e;
    margin-bottom: 0.75rem;
}

.data-gap-notice p {
    font-size: 0.9rem;
    color: #78350f;
    margin-bottom: 0.5rem;
}

.data-gap-notice ul {
    font-size: 0.9rem;
    color: #78350f;
    margin-left: 1.25rem;
    margin-bottom: 0.5rem;
}

.data-gap-notice li {
    margin-bottom: 0.25rem;
}

.data-gap-notice code {
    background: rgba(0, 0, 0, 0.1);
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 0.85rem;
}

/* フッター */
footer {
    text-align: center;
    padding: 2rem;
    color: var(--text-muted);
    font-size: 0.9rem;
}

footer p {
    margin-bottom: 0.5rem;
}

/* レスポンシブ */
@media (max-width: 640px) {
    header {
        padding: 2rem 1rem;
    }
    
    header h1 {
        font-size: 1.4rem;
    }
    
    main {
        padding: 1rem;
    }
    
    .stats-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .stat-value {
        font-size: 1.5rem;
    }
}
'''
    
    assets_dir = docs_dir / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    with open(assets_dir / 'style.css', 'w', encoding='utf-8') as f:
        f.write(css)


def generate_js(docs_dir: Path):
    """app.js を生成する"""
    
    js = '''// 労働基準関係法令違反 公表事案アーカイブ - JavaScript

document.addEventListener('DOMContentLoaded', function() {
    renderYearChart();
});

/**
 * 年別推移のバーチャートを描画
 */
function renderYearChart() {
    const container = document.getElementById('year-chart');
    if (!container) return;
    
    // yearData はHTMLにインラインで埋め込まれている
    if (typeof yearData === 'undefined' || Object.keys(yearData).length === 0) {
        return;
    }
    
    const years = Object.keys(yearData).sort();
    const values = years.map(y => yearData[y]);
    const maxValue = Math.max(...values);
    
    let html = '<div class="bar-chart">';
    
    for (const year of years) {
        const value = yearData[year];
        const width = (value / maxValue * 100).toFixed(1);
        
        html += `
            <div class="bar-row">
                <span class="bar-label">${year}</span>
                <div class="bar-container">
                    <div class="bar" style="width: ${width}%"></div>
                </div>
                <span class="bar-value">${value.toLocaleString()}</span>
            </div>
        `;
    }
    
    html += '</div>';
    container.innerHTML = html;
}
'''
    
    assets_dir = docs_dir / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    with open(assets_dir / 'app.js', 'w', encoding='utf-8') as f:
        f.write(js)


# =============================================================================
# メイン処理
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='GitHub Pages用の静的サイトを生成する',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s                              # デフォルト設定で生成
  %(prog)s --docs public                # 出力先を変更
        """
    )
    parser.add_argument('--appearances', default='timeline/appearances.tsv',
                        help='appearances.tsv のパス')
    parser.add_argument('--changes', default='timeline/changes.tsv',
                        help='changes.tsv のパス')
    parser.add_argument('--docs', default='docs',
                        help='出力ディレクトリ（デフォルト: docs）')
    
    args = parser.parse_args()
    
    appearances_path = Path(args.appearances)
    changes_path = Path(args.changes)
    docs_dir = Path(args.docs)
    
    print("GitHub Pages サイトを生成中...")
    print()
    
    # ディレクトリ作成
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / 'data').mkdir(parents=True, exist_ok=True)
    (docs_dir / 'assets').mkdir(parents=True, exist_ok=True)
    
    # データ読み込み
    appearances = load_appearances(appearances_path)
    changes = load_changes(changes_path)
    
    print(f"  appearances: {len(appearances)} 件")
    print(f"  changes: {len(changes)} 件")
    print()
    
    # 統計生成
    stats = generate_statistics(appearances, changes)
    
    # JSONデータ出力
    with open(docs_dir / 'data' / 'statistics.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    if not appearances.empty:
        appearances_json = appearances.to_dict('records')
        with open(docs_dir / 'data' / 'appearances.json', 'w', encoding='utf-8') as f:
            json.dump(appearances_json, f, ensure_ascii=False, indent=2)
    else:
        with open(docs_dir / 'data' / 'appearances.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    # HTML/CSS/JS生成
    generate_index_html(docs_dir, stats)
    generate_css(docs_dir)
    generate_js(docs_dir)
    
    print("生成完了:")
    print(f"  {docs_dir}/index.html")
    print(f"  {docs_dir}/data/statistics.json")
    print(f"  {docs_dir}/data/appearances.json")
    print(f"  {docs_dir}/assets/style.css")
    print(f"  {docs_dir}/assets/app.js")


if __name__ == "__main__":
    main()
