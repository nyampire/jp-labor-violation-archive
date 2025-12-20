# 労働基準関係法令違反 公表事案アーカイブ

厚生労働省が公開する「労働基準関係法令違反に係る公表事案」のPDFをアーカイブし、**掲載期間の時系列追跡**を行うプロジェクトです。

## このプロジェクトの目的

厚生労働省は労働基準関係法令に違反した企業・事業場を毎月公表していますが、一定期間（約1年）経過後にリストから削除されます。そのため：

- ❌ 過去にどの企業が掲載されていたか確認できない
- ❌ いつ掲載され、いつ削除されたか分からない
- ❌ 掲載期間の統計分析ができない

このリポジトリでは以下を提供します：

1. **PDFアーカイブ**: 過去のPDF原本を保存
2. **時系列追跡**: 各企業の初回掲載日・削除日・掲載期間を記録
3. **構造化データ**: TSV/JSON形式での機械可読データ
4. **GitHub Pages**: 統計情報を閲覧できるWebサイト

## 独自に提供する価値

| データ | 厚労省 | 他サービス | このリポジトリ |
|--------|:------:|:----------:|:--------------:|
| 現在の掲載企業一覧 | ✅ | ✅ | ✅ |
| 過去のPDF原本 | ❌ | ❌ | ✅ |
| 初回掲載日 | ❌ | ❌ | ✅ |
| 削除日 | ❌ | ❌ | ✅ |
| 掲載期間（日数） | ❌ | ❌ | ✅ |

## データソースと取得可能期間

| 期間 | ソース | 状況 |
|------|--------|:----:|
| 2017年5月〜2018年7月 | Internet Archive Wayback Machine | ✅ |
| 2018年8月〜2020年1月 | （未発見） | ❌ |
| 2020年2月〜現在 | H-CRISIS / 厚労省 | ✅ |

### 参照元リンク

- [厚生労働省 - 長時間労働削減に向けた取組](https://www.mhlw.go.jp/kinkyu/151106.html)
- [H-CRISIS（国立保健医療科学院）](https://h-crisis.niph.go.jp/)
- [Internet Archive Wayback Machine](https://web.archive.org/)

## ディレクトリ構成

```
jp-labor-violation-archive/
│
├── archive/                    # PDFアーカイブ
│   ├── pdf/                    # PDF原本（年別）
│   │   ├── 2017/
│   │   ├── 2018/
│   │   └── ...
│   └── metadata.tsv            # 各PDFのメタデータ（URL, ハッシュ等）
│
├── timeline/                   # 時系列データ
│   ├── appearances.tsv         # 企業ごとの掲載履歴（メインデータ）
│   ├── changes.tsv             # 更新ログ
│   └── current.tsv             # 最新PDFから抽出した企業リスト
│
├── docs/                       # GitHub Pages
│   ├── index.html
│   ├── data/
│   │   ├── appearances.json
│   │   └── statistics.json
│   └── assets/
│       ├── style.css
│       └── app.js
│
├── scripts/                    # スクリプト
│   ├── extract_companies.py    # PDF → TSV変換
│   ├── diff_detect.py          # 差分検出・時系列追跡
│   ├── fetch_pdf.py            # PDF取得（厚労省/Wayback/H-CRISIS）
│   └── generate_site.py        # GitHub Pages生成
│
├── .github/workflows/
│   └── monthly_update.yml      # 月次自動更新
│
├── requirements.txt
└── README.md
```

## データ形式

### `timeline/appearances.tsv`（メインデータ）

| カラム | 説明 | 例 |
|--------|------|-----|
| company_name | 企業・事業場名称 | （株）旅館ららぽーと函館 |
| location | 所在地 | 北海道函館市 |
| labor_bureau | 管轄労働局 | 北海道労働局 |
| first_appeared | 初回掲載日 | 2025-01-15 |
| last_appeared | 掲載終了日（activeなら空） | 2026-01-15 |
| duration_days | 掲載日数（終了後に計算） | 365 |
| violation_law | 違反法条 | 労働基準法第108条 |
| violation_summary | 事案概要 | 賃金台帳の記入不備... |
| prosecution_date | 送検日 | 2025-01-15 |
| status | 状態 | active / removed |

### `archive/metadata.tsv`

| カラム | 説明 |
|--------|------|
| date | 取得日 |
| url | 取得元URL |
| filename | 保存ファイル名 |
| sha256 | ファイルハッシュ |
| source | ソース（mhlw / wayback / hcrisis） |
| period | 対象期間（あれば） |

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/nyampire/jp-labor-violation-archive.git
cd jp-labor-violation-archive
```

### 2. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 3. 過去のPDFを取得

```bash
# Wayback Machineから2017-2018年のPDFを取得
python scripts/fetch_pdf.py --source wayback

# H-CRISISから2020年以降のPDFを取得
python scripts/fetch_pdf.py --source hcrisis

# 厚労省の最新PDFを取得
python scripts/fetch_pdf.py --source latest
```

### 4. PDFから企業リストを抽出

```bash
# 例: 特定のPDFを処理
python scripts/extract_companies.py archive/pdf/2025/2025-12-01_001527991.pdf -o timeline/current.tsv
```

### 5. 差分検出（時系列追跡）

```bash
python scripts/diff_detect.py timeline/current.tsv
```

### 6. GitHub Pagesを生成

```bash
python scripts/generate_site.py
```

## 自動更新

GitHub Actionsにより、毎月1日と15日に自動更新されます。

手動実行する場合は、GitHubリポジトリの Actions タブから `Monthly PDF Update` を選択し、`Run workflow` をクリックしてください。

## 分析例

このデータセットで可能になる分析：

- 「公表から削除まで平均何日か？」
- 「違反類型（安全衛生 vs 賃金未払い）で掲載期間に差があるか？」
- 「特定の労働局で公表件数が多い時期はあるか？」
- 「再掲載された企業はあるか？」

## 関連プロジェクト

- [nyampire/jp_labor_act_illegal_list](https://github.com/nyampire/jp_labor_act_illegal_list) - 旧リポジトリ（2017-2018年の変換済みTSV）
- [セルフキャリアデザイン協会 - 公表事案検索](https://self-cd.or.jp/violation-3) - 2020年以降の累積データ（Looker Studio）

## ライセンス

- **データ**: 厚生労働省の公開情報に基づく
- **スクリプト**: MIT License

## 貢献

Issue、Pull Requestを歓迎します。特に以下を募集しています：

- 2018年8月〜2020年1月のPDFデータ提供
- PDF解析精度の向上
- データの検証・修正
