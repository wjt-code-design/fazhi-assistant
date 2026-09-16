import json, re, os

# 统计方括号与书名号引用在 011 RAG 中的出现
brk = re.compile(r'\[[^\]]{1,20}?\s*(?:第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条)')
book = re.compile(r'《[^》]{1,24}?》\s*第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条')
rows = json.load(open('C:/Users/33393/Desktop/ai-legal-helper/diag/official-capture-011-rag/rows.json', encoding='utf-8'))
b = sum(len(brk.findall(r.get('answer') or '')) for r in rows)
k = sum(len(book.findall(r.get('answer') or '')) for r in rows)
print(f'011 RAG: bracket-cites={b}, book-cites={k}, answers={len(rows)}')
for r in rows:
    a = r.get('answer') or ''
    if brk.findall(a):
        print('  bracket in:', r['id'])