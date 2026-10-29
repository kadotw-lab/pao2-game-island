# -*- coding: utf-8 -*-
"""
文興遊戲群島 — 資料建置腳本
用法：在「20261029_跑二遊戲島」資料夾執行  python3 _island/build.py
依 CLASSES 設定掃描各班的「遊戲程式」與「遊戲封面」資料夾，產生：
  _island/covers/   封面縮圖 (jpg)
  _island/games/    沒有副檔名的遊戲檔，複製一份加上 .html
  _island/data.js   島嶼資料（index.html 會讀取）
新增同學作品或新的班級後重跑一次即可。
"""
import os, re, json, shutil, difflib, urllib.parse, sys, io, base64
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
OUT = '_island'
os.makedirs(f'{OUT}/covers', exist_ok=True)
os.makedirs(f'{OUT}/games', exist_ok=True)

# ---- 班級設定：要加新班級，在這裡多加一行 ----
CLASSES = [
    {'key': 'pao2', 'name': '跑二', 'course': '國二跑班資訊科技', 'games': '遊戲程式',          'covers': '遊戲封面',          'color': '#3b3550'},
    {'key': 'pao6', 'name': '跑六', 'course': '國一跑班資訊科技', 'games': '跑六/跑六遊戲程式', 'covers': '跑六/跑六遊戲封面', 'color': '#ef6f53'},
]

# ---- 手動修正（可自行增補）----
# 封面配對：{學號: [第1款遊戲用第幾張封面, 第2款..]}（從 1 起算）
COVER_ORDER = {'114170': [2, 1]}
# 遊戲顯示名稱（Gemini 連結作品，或網頁標題不適合直接顯示的）
TITLE_OVERRIDES = {'114218': '達達特攻', '114244': '姜精改史：姜精戰黃帝',
                   '114289': '無名射擊遊戲', '114318': '奇特遊戲：霓虹奇幻騎士',
                   '115159': '記憶翻牌'}

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
    return atts, links

def game_title(path):
    m = re.search(r'<title[^>]*>(.*?)</title>', read(path), re.S | re.I)
    t = m.group(1).strip() if m else os.path.basename(path)
    return re.sub(r'\s+', ' ', t)

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

def students(game_dir, cover_dir):
    ids = {}
    for tree in (game_dir, cover_dir):
        if not os.path.isdir(tree): continue
        for d in os.listdir(tree):
            m = re.match(r'(hs\d+)\s*\((.*?)\)', d)
            if m: ids.setdefault(m.group(1), m.group(2))
    return sorted(ids.items())

def thumb(src, dst, w=640):
    try:
        im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
        im.thumbnail((w, w * 2))
        im.save(dst, 'JPEG', quality=82, optimize=True, progressive=True)
        return im.size
    except Exception as e:
        print('  ! 封面無法讀取', src, e)
        return None

def tex_b64(src, w=300):
    im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
    im.thumbnail((w, w * 2))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=72, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()

islands = []
for cl in CLASSES:
    GAME_DIR, COVER_DIR = cl['games'], cl['covers']
    print(f"== {cl['name']}（{cl['course']}）")
    for sid, name in students(GAME_DIR, COVER_DIR):
        num = sid[2:]
        folder = f'{sid} ({name})'
        games, links, covers = [], [], []
        gc = os.path.join(GAME_DIR, folder, 'content.html')
        if os.path.exists(gc):
            atts, links = parse_content(gc)
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
                if num in TITLE_OVERRIDES and len(atts) == 1: main, sub = TITLE_OVERRIDES[num], ''
                games.append({'title': main, 'sub': sub, 'href': href.replace(os.sep, '/')})
        cc = os.path.join(COVER_DIR, folder, 'content.html')
        if os.path.exists(cc):
            atts, clinks = parse_content(cc)
            links = links + [u for u in clinks if u not in links]
            for i, a in enumerate(atts):
                src = os.path.join(COVER_DIR, folder, a)
                if not os.path.exists(src): continue
                dst = f'{OUT}/covers/{num}_{i+1}.jpg'
                size = thumb(src, dst)
                if size:
                    covers.append({'src': dst, 'name': os.path.splitext(a)[0], 'w': size[0], 'h': size[1], 'tex': tex_b64(dst)})
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
        ext = [u for u in links if 'http' in u]
        if not games and ext:
            games.append({'title': TITLE_OVERRIDES.get(num, '線上版遊戲'), 'sub': 'Gemini 線上遊戲', 'href': ext[0], 'external': True,
                          'cover': covers[0]['src'] if covers else None})
        islands.append({'id': num, 'name': name, 'cls': cl['key'], 'games': games,
                        'covers': [{k: c[k] for k in ('src', 'w', 'h', 'tex')} for c in covers]})
        print(' ', num, name, len(games), 'games', len(covers), 'covers')

with open(f'{OUT}/data.js', 'w', encoding='utf-8') as f:
    f.write('// 由 build.py 自動產生，請勿手動編輯\nwindow.CLASSES = ')
    json.dump([{k: c[k] for k in ('key', 'name', 'course', 'color')} for c in CLASSES], f, ensure_ascii=False)
    f.write(';\nwindow.ISLANDS = ')
    json.dump(islands, f, ensure_ascii=False, indent=1)
    f.write(';\n')
print('完成：', len(islands), '座島，', sum(len(i['games']) for i in islands), '款遊戲')
