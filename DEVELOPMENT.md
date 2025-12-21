# 開発者ドキュメント

このドキュメントは、jp-labor-violation-archive プロジェクトのメンテナンス・開発を行う際のリファレンスです。

## 目次

1. [プロジェクト概要](#プロジェクト概要)
2. [ディレクトリ構成](#ディレクトリ構成)
3. [環境構築](#環境構築)
4. [スクリプト一覧](#スクリプト一覧)
5. [運用フロー](#運用フロー)
6. [データ形式](#データ形式)
7. [GitHub Actions](#github-actions)
8. [トラブルシューティング](#トラブルシューティング)
9. [既知の問題・制限事項](#既知の問題制限事項)

---

## プロジェクト概要

厚生労働省が公表する「労働基準関係法令違反に係る公表事案」のPDFをアーカイブし、掲載期間の時系列追跡を行うプロジェクト。

### データソース

| 期間 | ソース | 備考 |
|------|--------|------|
| 2017年5月〜2018年7月 | Wayback Machine | 過去アーカイブ |
| 2018年8月〜2020年11月 | - | **データ欠損期間** |
| 2020年12月〜現在 | H-CRISIS / 厚労省 | 現行データ |

### 主要URL

- **厚労省ページ**: https://www.mhlw.go.jp/kinkyu/151106.html
- **H-CRISIS**: https://h-crisis.niph.go.jp/
- **GitHub Pages**: https://nyampire.github.io/jp-labor-violation-archive/

---

## ディレクトリ構成

```
jp-labor-violation-archive/
│
├── archive/                        # PDFアーカイブ
│   ├── pdf/                        # PDF原本（年別サブディレクトリ）
│   │   ├── 2017/
│   │   ├── 2018/
│   │   ├── ...
│   │   └── 2025/
│   └── metadata.tsv                # 各PDFのメタデータ
│
├── timeline/                       # 時系列データ
│   ├── appearances.tsv             # 企業ごとの掲載履歴（メインデータ）
│   ├── changes.tsv                 # 更新ログ
│   └── current.tsv                 # 最新PDFから抽出した企業リスト（一時ファイル）
│
├── docs/                           # GitHub Pages（自動生成）
│   ├── index.html                  # トップページ
│   ├── data/
│   │   ├── appearances.json        # 全企業データ
│   │   ├── active.json             # 現在の公表対象のみ
│   │   └── statistics.json         # 統計データ
│   └── assets/
│       ├── style.css
│       └── app.js
│
├── scripts/                        # スクリプト
│   ├── fetch_pdf.py                # PDF取得
│   ├── extract_companies.py        # PDF→TSV変換
│   ├── diff_detect.py              # 差分検出・時系列追跡
│   ├── cleanup_tsv.py              # データLint・クリーンアップ
│   ├── generate_site.py            # GitHub Pages生成
│   ├── add_data_gap_flag.py        # データ欠損フラグ追加（一度だけ実行）
│   └── process_all_pdfs.sh         # 全PDF一括処理
│
├── .github/workflows/
│   └── monthly_update.yml          # 月次自動更新
│
├── README.md                       # プロジェクト説明
├── DEVELOPMENT.md                  # 本ドキュメント
├── LICENSE                         # MITライセンス
└── requirements.txt                # Python依存パッケージ
```

---

## 環境構築

### 必要なもの

- Python 3.9以上
- pip

### セットアップ

```bash
# リポジトリをクローン
git clone https://github.com/nyampire/jp-labor-violation-archive.git
cd jp-labor-violation-archive

# 依存パッケージをインストール
pip install -r requirements.txt
```

### 依存パッケージ

```
pandas
pdfplumber
requests
beautifulsoup4
```

---

## スクリプト一覧

### 1. fetch_pdf.py - PDF取得

厚労省、Wayback Machine、H-CRISISからPDFを取得する。

```bash
# 厚労省から最新PDFを取得
python scripts/fetch_pdf.py --source latest

# Wayback Machineから過去PDFを取得（2017-2018年）
python scripts/fetch_pdf.py --source wayback

# H-CRISISから取得（2020年以降）
python scripts/fetch_pdf.py --source hcrisis

# 特定の年のみ取得
python scripts/fetch_pdf.py --source hcrisis --year 2024
```

**出力**: `archive/pdf/YYYY/YYYY-MM-DD_XXXXXX.pdf`

### 2. extract_companies.py - PDF→TSV変換

PDFから企業リストを抽出してTSV形式で出力する。

```bash
# 基本的な使い方
python scripts/extract_companies.py archive/pdf/2025/2025-01-01_001234567.pdf

# 出力先を指定
python scripts/extract_companies.py archive/pdf/2025/2025-01-01_001234567.pdf -o timeline/current.tsv

# 詳細ログを表示
python scripts/extract_companies.py archive/pdf/2025/2025-01-01_001234567.pdf -v
```

**出力カラム**: `company_name`, `location`, `labor_bureau`, `violation_law`, `violation_summary`, `prosecution_date`, `publication_date`

### 3. diff_detect.py - 差分検出・時系列追跡

新しい企業リストと既存の掲載履歴を比較し、追加・削除を検出する。

```bash
# 基本的な使い方
python scripts/diff_detect.py timeline/current.tsv

# 日付を指定（過去データを処理する場合）
python scripts/diff_detect.py timeline/current.tsv -d 2024-06-01

# ファイルパスを指定
python scripts/diff_detect.py data.tsv -a timeline/appearances.tsv -c timeline/changes.tsv
```

**処理内容**:
- 新規追加: `first_appeared` を記録、`status=active`
- 掲載終了: `last_appeared` と `duration_days` を記録、`status=removed`

### 4. cleanup_tsv.py - データLint・クリーンアップ

appearances.tsv のデータ品質をチェックし、問題を修正する。

```bash
# 問題を検出して表示（修正なし）
python scripts/cleanup_tsv.py

# 警告も表示
python scripts/cleanup_tsv.py --warnings

# 全問題を詳細表示
python scripts/cleanup_tsv.py --all

# 問題を修正
python scripts/cleanup_tsv.py --fix

# バックアップを作成して修正
python scripts/cleanup_tsv.py --fix --backup
```

**検出する問題**:

| カテゴリ | 種別 | 対応 |
|---------|------|------|
| 日付形式 | エラー | 自動修正または削除 |
| 日付の年が範囲外 | エラー | 自動修正または削除 |
| 企業名が空/短すぎる | エラー | 削除 |
| PDFタイトル行の混入 | エラー | 削除 |
| 所在地にスペース混入 | エラー | 自動修正 |
| 所在地の文字化け | 警告 | 既知パターンは修正、それ以外は保持 |
| 企業名が長すぎる | 警告 | 保持 |

### 5. generate_site.py - GitHub Pages生成

appearances.tsv からGitHub Pages用のHTML/CSS/JS/JSONを生成する。

```bash
# 基本的な使い方
python scripts/generate_site.py

# 出力先を変更
python scripts/generate_site.py --docs public
```

**生成ファイル**:
- `docs/index.html` - トップページ
- `docs/data/appearances.json` - 全企業データ
- `docs/data/active.json` - 現在の公表対象のみ
- `docs/data/statistics.json` - 統計データ
- `docs/assets/style.css` - スタイルシート
- `docs/assets/app.js` - JavaScript

### 6. add_data_gap_flag.py - データ欠損フラグ追加

既存の appearances.tsv に `crossed_data_gap` フラグを追加する。**初回のみ実行**。

```bash
python scripts/add_data_gap_flag.py
```

### 7. process_all_pdfs.sh - 全PDF一括処理

archive/pdf 配下の全PDFを時系列順に処理する。**初期構築時に使用**。

```bash
bash scripts/process_all_pdfs.sh
```

---

## 運用フロー

### 月次更新（自動）

GitHub Actionsにより毎月1日と15日に自動実行される。

1. 厚労省から最新PDFを取得
2. PDFから企業リストを抽出
3. 差分検出・時系列追跡
4. GitHub Pages生成
5. コミット・プッシュ
6. GitHub Pagesにデプロイ

### 月次更新（手動）

```bash
# 1. 最新PDFを取得
python scripts/fetch_pdf.py --source latest

# 2. PDFから企業リストを抽出
python scripts/extract_companies.py archive/pdf/2025/YYYY-MM-DD_XXXXXX.pdf -o timeline/current.tsv

# 3. 差分検出
python scripts/diff_detect.py timeline/current.tsv

# 4. サイト生成
python scripts/generate_site.py

# 5. コミット・プッシュ
git add -A
git commit -m "Update: $(date +%Y-%m-%d)"
git push
```

### データクリーンアップ

問題が見つかった場合のクリーンアップ手順:

```bash
# 1. 問題を確認
python scripts/cleanup_tsv.py --all

# 2. バックアップを取って修正
python scripts/cleanup_tsv.py --fix --backup

# 3. サイト再生成
python scripts/generate_site.py

# 4. コミット
git add -A
git commit -m "Clean up data issues"
git push
```

### 過去データの追加

新たに過去のPDFが見つかった場合:

```bash
# 1. PDFを適切なディレクトリに配置
cp new_pdf.pdf archive/pdf/2019/2019-06-01_manual.pdf

# 2. 企業リストを抽出
python scripts/extract_companies.py archive/pdf/2019/2019-06-01_manual.pdf -o timeline/current.tsv

# 3. 日付を指定して差分検出
python scripts/diff_detect.py timeline/current.tsv -d 2019-06-01

# 4. 以降の全PDFを再処理（時系列順に）
bash scripts/process_all_pdfs.sh
```

---

## データ形式

### appearances.tsv

メインデータファイル。企業ごとの掲載履歴を記録。

| カラム | 型 | 説明 | 例 |
|--------|-----|------|-----|
| company_name | string | 企業・事業場名称 | （株）ABC建設 |
| location | string | 所在地 | 東京都新宿区 |
| labor_bureau | string | 管轄労働局 | 東京労働局 |
| first_appeared | date | 初回掲載日 | 2024-01-15 |
| last_appeared | date | 掲載終了日（activeなら空） | 2025-01-15 |
| duration_days | int | 掲載日数（終了後に計算） | 365 |
| violation_law | string | 違反法条 | 労働基準法第32条 |
| violation_summary | string | 事案概要 | 違法な時間外労働... |
| prosecution_date | string | 送検日 | H29.1.15 |
| status | string | 状態 | active / removed |
| crossed_data_gap | string | データ欠損期間をまたぐ | true / (空) |

### changes.tsv

更新ログ。各PDF処理時の追加・削除件数を記録。

| カラム | 説明 |
|--------|------|
| date | 更新日 |
| added | 追加件数 |
| removed | 削除件数 |
| total_active | 現在アクティブな件数 |

### metadata.tsv

PDF取得履歴。

| カラム | 説明 |
|--------|------|
| date | 取得日 |
| url | 取得元URL |
| filename | 保存ファイル名 |
| sha256 | ファイルハッシュ |
| source | ソース（mhlw / wayback / hcrisis） |
| period | 対象期間（あれば） |

---

## GitHub Actions

### ワークフロー: monthly_update.yml

```yaml
# 実行タイミング
on:
  schedule:
    - cron: '0 0 1,15 * *'  # 毎月1日と15日の 9:00 JST
  workflow_dispatch:        # 手動実行も可能
```

### 手動実行

1. GitHubリポジトリの **Actions** タブを開く
2. **Monthly PDF Update** を選択
3. **Run workflow** をクリック

### トラブルシューティング

**Actions失敗時の確認ポイント**:

1. **Fetch latest PDF** - 厚労省のURLが変わっていないか
2. **Extract companies** - PDF形式が変わっていないか
3. **Deploy to GitHub Pages** - `environment` 設定が正しいか

---

## トラブルシューティング

### PDF抽出がうまくいかない

厚労省のPDF形式が変わった可能性がある。

```bash
# 詳細ログを出力して確認
python scripts/extract_companies.py archive/pdf/2025/xxxx.pdf -v
```

`extract_companies.py` の抽出ロジックを確認・修正する。

### 文字化けデータが混入

PDF抽出時に文字化けが発生することがあります。GitHub Actionsでは自動的に文字化けを検出し、警告を出力します。

```bash
# 問題を確認
python scripts/cleanup_tsv.py --all | grep corrupted

# 文字化けの詳細を確認
python scripts/cleanup_tsv.py --warnings
```

**文字化けの例**: `中愛部知エ県リ愛ア西セ市ンタ`（正しくは `愛知県愛西市中部エリアセンタ`）

**対応方法**:
1. `cleanup_tsv.py` の `KNOWN_CORRUPTED_PATTERNS` に正しいパターンを追加
2. `--fix` オプションで自動修正

```python
# cleanup_tsv.py 内
KNOWN_CORRUPTED_PATTERNS = {
    '中愛部知エ県リ愛ア西セ市ンタ': '愛知県愛西市中部エリアセンタ',
    # 新しいパターンをここに追加
}
```

**検出ロジック**:
- 漢字とカタカナが不自然に交互に出現（例: `漢カ漢カ漢カ`）
- カタカナが散在して出現

### Git push が rejected される

GitHub Actionsが先にpushした場合:

```bash
git pull --rebase
git push
```

### GitHub Pagesが更新されない

1. Actions タブでワークフローの実行状況を確認
2. Settings → Pages でソースが **GitHub Actions** になっているか確認
3. 数分待ってからハードリロード（Ctrl+Shift+R）

---

## 既知の問題・制限事項

### データ欠損期間

**2018年8月〜2020年11月** のPDFデータが存在しない。

- この期間をまたぐレコードは `crossed_data_gap=true`
- `last_appeared` と `duration_days` が実際より長い可能性
- 平均掲載日数の計算からは除外済み

### PDF形式の変動

厚労省のPDF形式は時期によって異なる:
- テーブル形式（pdfplumberで抽出可能）
- テキスト形式（正規表現で抽出）

`extract_companies.py` は両方に対応しているが、形式が大きく変わった場合は修正が必要。

### 企業の同定

同一企業でも以下の場合は別レコードとして扱われる:
- 企業名の表記ゆれ（（株）vs 株式会社）
- 所在地の表記ゆれ
- 異なる違反法条

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2024-12-21 | 初版作成 |

---

## 連絡先

Issue、Pull Requestは GitHub リポジトリへ:
https://github.com/nyampire/jp-labor-violation-archive
