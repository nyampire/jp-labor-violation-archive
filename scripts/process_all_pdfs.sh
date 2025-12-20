#!/bin/bash
#
# process_all_pdfs.sh - archive/pdf 配下の全PDFを処理して appearances.tsv を構築する
#
# 使用方法:
#   ./scripts/process_all_pdfs.sh
#
# 処理内容:
#   1. archive/pdf 配下の全PDFをファイル名（日付順）でソート
#   2. 各PDFから企業リストを抽出
#   3. 差分検出を実行して appearances.tsv を更新
#

set -e  # エラーで停止

# カラー出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# スクリプトのディレクトリを基準にプロジェクトルートを特定
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ディレクトリ設定
PDF_DIR="$PROJECT_ROOT/archive/pdf"
TIMELINE_DIR="$PROJECT_ROOT/timeline"
CURRENT_TSV="$TIMELINE_DIR/current.tsv"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}PDF一括処理スクリプト${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo "プロジェクトルート: $PROJECT_ROOT"
echo "PDFディレクトリ: $PDF_DIR"
echo ""

# PDFファイルを検索（ファイル名でソート = 日付順）
PDF_FILES=$(find "$PDF_DIR" -name "*.pdf" -type f 2>/dev/null | sort)

if [ -z "$PDF_FILES" ]; then
    echo -e "${RED}エラー: PDFファイルが見つかりません${NC}"
    echo "先に以下を実行してください:"
    echo "  python scripts/fetch_pdf.py --source all"
    exit 1
fi

# ファイル数をカウント
TOTAL=$(echo "$PDF_FILES" | wc -l | tr -d ' ')
echo -e "処理対象: ${GREEN}$TOTAL${NC} ファイル"
echo ""

# 既存の appearances.tsv をバックアップ（存在する場合）
if [ -f "$TIMELINE_DIR/appearances.tsv" ]; then
    BACKUP_FILE="$TIMELINE_DIR/appearances.tsv.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$TIMELINE_DIR/appearances.tsv" "$BACKUP_FILE"
    echo -e "${YELLOW}既存データをバックアップ: $BACKUP_FILE${NC}"
    echo ""
fi

# 確認プロンプト
read -p "処理を開始しますか？ (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "キャンセルしました"
    exit 0
fi

echo ""
echo -e "${BLUE}処理開始...${NC}"
echo ""

# timeline ディレクトリを作成
mkdir -p "$TIMELINE_DIR"

# 初回実行時は appearances.tsv を削除してクリーンスタート
if [ -f "$TIMELINE_DIR/appearances.tsv" ]; then
    read -p "既存の appearances.tsv を削除してクリーンスタートしますか？ (y/N): " CLEAN
    if [[ "$CLEAN" =~ ^[Yy]$ ]]; then
        rm -f "$TIMELINE_DIR/appearances.tsv"
        rm -f "$TIMELINE_DIR/changes.tsv"
        echo -e "${YELLOW}クリーンスタートします${NC}"
    fi
fi

echo ""

# カウンター
COUNT=0
SUCCESS=0
FAILED=0

# 各PDFを処理
while IFS= read -r PDF_FILE; do
    COUNT=$((COUNT + 1))
    
    # ファイル名から日付を抽出（例: 2017-05-10_170510-01.pdf → 2017-05-10）
    FILENAME=$(basename "$PDF_FILE")
    DATE_PART=$(echo "$FILENAME" | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}' || echo "")
    
    if [ -z "$DATE_PART" ]; then
        echo -e "${YELLOW}[$COUNT/$TOTAL] スキップ（日付が抽出できません）: $FILENAME${NC}"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    echo -e "${BLUE}[$COUNT/$TOTAL]${NC} $FILENAME (日付: $DATE_PART)"
    
    # Step 1: PDFから企業リストを抽出
    echo "  抽出中..."
    if python3.9 "$SCRIPT_DIR/extract_companies.py" "$PDF_FILE" -o "$CURRENT_TSV"; then
        # 抽出件数を取得
        EXTRACTED=$(tail -n +2 "$CURRENT_TSV" 2>/dev/null | wc -l | tr -d ' ')
        echo -e "  ${GREEN}抽出完了: $EXTRACTED 件${NC}"
    else
        echo -e "  ${RED}抽出失敗${NC}"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    # 抽出件数が0の場合はスキップ
    if [ "$EXTRACTED" -eq 0 ]; then
        echo -e "  ${YELLOW}警告: 抽出件数が0件のためスキップ${NC}"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    # Step 2: 差分検出
    echo "  差分検出中..."
    if python3.9 "$SCRIPT_DIR/diff_detect.py" "$CURRENT_TSV" -d "$DATE_PART"; then
        echo -e "  ${GREEN}差分検出完了${NC}"
        SUCCESS=$((SUCCESS + 1))
    else
        echo -e "  ${RED}差分検出失敗${NC}"
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
    
done <<< "$PDF_FILES"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}処理完了${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo -e "成功: ${GREEN}$SUCCESS${NC} / $TOTAL"
echo -e "失敗: ${RED}$FAILED${NC} / $TOTAL"
echo ""

# 結果サマリー
if [ -f "$TIMELINE_DIR/appearances.tsv" ]; then
    TOTAL_RECORDS=$(tail -n +2 "$TIMELINE_DIR/appearances.tsv" | wc -l | tr -d ' ')
    ACTIVE=$(grep -c "active" "$TIMELINE_DIR/appearances.tsv" 2>/dev/null || echo "0")
    REMOVED=$(grep -c "removed" "$TIMELINE_DIR/appearances.tsv" 2>/dev/null || echo "0")
    
    echo "appearances.tsv:"
    echo -e "  総レコード数: ${GREEN}$TOTAL_RECORDS${NC}"
    echo -e "  アクティブ: ${GREEN}$ACTIVE${NC}"
    echo -e "  削除済み: ${YELLOW}$REMOVED${NC}"
fi

echo ""
echo "次のステップ:"
echo "  1. python3.9 scripts/generate_site.py  # GitHub Pages生成"
echo "  2. git add -A && git commit -m 'Add historical data'"
echo "  3. git push"
