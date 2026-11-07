#!/usr/bin/env python3
"""
1 Lombard Street journal builder.

Writers add a row to the shared Google Sheet and write the post in a Google Doc.
This script reads the sheet, pulls each published Doc, cleans it up and builds
static pages, so every post is fast and fully readable by search engines and AI tools.

  python3 scripts/journal.py            fetch from Google, then build
  python3 scripts/journal.py --offline  rebuild from data/journal.json only

Only the Python standard library is needed; Pillow is used for images if installed.
"""
import csv, datetime, html, io, json, math, os, re, sys, urllib.parse, urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = json.load(open(os.path.join(ROOT, "scripts", "journal-config.json")))
SITE_URL = CONF["site_url"].rstrip("/") + "/"
TPL_DIR = os.path.join(ROOT, "scripts", "templates")
DATA = os.path.join(ROOT, "data", "journal.json")
IMG_DIR = os.path.join(ROOT, "images", "journal")
POST_DIR = os.path.join(ROOT, "post")
UA = {"User-Agent": "Mozilla/5.0 (1 Lombard Street journal builder)"}

try:
    from PIL import Image, ImageOps
except ImportError:  # images are then saved as downloaded
    Image = None


# ---------------------------------------------------------------- helpers
def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def slugify(t):
    t = html.unescape(t).lower().replace("&", " and ").replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:80]


def doc_id(link):
    m = re.search(r"/document/d/([\w-]+)", link or "")
    return m.group(1) if m else None


def drive_direct(link):
    """Turn a Google Drive share link into a direct download link."""
    m = re.search(r"/file/d/([\w-]+)", link) or re.search(r"[?&]id=([\w-]+)", link)
    return f"https://drive.google.com/uc?export=download&id={m.group(1)}" if m and "drive.google" in link else link


def esc(t):
    return html.escape(t or "", quote=True)


def save_image(url, name, max_w=2000):
    """Download an image into images/journal and return its site path."""
    os.makedirs(IMG_DIR, exist_ok=True)
    data = get(drive_direct(url), binary=True)
    if Image:
        try:
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
            im.thumbnail((max_w, max_w))
            path = os.path.join(IMG_DIR, name + ".jpg")
            im.save(path, quality=80, optimize=True, progressive=True)
            return "images/journal/" + name + ".jpg"
        except Exception:
            pass
    ext = ".png" if data[:4] == b"\x89PNG" else ".jpg"
    open(os.path.join(IMG_DIR, name + ext), "wb").write(data)
    return "images/journal/" + name + ext


# ---------------------------------------------------------------- Google Doc -> clean HTML
class DocCleaner(HTMLParser):
    """Keeps headings, paragraphs, lists, links, bold/italic, quotes and images. Drops Google's styling."""
    KEEP = {"p", "h1", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "table", "tr", "td", "th", "br"}

    def __init__(self, bold, italic):
        super().__init__(convert_charrefs=True)
        self.bold, self.italic = bold, italic
        self.out, self.stack, self.imgs, self.in_style, self.skip = [], [], [], False, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.skip:
            self.stack.append(None); return
        if tag in ("style", "head", "title"):
            self.in_style = True; return
        if tag == "img":
            self.imgs.append(a.get("src", "")); self.out.append(f"\x00IMG{len(self.imgs) - 1}\x00"); return
        if tag == "a" and a.get("href"):
            href = a["href"]
            q = urllib.parse.urlparse(href)
            if q.netloc.endswith("google.com") and q.path == "/url":
                href = urllib.parse.parse_qs(q.query).get("q", [href])[0]
            if href.startswith("#"):
                self.stack.append(None); return
            self.out.append(f'<a href="{esc(href)}">'); self.stack.append("a"); return
        if tag == "span":
            cls = set((a.get("class") or "").split())
            style = a.get("style", "")
            b = bool(cls & self.bold) or "font-weight:700" in style
            i = bool(cls & self.italic) or "font-style:italic" in style
            opened = []
            if b: self.out.append("<strong>"); opened.append("strong")
            if i: self.out.append("<em>"); opened.append("em")
            self.stack.append(opened); return
        if tag == "p" and ({"title", "subtitle"} & set((a.get("class") or "").split())):
            self.skip = True; self.stack.append("__skip"); return
        if tag in self.KEEP:
            t = {"h1": "h2", "h2": "h2", "h3": "h3", "h4": "h3"}.get(tag, tag)
            self.out.append(f"<{t}>"); self.stack.append(t)
        else:
            self.stack.append(None)

    def handle_endtag(self, tag):
        if tag in ("style", "head", "title"):
            self.in_style = False; return
        if tag in ("img", "br") or not self.stack:
            return
        top = self.stack.pop()
        if top == "__skip":
            self.skip = False; return
        if self.skip:
            return
        if isinstance(top, list):
            self.out.extend(f"</{t}>" for t in reversed(top))
        elif top:
            self.out.append(f"</{top}>")

    def handle_data(self, d):
        if not self.in_style and not self.skip:
            self.out.append(esc(d).replace("\xa0", " "))


