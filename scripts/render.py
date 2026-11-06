#!/usr/bin/env python3
"""XII News : fabrique les visuels du jour à partir d'un fichier d'édition JSON.

Usage : python3 scripts/render.py <edition.json> <dossier_sortie> <logo.jpg>

Entrée : {"dateLabel": "Jeudi 5 novembre 2026", "slides": [{cat, kicker, title, body, why, source, url, stat?, list?, image?}, ...]}
  image (facultatif) : {"url": lien direct vers une photo libre de droits, "credit": "Auteur / licence"}, utilisée en fond de la story
Sortie :
  post_01.jpg ... post_13.jpg   carrousel 1080x1350 : sommaire puis les 12 infos, chacune avec sa source
  story_01.jpg ... story_12.jpg stories 1080x1920 : les 12 mêmes infos, qui renvoient au post
  caption.txt                   légende du post (sources listées, 2 200 caractères max)
  manifest.json                 ce que le robot de publication doit envoyer
Les polices (Google Fonts, licence OFL) sont téléchargées au premier lancement.
"""
import json, math, os, random, sys, urllib.request
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
FONT_URLS = {
    "Archivo.ttf": "ofl/archivo/Archivo%5Bwdth,wght%5D.ttf",
    "Mono.ttf": "ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
}
W = 1080
STORY_H, POST_H = 1920, 1350
RED = "#e3262b"
INK = (246, 247, 249)
BLACK = (17, 19, 23)
CATS = {
    "breaking": ("Breaking", "#ff4b55"),
    "geo": ("Géopolitique", "#f2b45a"),
    "biz": ("Entreprises", "#5fd6a8"),
    "ia": ("IA", "#a993ff"),
    "robot": ("Robotique", "#5cc4f0"),
    "space": ("Espace", "#93a8ff"),
    "science": ("Science & santé", "#7fe08f"),
    "games": ("Jeux vidéo", "#f27ad3"),
    "sport": ("Sport", "#f5cf47"),
    "culture": ("Culture & ciné", "#f59366"),
    "watch": ("Aujourd'hui", "#e3262b"),
}
ORDER = ["breaking", "geo", "biz", "ia", "robot", "space", "science", "games", "sport", "culture"]
FILL_FROM = ["breaking", "geo", "biz", "ia", "science", "space", "sport", "games", "robot", "culture"]
CAPTION_MAX = 2200


# ---------- outils ----------

