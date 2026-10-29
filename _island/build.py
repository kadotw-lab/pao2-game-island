# -*- coding: utf-8 -*-
"""
跑二遊戲島 — 資料建置腳本
用法：在「20261029_跑二遊戲島」資料夾執行  python3 _island/build.py
會掃描「遊戲程式」與「遊戲封面」兩個資料夾，產生：
  _island/covers/   封面縮圖 (jpg)
  _island/games/    沒有副檔名的遊戲檔，複製一份加上 .html
  _island/data.js   島嶼資料（index.html 會讀取）
新增同學作品後重跑一次即可。
"""
import os, re, json, shutil, difflib, urllib.parse, sys, io, base64
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
GAME_DIR, COVER_DIR = '遊戲程式', '遊戲封面'
OUT = '_island'
os.makedirs(f'{OUT}/covers', exist_ok=True)
os.makedirs(f'{OUT}/games', exist_ok=True)

def read(p):
    return open(p, encoding='utf-8', errors='ignore').read()

def parse_content(p):
    s = read(p)
    atts = [urllib.parse.unquote(a) for a in re.findall(r"<li>\s*<a href='([^']*)'", s)]
    art = re.search(r"<div class=article>(.*?)</div>", s, re.S)
    links = []
    if art:
        links = re.findall(r'href=["\']?(https?://[^"\'> ]+)', art.group(1))
        links += [u for u in re.findall(r'https?://[^\s<"\']+', re.sub(r'<[^>]+>', ' ', art.group(1))) if u not in links]
    t = re.search(r"<div class='title'><a[^>]*>(.*?)</a>", s)
    return atts, links, (t.group(1) if t else '')

def game_title(path):
    s = read(path)
    m = re.search(r'<title[^>]*>(.*?)</title>', s, re.S | re.I)
    t = m.group(1).strip() if m else os.path.basename(path)
    t = re.sub(r'\s+', ' ', t)
    return t

def short(t):
    # 「中文標題 (English)」→ 主標 + 副標
    t = t.replace('｜', '|')
    main, sub = t, ''
    for sep in [' - ', ' | ', ' (', '（']:
        if sep in main:
            i = main.index(sep)
            main, sub = main[:i], main[i:].strip(' -|()（）')
            break
    return main.strip(), sub.strip(' ()（）')

def students():
    ids = {}
    for tree in (GAME_DIR, COVER_DIR):
        if not os.path.isdir(tree): continue
        for d in os.listdir(tree):
            m = re.match(r'(hs\d+)\s*\((.*?)\)', d)
            if m: ids.setdefault(m.group(1), m.group(2))
    return sorted(ids.items())

def thumb(src, dst, w=640):
    try:
        im = Image.open(src)
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((w, w * 2))
        im.save(dst, 'JPEG', quality=82, optimize=True, progressive=True)
        return im.size
    except Exception as e:
        print('  ! 封面無法讀取', src, e)
        return None

# ---- 手動修正（可自行增補）----
# 封面配對：{學號: [第1款遊戲用第幾張封面, 第2款..]}（從 1 起算）
COVER_ORDER = {'114170': [2, 1]}
# 線上(Gemini)作品的顯示名稱
TITLE_OVERRIDES = {'114218': '達達特攻', '114244': '姜精改史：姜精戰黃帝',
                   '114289': '無名射擊遊戲', '114318': '奇特遊戲：霓虹奇幻騎士'}

def tex_b64(src, w=300):
    im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
    im.thumbnail((w, w * 2))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=72, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()

islands = []
for sid, name in students():
    num = sid[2:]
    folder = f'{sid} ({name})'
    games, links, covers = [], [], []
    gc = os.path.join(GAME_DIR, folder, 'content.html')
    if os.path.exists(gc):
        atts, links, _ = parse_content(gc)
        for i, a in enumerate(atts):
            src = os.path.join(GAME_DIR, folder, a)
            if not os.path.exists(src): continue
            low = a.lower()
            if not (low.endswith('.html') or low.endswith('.htm')):
                if '.' in os.path.basename(a)[-6:]:
                    continue  # 非網頁附件
                dst = f'{OUT}/games/{num}_{i+1}.html'
                shutil.copyfile(src, dst)
                href = dst
            else:
                href = src
            main, sub = short(game_title(src))
            games.append({'title': main, 'sub': sub, 'href': href.replace(os.sep, '/')})
    cc = os.path.join(COVER_DIR, folder, 'content.html')
    if os.path.exists(cc):
        atts, _, _ = parse_content(cc)
        for i, a in enumerate(atts):
            src = os.path.join(COVER_DIR, folder, a)
            if not os.path.exists(src): continue
            dst = f'{OUT}/covers/{num}_{i+1}.jpg'
            size = thumb(src, dst)
            if size:
                covers.append({'src': dst, 'name': os.path.splitext(a)[0], 'w': size[0], 'h': size[1],
                               'tex': tex_b64(dst)})
    # 封面與遊戲配對（多款遊戲時依名稱相似度）
    used = set()
    for g in games:
        best, score = None, -1
        for j, c in enumerate(covers):
            if j in used: continue
            r = difflib.SequenceMatcher(None, g['title'], c['name']).ratio()
            if r > score: best, score = j, r
        if best is not None and (len(covers) == len(games) or score > 0.3 or len(covers) == 1):
            g['cover'] = covers[best]['src']
            if len(covers) > 1: used.add(best)
    for g in games:
        if 'cover' not in g and covers: g['cover'] = covers[0]['src']
    if num in COVER_ORDER:
        for g, k in zip(games, COVER_ORDER[num]):
            if k - 1 < len(covers): g['cover'] = covers[k - 1]['src']
    ext = [u for u in links if 'gemini' in u or 'http' in u]
    if not games and ext:
        games.append({'title': TITLE_OVERRIDES.get(num, '線上版遊戲'), 'sub': 'Gemini 線上遊戲', 'href': ext[0], 'external': True,
                      'cover': covers[0]['src'] if covers else None})
    islands.append({'id': num, 'name': name, 'games': games,
                    'covers': [{k: c[k] for k in ('src', 'w', 'h', 'tex')} for c in covers]})
    print(num, name, len(games), 'games', len(covers), 'covers')

with open(f'{OUT}/data.js', 'w', encoding='utf-8') as f:
    f.write('// 由 build.py 自動產生，請勿手動編輯\nwindow.ISLANDS = ')
    json.dump(islands, f, ensure_ascii=False, indent=1)
    f.write(';\n')
print('完成：', len(islands), '座島，', sum(len(i['games']) for i in islands), '款遊戲')
