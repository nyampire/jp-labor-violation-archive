python3.9 -c "
import pdfplumber

with pdfplumber.open('archive/pdf/2017/2017-05-10_170510-01.pdf') as pdf:
    page = pdf.pages[1]  # 2ページ目
    tables = page.extract_tables()
    
    print(f'テーブル数: {len(tables)}')
    if tables:
        table = tables[0]
        print(f'行数: {len(table)}')
        print(f'列数: {len(table[0]) if table else 0}')
        print()
        print('=== 最初の5行 ===')
        for i, row in enumerate(table[:5]):
            print(f'行{i}: {row}')
"