def fonts():
    os.makedirs(FONTS, exist_ok=True)
    for name, path in FONT_URLS.items():
        dst = os.path.join(FONTS, name)
        if not os.path.exists(dst):
            urllib.request.urlretrieve("https://raw.githubusercontent.com/google/fonts/main/" + path, dst)
    cache = {}

    def f(name, size, weight=None, width=None):
        key = (name, size, weight, width)
        if key not in cache:
            ft = ImageFont.truetype(os.path.join(FONTS, name), size)
            try:
                vals = []
                for a in ft.get_variation_axes():
                    n = a["name"].decode() if isinstance(a["name"], bytes) else str(a["name"])
                    if n.lower().startswith("weight"):
                        vals.append(weight or a["default"])
                    elif n.lower().startswith("width"):
                        vals.append(width or a["default"])
                    else:
                        vals.append(a["default"])
                ft.set_variation_by_axes(vals)
            except Exception:
                pass
            cache[key] = ft
        return cache[key]
    return f


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def wrap(draw, text, font, width):
    words, lines, cur = str(text or "").split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def spaced(draw, xy, text, font, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x


def domain(url):
    try:
        d = urlparse(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""


# ---------- fonds ----------

def base_bg(h):
    img = Image.new("RGB", (W, h), (17, 20, 25))
    top = Image.new("RGB", (W, h), (40, 46, 56))
    mask = Image.linear_gradient("L").resize((W, h)).point(lambda v: 255 - v)
    img.paste(top, (0, 0), mask)
    return img.convert("RGBA")


def red_arc(img, cx, cy, r, start, end, width=10, alpha=230):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).arc([cx - r, cy - r, cx + r, cy + r], start, end, fill=hexc(RED, alpha), width=width)
    img.alpha_composite(layer)


def motif(img, cat, accent, seed, story):
    """Illustration générative de la rubrique, dans le haut de l'image."""
    h = img.size[1]
    rnd = random.Random(seed)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = W / 2
    cy = h * (0.30 if story else 0.27)
    zone = h * (0.60 if story else 0.52)
    k = 1.0 if story else 0.78
    G = lambda a: (205, 214, 226, int(a))
    A = lambda a: hexc(accent, int(a))
    if cat == "breaking":
        for i in range(7):
            r = (80 + i * 110) * k
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=G(150 - i * 18), width=3)
        d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=hexc(RED))
        for y in range(0, h, 12):
            d.line([0, y, W, y], fill=(255, 255, 255, 8))
    elif cat == "geo":
        R = W * 0.38 * k
        for la in range(-75, 76, 15):
            for lo in range(0, 360, 7):
                a, b = math.radians(lo + 20), math.radians(la)
                x, z, y = math.cos(b) * math.sin(a), math.cos(b) * math.cos(a), math.sin(b)
                if z >= 0:
                    d.ellipse([cx + x * R - 3.5, cy - y * R - 3.5, cx + x * R + 3.5, cy - y * R + 3.5], fill=G(50 + 170 * z))
        for _ in range(7):
            a, b = math.radians(rnd.uniform(-60, 60)), math.radians(rnd.uniform(-50, 50))
            x, y = math.sin(a) * math.cos(b), math.sin(b)
            d.ellipse([cx + x * R - 8, cy - y * R - 8, cx + x * R + 8, cy - y * R + 8], fill=A(255))
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=G(110), width=3)
    elif cat == "biz":
        n, base, w = 12, cy + h * 0.18 * k, W / 12
        for i in range(n):
            bh = (0.25 + 0.55 * rnd.random()) * h * 0.30 * k
            x = i * w + w * 0.25
            d.rectangle([x, base - bh, x + w * 0.5, base - bh * 0.3], fill=G(150 if rnd.random() > 0.35 else 60))
            d.line([x + w * 0.25, base - bh - 24, x + w * 0.25, base - bh * 0.3 + 24], fill=G(130), width=3)
        pts = [(i / 30 * W, cy + h * 0.08 * k - i / 30 * h * 0.15 * k + math.sin(i * 0.9) * 22) for i in range(31)]
        d.line(pts, fill=A(240), width=6)
    elif cat in ("ia", "science"):
        pts = [(W * rnd.random(), zone * rnd.random()) for _ in range(38)]
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dist = math.dist(pts[i], pts[j])
                if dist < W * 0.27:
                    d.line([pts[i], pts[j]], fill=G(120 * (1 - dist / (W * 0.27))), width=2)
        for n_, p in enumerate(pts):
            d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=A(240) if n_ % 5 == 0 else G(200))
        if cat == "science":
            for j in range(2):
                wave = [(W * 0.15 + t * W * 0.7 / 60, cy + math.sin(t / 60 * math.pi * 4 + j * math.pi) * 120 * k) for t in range(61)]
                d.line(wave, fill=A(220) if j == 0 else G(170), width=5)
    elif cat == "robot":
        for x in range(-h, W + h, 60):
            d.line([x, 0, x + h * 0.58, h], fill=(255, 255, 255, 22), width=2)
            d.line([x, 0, x - h * 0.58, h], fill=(255, 255, 255, 22), width=2)

        def gear(x, y, r, teeth, rot, col):
            p = [(x + math.cos(rot + i * math.pi / teeth) * (r if i % 2 else r * 1.18),
                  y + math.sin(rot + i * math.pi / teeth) * (r if i % 2 else r * 1.18)) for i in range(teeth * 2)]
            d.polygon(p, outline=col, width=6)
            d.ellipse([x - r * .35, y - r * .35, x + r * .35, y + r * .35], outline=col, width=6)
        gear(cx - W * 0.12, cy, W * 0.2 * k, 12, 0.2, G(220))
        gear(cx + W * 0.22, cy + W * 0.22 * k, W * 0.12 * k, 8, 0.5, A(240))
    elif cat == "space":
        for _ in range(320):
            z = rnd.random()
            x, y, r = W * rnd.random(), h * rnd.random(), 1 + z * 3
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(60 + 180 * z)))
        ry = W * 0.12 * k
        d.ellipse([cx - W * 0.42, cy - ry, cx + W * 0.42, cy + ry], outline=G(170), width=3)
        d.ellipse([cx - 14, cy - ry - 14, cx + 14, cy - ry + 14], fill=A(255))
    elif cat == "games":
        px = 40
        for gy in range(0, int(zone), px):
            for gx in range(0, W, px):
                if rnd.random() < 0.16:
                    d.rectangle([gx + 4, gy + 4, gx + px - 4, gy + px - 4], fill=G(40 + 120 * rnd.random()))
        bw, bh = 260 * k, 110 * k
        d.rounded_rectangle([cx - bw, cy - bh, cx + bw, cy + bh], radius=bh, outline=G(230), width=8)
        d.line([cx - bw * .65, cy, cx - bw * .35, cy], fill=G(230), width=10)
        d.line([cx - bw * .5, cy - bh * .36, cx - bw * .5, cy + bh * .36], fill=G(230), width=10)
        for ox, oy in [(0.5, -0.27), (0.69, 0.18)]:
            d.ellipse([cx + bw * ox - 22, cy + bh * oy - 22, cx + bw * ox + 22, cy + bh * oy + 22], fill=A(255))
    elif cat == "sport":
        for i in range(9):
            y = h * 0.06 + i * 80 * k
            d.line([0, y, W, y + 140], fill=G(25 + i * 9), width=4)
        r = 170 * k
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=G(230), width=8)
        d.arc([cx - r * 1.9, cy - r, cx + r * 0.12, cy + r], -60, 60, fill=A(240), width=6)
        d.arc([cx - r * 0.12, cy - r, cx + r * 1.9, cy + r], 120, 240, fill=A(240), width=6)
    elif cat == "culture":
        fw, top = 150, h * (0.12 if story else 0.11)
        for i in range(-1, W // fw + 2):
            x = i * fw + 30
            d.rectangle([x, top, x + fw - 20, top + 200 * k], outline=G(150), width=5)
            for j in range(4):
                d.rectangle([x + 10 + j * 34, top - 40, x + 30 + j * 34, top - 18], fill=G(110))
                d.rectangle([x + 10 + j * 34, top + 200 * k + 18, x + 30 + j * 34, top + 200 * k + 40], fill=G(110))
        for j in range(5):
            a = -0.9 + j * 0.45
            d.line([cx, zone, cx + math.sin(a) * 900, zone - math.cos(a) * 900], fill=A(40), width=60)
    img.alpha_composite(layer)


def story_photo(slide, h):
    """Photo libre de droits (slide["image"]["url"]) recadrée en plein cadre pour la story ; None si absente ou illisible."""
    info = slide.get("image") or {}
    url = info.get("url") if isinstance(info, dict) else None
    if not url:
        return None
    try:
        import io, requests
        r = requests.get(url, timeout=25, headers={"User-Agent": "XIINewsBot/1.0 (https://github.com/Slade0290/xii-news)"})
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        sw, sh = im.size
        scale = max(W / sw, h / sh)
        im = im.resize((max(W, round(sw * scale)), max(h, round(sh * scale))), Image.LANCZOS)
        x, y = (im.size[0] - W) // 2, (im.size[1] - h) // 3
        im = im.crop((x, y, x + W, y + h))
        dark = Image.new("RGB", (W, h), (10, 12, 16))
        return Image.blend(im, dark, 0.25).convert("RGBA")
    except Exception as e:
        print(f"Photo ignorée ({url}) : {e}", file=sys.stderr)
        return None


def shade(img, start):
    w, h = img.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for y in range(h):
        t = y / h
        a = int(110 * (1 - t / 0.16)) if t < 0.16 else (int(228 * min(1, (t - start) / 0.38)) if t > start else 0)
        d.line([0, y, w, y], fill=(10, 12, 16, a))
    img.alpha_composite(layer)


def logo_mark(d, F, x, y, scale=1.0, color=INK):
    xf = F("Archivo.ttf", int(58 * scale), 900, 100)
    d.text((x, y), "XII", font=xf, fill=color)
    xw = d.textlength("XII", font=xf)
    nx = spaced(d, (x + xw + 22 * scale, y + 18 * scale), "NEWS", F("Archivo.ttf", int(26 * scale), 500, 125), color, 9 * scale)
    d.line([nx + 10, y + 32 * scale, nx + 70 * scale, y + 32 * scale], fill=hexc(RED), width=max(2, int(4 * scale)))


# ---------- mise en page du texte ----------

def text_block(d, F, items, accent, h, top_min, bottom, S):
    M, MAXW = 72, W - 144

    def height(it):
        k, p = it[0], it[1]
        if k == "kicker":
            return S["kicker"] + 34
        if k == "title":
            return len(p) * int(it[2].size * 1.04)
        if k == "stat":
            lab = wrap(d, p["label"], F("Archivo.ttf", S["statlabel"], 500), MAXW)
            return int(S["stat"] * 1.28) + int(S["statlabel"] * 1.2) * len(lab)
        if k == "list":
            lf = F("Archivo.ttf", S["list"], 500)
            return sum(int(S["list"] * 1.3) * len(wrap(d, r[1], lf, MAXW - 200)) + 18 for r in p)
        if k in ("para", "why"):
            return len(p) * int(it[2].size * 1.42)
        if k == "foot":
            return S["foot"] + 24
        return 0

    gap = S["gap"]
    total = sum(height(it) for it in items) + gap * (len(items) - 1)
    y = max(top_min, h - bottom - total)
    for it in items:
        k, p = it[0], it[1]
        if k == "kicker":
            f = F("Mono.ttf", S["kicker"], 600)
            tw = d.textlength(p, font=f)
            ph = S["kicker"] + 30
            d.rounded_rectangle([M, y, M + tw + 76, y + ph], radius=ph // 2, fill=(255, 255, 255, 34))
            d.ellipse([M + 22, y + ph / 2 - 8, M + 38, y + ph / 2 + 8], fill=hexc(accent))
            d.text((M + 52, y + 14), p, font=f, fill=INK)
        elif k == "title":
            f = it[2]
            for i, line in enumerate(p):
                d.text((M, y + i * int(f.size * 1.04)), line, font=f, fill=INK)
        elif k == "stat":
            d.text((M, y - 8), p["value"], font=F("Archivo.ttf", S["stat"], 900, 100), fill=hexc(accent))
            lf = F("Archivo.ttf", S["statlabel"], 500)
            for i, line in enumerate(wrap(d, p["label"], lf, MAXW)):
                d.text((M, y + int(S["stat"] * 1.28) + i * int(S["statlabel"] * 1.2)), line, font=lf, fill=INK + (205,))
        elif k == "list":
            lf, bf, yy = F("Archivo.ttf", S["list"], 500), F("Mono.ttf", int(S["list"] * 0.78), 600), y
            for r in p:
                d.text((M, yy + 6), r[0], font=bf, fill=hexc(accent))
                lines = wrap(d, r[1], lf, MAXW - 200)
                for i, line in enumerate(lines):
                    d.text((M + 200, yy + i * int(S["list"] * 1.3)), line, font=lf, fill=INK)
                yy += int(S["list"] * 1.3) * len(lines) + 18
        elif k == "para":
            f = it[2]
            for i, line in enumerate(p):
                d.text((M, y + i * int(f.size * 1.42)), line, font=f, fill=INK)
        elif k == "why":
            f = it[2]
            hh = len(p) * int(f.size * 1.42)
            d.rectangle([M, y + 6, M + 5, y + hh - 6], fill=hexc(accent))
            for i, line in enumerate(p):
                d.text((M + 30, y + i * int(f.size * 1.42)), line, font=f, fill=INK + (200,))
        elif k == "foot":
            d.text((M, y + 10), p, font=F("Mono.ttf", S["foot"], 600), fill=INK + (190,))
        y += height(it) + gap


STORY_SIZES = dict(title=100, title_small=84, kicker=30, stat=150, statlabel=38, list=40, body=42, why=36, foot=28, gap=32)
POST_SIZES = dict(title=74, title_small=64, kicker=24, stat=112, statlabel=30, list=32, body=33, why=29, foot=24, gap=24)


def render_actu(slide, date_label, F, out, n, total, story):
    h = STORY_H if story else POST_H
    S = STORY_SIZES if story else POST_SIZES
    cat = slide.get("cat", "watch")
    name, accent = CATS.get(cat, CATS["watch"])
    M, MAXW = 72, W - 144

    photo = story_photo(slide, h) if story else None
    if photo is not None:
        img = photo
        shade(img, 0.22)
    else:
        img = base_bg(h)
        motif(img, cat, accent, n * 97 + 13, story)
        red_arc(img, -W * 0.1, h * 1.02, W * 0.9, 285, 335, width=10, alpha=190)
        shade(img, 0.36 if story else 0.30)
    img = img.convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")

    # en-tête
    if story:
        logo_mark(d, F, M, 80)
        df = F("Mono.ttf", 24, 500)
        dl = date_label.upper()
        d.text((W - M - d.textlength(dl, font=df), 100), dl, font=df, fill=INK + (190,))
        credit = (slide.get("image") or {}).get("credit") if photo is not None else None
        if credit:
            cf = F("Mono.ttf", 20, 500)
            ct = ("Photo : " + credit)[:70]
            d.text((W - M - d.textlength(ct, font=cf), 140), ct, font=cf, fill=INK + (170,))
    else:
        logo_mark(d, F, M, 52, 0.9)
        cf = F("Mono.ttf", 26, 600)
        ct = f"{n + 1:02d}/{total:02d}"
        d.text((W - M - d.textlength(ct, font=cf), 66), ct, font=cf, fill=hexc(RED))

    big = F("Archivo.ttf", S["title"], 900, 100)
    tl = wrap(d, slide.get("title", "").upper(), big, MAXW)
    if len(tl) > 3:
        big = F("Archivo.ttf", S["title_small"], 900, 100)
        tl = wrap(d, slide.get("title", "").upper(), big, MAXW)
    items = [("kicker", f"{name} · {slide.get('kicker', '')}".upper()), ("title", tl, big)]
    if slide.get("stat"):
        items.append(("stat", slide["stat"]))
    if slide.get("list"):
        items.append(("list", slide["list"]))
    if slide.get("body"):
        bf = F("Archivo.ttf", S["body"], 450)
        items.append(("para", wrap(d, slide["body"], bf, MAXW), bf))
    if slide.get("why"):
        wf = F("Archivo.ttf", S["why"], 400)
        items.append(("why", wrap(d, slide["why"], wf, MAXW - 30), wf))
    src = slide.get("source")
    if src:
        dom = domain(slide.get("url", ""))
        items.append(("foot", f"SOURCE : {src.upper()}" + (f" · {dom}" if dom and not story else "")))

    if story:
        text_block(d, F, items, accent, h, 250, 210, S)
        # renvoi vers le post
        bar_y = h - 150
        d.rounded_rectangle([M, bar_y, W - M, bar_y + 84], radius=42, fill=hexc(RED, 235))
        bf = F("Archivo.ttf", 31, 700)
        t = "Détails et sources dans le post du jour →"
        d.text(((W - d.textlength(t, font=bf)) / 2, bar_y + 23), t, font=bf, fill=INK)
    else:
        text_block(d, F, items, accent, h, 150, 70, S)
    img.save(out, "JPEG", quality=88, optimize=True, progressive=True)


def render_cover(picked, date_label, F, out, logo_path):
    """Première image du carrousel : le sommaire des 12 infos, sur fond clair comme la photo de profil."""
    h = POST_H
    img = Image.new("RGB", (W, h), (233, 236, 240))
    logo = Image.open(logo_path).convert("RGB").resize((h, h), Image.LANCZOS)
    logo = logo.crop(((h - W) // 2, 0, (h - W) // 2 + W, h))
    img = Image.blend(logo, Image.new("RGB", (W, h), (233, 236, 240)), 0.93)
    d = ImageDraw.Draw(img, "RGBA")
    d.arc([W * 0.62, -h * 0.55, W * 1.5, h * 0.20], 110, 170, fill=hexc(RED), width=12)
    M = 72
    logo_mark(d, F, M, 50, 2.2, BLACK)
    d.text((M, 210), date_label.upper(), font=F("Mono.ttf", 28, 600), fill=hexc(RED))
    d.text((M, 252), "LE MONDE EN 12 INFOS", font=F("Archivo.ttf", 30, 800, 110), fill=BLACK)
    d.line([M, 305, W - M, 305], fill=BLACK + (60,), width=2)

    y0, bottom = 328, h - 110
    lf = F("Mono.ttf", 21, 600)
    col = M + 300
    chosen = None
    for size in (31, 29, 27, 25):
        tf = F("Archivo.ttf", size, 650)
        rows = [wrap(d, s.get("title", ""), tf, W - M - col)[:2] for s in picked]
        lh = int(size * 1.22)
        tot = sum(len(r) * lh for r in rows) + 16 * len(rows)
        chosen = (tf, rows, lh)
        if y0 + tot <= bottom:
            break
    tf, rows, lh = chosen
    y = y0
    for i, (s, lines) in enumerate(zip(picked, rows)):
        name, accent = CATS.get(s.get("cat"), CATS["watch"])
        d.text((M, y + 4), f"{i + 1:02d}", font=lf, fill=hexc(RED))
        d.ellipse([M + 44, y + 9, M + 56, y + 21], fill=hexc(accent if s.get("cat") != "breaking" else RED))
        d.text((M + 68, y + 4), name.upper(), font=lf, fill=BLACK + (150,))
        for j, line in enumerate(lines):
            d.text((col, y + j * lh), line, font=tf, fill=BLACK)
        y += len(lines) * lh + 16
    d.rectangle([0, h - 92, W, h], fill=BLACK)
    t = "Swipe →  chaque info avec sa source"
    bf = F("Archivo.ttf", 30, 650)
    d.text((M, h - 66), t, font=bf, fill=INK)
    d.text((W - M - d.textlength("@xii.news", font=bf), h - 66), "@xii.news", font=bf, fill=INK + (200,))
    img.save(out, "JPEG", quality=90, optimize=True, progressive=True)


# ---------- sélection et légende ----------

def pick12(slides):
    by_cat = {}
    for s in slides:
        if s.get("cat") in ORDER:
            by_cat.setdefault(s["cat"], []).append(s)
    picked = [by_cat[c][0] for c in ORDER if by_cat.get(c)]
    used = {id(s) for s in picked}
    for depth in (1, 2, 3):
        for c in FILL_FROM:
            if len(picked) >= 12:
                break
            group = by_cat.get(c, [])
            if len(group) > depth and id(group[depth]) not in used:
                picked.append(group[depth]); used.add(id(group[depth]))
    picked = picked[:12]
    picked.sort(key=lambda s: ORDER.index(s["cat"]))
    return picked


def caption(picked, date_label):
    head = [f"XII NEWS · {date_label}", "Le monde en 12 infos ce matin. Swipe 👉", ""]
    tail = ["", "🔗 Les liens de toutes les sources sont en commentaire",
            "📲 Version longue : lien en bio",
            "🤖 Brief préparé avec l'aide d'une IA, chaque info est sourcée.", "",
            "#xiinews #actu #revuedepresse #geopolitique #tech #IA #robotique #espace #science #jeuxvideo #sport #cinema"]

    def build(long):
        body = []
        for i, s in enumerate(picked, 1):
            name = CATS[s["cat"]][0].upper()
            src = s.get("source", "")
            dom = domain(s.get("url", ""))
            src_txt = f"{src} ({dom})" if long and dom else src
            if long:
                body += [f"{i:02d} · {name} : {s.get('title', '')}", f"   Source : {src_txt}"]
            else:
                body.append(f"{i:02d} · {s.get('title', '')} [{src_txt}]")
        return "\n".join(head + body + tail)

    for long in (True, False):
        c = build(long)
        if len(c) <= CAPTION_MAX:
            return c
    return c[:CAPTION_MAX - 1] + "…"


def links_comments(picked):
    """Commentaire(s) épinglés sous le post : le lien complet de chaque source (2 200 caractères max chacun)."""
    lines = [f"{i:02d} · {s.get('source', '')} : {s.get('url', '')}" for i, s in enumerate(picked, 1) if s.get("url")]
    out, cur = [], "🔗 Sources du jour"
    for ln in lines:
        if len(cur) + 1 + len(ln) > CAPTION_MAX:
            out.append(cur); cur = "🔗 Sources (suite)"
        cur += "\n" + ln
    out.append(cur)
    return out


def main():
    src, outdir, logo_path = sys.argv[1], sys.argv[2], sys.argv[3]
    data = json.load(open(src, encoding="utf-8"))
    date_label = data.get("dateLabel", "")
    picked = pick12(data["slides"])
    if len(picked) < 12:
        print(f"ATTENTION : seulement {len(picked)} infos disponibles", file=sys.stderr)
    os.makedirs(outdir, exist_ok=True)
    F = fonts()

    carousel = ["post_01.jpg"]
    render_cover(picked, date_label, F, os.path.join(outdir, "post_01.jpg"), logo_path)
    stories = []
    for i, s in enumerate(picked):
        pn = f"post_{i + 2:02d}.jpg"
        render_actu(s, date_label, F, os.path.join(outdir, pn), i, len(picked), story=False)
        carousel.append(pn)
        sn = f"story_{i + 1:02d}.jpg"
        render_actu(s, date_label, F, os.path.join(outdir, sn), i, len(picked), story=True)
        stories.append(sn)

    cap = caption(picked, date_label)
    open(os.path.join(outdir, "caption.txt"), "w", encoding="utf-8").write(cap)
    comments = links_comments(picked)
    open(os.path.join(outdir, "commentaire_sources.txt"), "w", encoding="utf-8").write("\n\n".join(comments))
    manifest = {"dateLabel": date_label, "carousel": carousel, "stories": stories, "caption": cap, "comments": comments,
                "sources": [{"title": s.get("title"), "source": s.get("source"), "url": s.get("url")} for s in picked]}
    json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(carousel)} images de carrousel, {len(stories)} stories, légende de {len(cap)} caractères -> {outdir}")


if __name__ == "__main__":
    main()