def plain(h):
    h = re.sub(r"</(p|h2|h3|li|blockquote|figure)>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


def clean_doc(raw):
    css = " ".join(re.findall(r"<style[^>]*>(.*?)</style>", raw, re.S))
    bold = set(re.findall(r"\.(c\d+)\{[^}]*font-weight:700", css))
    italic = set(re.findall(r"\.(c\d+)\{[^}]*font-style:italic", css))
    body = re.search(r"<body[^>]*>(.*)</body>", raw, re.S)
    p = DocCleaner(bold, italic); p.feed(body.group(1) if body else raw)
    out = "".join(p.out)
    out = re.sub(r"<(p|h2|h3|li)>\s*</\1>", "", out)                 # empty blocks
    out = re.sub(r"</strong>\s*<strong>", " ", out).replace("<strong></strong>", "")
    out = re.sub(r"<p>\s*(\x00IMG\d+\x00)\s*</p>", r"\1", out)
    return out.strip(), p.imgs


# ---------------------------------------------------------------- fetch from Google
def fetch():
    sheet = CONF.get("sheet_csv") or ""
    if not sheet:
        print("No sheet configured in scripts/journal-config.json; keeping existing posts.")
        return load()
    m = re.search(r"/spreadsheets/d/([\w-]+)", sheet)
    gid = re.search(r"[#&?]gid=(\d+)", sheet)
    if m and "export?format=csv" not in sheet and "output=csv" not in sheet:
        sheet = f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv" + (f"&gid={gid.group(1)}" if gid else "")
    rows = list(csv.DictReader(io.StringIO(get(sheet))))
    old = {p["slug"]: p for p in load()}
    posts = []
    for r in rows:
        r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
        if r.get("status", "").lower() not in ("publish", "published", "live"):
            continue
        title = r.get("title")
        if not title:
            continue
        slug = slugify(r.get("slug") or title)
        try:
            date = datetime.date.fromisoformat(r.get("date") or "").isoformat()
        except ValueError:
            date = old.get(slug, {}).get("date") or datetime.date.today().isoformat()
        post = {"slug": slug, "title": title, "date": date, "author": r.get("author") or "1 Lombard Street",
                "summary": r.get("summary", ""), "category": r.get("category", ""), "doc": r.get("google doc", ""),
                "image_src": r.get("hero image", ""), "image": old.get(slug, {}).get("image", ""), "body": ""}
        try:
            if post["image_src"] and post["image_src"] != old.get(slug, {}).get("image_src"):
                post["image"] = save_image(post["image_src"], slug)
            did = doc_id(post["doc"])
            if did:
                body, imgs = clean_doc(get(f"https://docs.google.com/document/d/{did}/export?format=html"))
                lead = re.match(r"\s*<h2>(.*?)</h2>", body)
                if lead and plain(lead.group(1)).lower().strip(" .") == html.unescape(title).lower().strip(" ."):
                    body = body[lead.end():]
                for i, src in enumerate(imgs):
                    try:
                        path = save_image(src, f"{slug}-{i + 1}", 1600)
                        body = body.replace(f"\x00IMG{i}\x00", f'<figure><img src="../{path}" alt="" loading="lazy"></figure>')
                    except Exception as e:
                        print("  image skipped:", e); body = body.replace(f"\x00IMG{i}\x00", "")
                post["body"] = body
            elif r.get("body"):
                post["body"] = "".join(f"<p>{esc(x)}</p>" for x in re.split(r"\n\s*\n", r["body"]) if x.strip())
            if not post["body"] and slug in old:
                post["body"] = old[slug]["body"]
        except Exception as e:  # keep the last good version if Google is unreachable
            print(f"  {slug}: {e}")
            if slug in old:
                post = {**old[slug], **{k: post[k] for k in ("title", "summary", "category", "author", "date")}}
        if not post["body"]:
            print(f"  {slug}: no content yet, skipped"); continue
        if not post["summary"]:
            txt = plain(post["body"]); post["summary"] = (txt[:155].rsplit(" ", 1)[0] + "…") if len(txt) > 155 else txt
        if not post["image"]:
            first = re.search(r'<img src="\.\./([^"]+)"', post["body"])
            post["image"] = first.group(1) if first else "images/photos/dome-l.jpg"
        posts.append(post)
        print("  published:", slug)
    return posts


def load():
    return json.load(open(DATA)) if os.path.exists(DATA) else []


# ---------------------------------------------------------------- render
def fmt_date(d):
    return datetime.date.fromisoformat(d).strftime("%-d %B %Y")


def read_time(body):
    return max(1, math.ceil(len(re.sub(r"<[^>]+>", " ", body).split()) / 220))


def card(p, prefix):
    cat = f'<span class="label">{esc(p["category"])}</span>' if p["category"] else f'<span class="label">{fmt_date(p["date"])}</span>'
    return (f'<a class="tile reveal j-card" href="{prefix}post/{p["slug"]}.html"><div class="img"><img src="{prefix}{p["image"]}" alt="" loading="lazy"></div>'
            f'<div class="meta">{cat}<h3>{esc(p["title"])}</h3><p>{esc(p["summary"])}</p></div></a>')


def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "</script>"


def render(posts):
    posts = sorted(posts, key=lambda p: p["date"], reverse=True)
    os.makedirs(POST_DIR, exist_ok=True)
    tpl_post = open(os.path.join(TPL_DIR, "post.html")).read()
    tpl_index = open(os.path.join(TPL_DIR, "journal.html")).read()
    rid = SITE_URL + "#restaurant"
    keep = set()
    for i, p in enumerate(posts):
        url = f"{SITE_URL}post/{p['slug']}"
        img = SITE_URL + p["image"]
        more = [q for q in posts if q is not p][:3]
        more_html = ('<section class="sec stone"><div class="wrap"><p class="label label-rule reveal">From the journal</p>'
                     '<h2 class="h2 reveal">Keep reading</h2><div class="cards">' + "".join(card(q, "../") for q in more) + "</div></div></section>") if more else ""
        schema = {"@context": "https://schema.org", "@graph": [
            {"@type": "BlogPosting", "@id": url + "#article", "headline": html.unescape(p["title"]), "description": html.unescape(p["summary"]),
             "image": img, "datePublished": p["date"], "dateModified": p["date"], "inLanguage": "en-GB",
             "author": {"@type": "Person" if p["author"] != "1 Lombard Street" else "Organization", "name": p["author"]},
             "publisher": {"@type": "Organization", "@id": rid, "name": "1 Lombard Street", "logo": {"@type": "ImageObject", "url": SITE_URL + "assets/img/logo-dark.png"}},
             "mainEntityOfPage": url, "articleSection": p["category"] or "Journal", "about": {"@id": rid},
             "wordCount": len(re.sub(r"<[^>]+>", " ", p["body"]).split())},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
                {"@type": "ListItem", "position": 2, "name": "Journal", "item": SITE_URL + "journal.html"},
                {"@type": "ListItem", "position": 3, "name": html.unescape(p["title"]), "item": url}]}]}
        page = (tpl_post.replace("{{TITLE}}", esc(html.unescape(p["title"])) + " | 1 Lombard Street")
                .replace("{{DESC}}", esc(html.unescape(p["summary"])))
                .replace("{{CANONICAL}}", url).replace("{{OG_IMAGE}}", img).replace("{{JSONLD}}", ld(schema))
                .replace("{{HERO}}", "../" + p["image"]).replace("{{H1}}", esc(html.unescape(p["title"])))
                .replace("{{META}}", f'{fmt_date(p["date"])} · {esc(p["author"])} · {read_time(p["body"])} min read')
                .replace("{{LABEL}}", esc(p["category"] or "Journal"))
                .replace("{{BODY}}", p["body"]).replace("{{MORE}}", more_html))
        open(os.path.join(POST_DIR, p["slug"] + ".html"), "w").write(page)
        keep.add(p["slug"] + ".html")
    for f in os.listdir(POST_DIR):  # posts taken down in the sheet
        if f.endswith(".html") and f not in keep:
            os.remove(os.path.join(POST_DIR, f))

    grid = ('<div class="cards j-grid">' + "".join(card(p, "") for p in posts) + "</div>") if posts else \
        '<p class="big reveal" style="text-align:center">New stories from the hall are on their way.</p>'
    idx_schema = {"@context": "https://schema.org", "@type": "Blog", "@id": SITE_URL + "journal.html#blog", "name": "1 Lombard Street Journal",
                  "url": SITE_URL + "journal.html", "publisher": {"@id": rid}, "inLanguage": "en-GB",
                  "blogPost": [{"@type": "BlogPosting", "headline": html.unescape(p["title"]), "url": f"{SITE_URL}post/{p['slug']}", "datePublished": p["date"]} for p in posts[:20]]}
    open(os.path.join(ROOT, "journal.html"), "w").write(tpl_index.replace("{{GRID}}", grid).replace("{{JSONLD}}", ld(idx_schema)))

    # sitemap: replace the journal entries
    sm_path = os.path.join(ROOT, "sitemap.xml")
    if os.path.exists(sm_path):
        sm = open(sm_path).read()
        sm = re.sub(r"<url><loc>[^<]*(?:/post/|/journal)[^<]*</loc>.*?</url>", "", sm)
        add = f"<url><loc>{SITE_URL}journal.html</loc><lastmod>{posts[0]['date'] if posts else datetime.date.today().isoformat()}</lastmod><priority>0.7</priority></url>"
        add += "".join(f"<url><loc>{SITE_URL}post/{p['slug']}</loc><lastmod>{p['date']}</lastmod><priority>0.6</priority></url>" for p in posts)
        open(sm_path, "w").write(sm.replace("</urlset>", add + "</urlset>"))
    # llms.txt: list the latest posts
    lp = os.path.join(ROOT, "llms.txt")
    if os.path.exists(lp):
        t = open(lp).read().split("\n## Journal")[0].rstrip() + "\n"
        if posts:
            t += "\n## Journal\n" + "".join(f"- [{html.unescape(p['title'])}]({SITE_URL}post/{p['slug']}): {html.unescape(p['summary'])}\n" for p in posts[:30])
        open(lp, "w").write(t)
    print(f"Built {len(posts)} post(s).")


def main():
    posts = load() if "--offline" in sys.argv else fetch()
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    json.dump(posts, open(DATA, "w"), indent=1, ensure_ascii=False)
    render(posts)


if __name__ == "__main__":
    main()
