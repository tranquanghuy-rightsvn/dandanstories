#!/usr/bin/env python3
"""
Build site tinh DanDan Stories tu data/ + templates/ + static/ (chi dung Python stdlib).

Quy uoc (chot o GAS.md muc VIII):
  data/website.json         cai dat website (CMS tab "Cai dat website")
  data/categories.json      danh muc [{slug, name, description, order}]
  data/posts.json           index nhe moi bai (khong content)
  data/posts/<slug>.json    noi dung day du 1 bai ({"slug", "content_html"})
  data/pages.json           trang tinh, kem noi dung
  templates/*.html          thiet ke (placeholder {{TOKEN}}), sua tay
  static/**                 CSS/JS/anh/vendor/admin - copy nguyen vao html/

Output: html/ (XOA SACH va sinh lai moi lan build - gitignore, khong sua tay):
  html/index.html                         trang chu
  html/<slug>/index.html                  bai viet, danh muc, trang tinh (URL "/<slug>/")
  html/<danh-muc>/trang-<n>/index.html    phan trang danh muc
  html/tim-kiem/index.html + search-index.json
  html/404.html, sitemap.xml, feed.xml, robots.txt

Vi html/ luon sinh lai tu dau, khong co file "mo coi" sau khi xoa bai qua CMS.

Chay:
  python3 scripts/build.py           # du lieu that (data/)
  python3 scripts/build.py --demo    # du lieu mau (demo/data + demo/static) de xem giao dien
"""
import argparse
import hashlib
import html as htmllib
import json
import math
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "html"

POSTS_PER_PAGE = 12
# Phai khop RESERVED_SLUGS trong gas/Code.js (gas/ khong nam trong git nen 2 cho nay KHONG tu
# dong bo duoc - sua 1 ben thi sua luon ben kia).
RESERVED_SLUGS = {"images", "assets", "vendor", "admin", "tim-kiem", "trang", "feed", "sitemap", "404"}

DEFAULT_WEBSITE = {
    "site_name": "DanDan Stories",
    "tagline": "Những câu chuyện nhỏ, ở lại thật lâu.",
    "description": "DanDan Stories - nơi kể những câu chuyện đời thường, ký ức, hành trình và cảm xúc.",
    "domain_url": "https://dandanstories.com/",
    "lang": "vi",
    "author_default": "DanDan",
    "footer_about": "Góc nhỏ để kể và đọc những câu chuyện đời thường - chậm rãi, chân thật và ấm áp.",
    "contact_email": "",
    "contact_phone": "",
    "contact_address": "",
    "facebook": "",
    "youtube": "",
    "tiktok": "",
    "instagram": "",
    "ga_id": "",
    "head_html": "",
    "ads_txt": "",
    "logo": "",
    "favicon": "",
    "og_image": "",
}


# ---------- tien ich ----------

def esc(value):
    return htmllib.escape(str(value or ""), quote=True)


def load_json(path, default):
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else default


def render(tpl, mapping):
    """Thay {{TOKEN}} trong 1 LUOT duy nhat - noi dung bai viet lo chua chuoi "{{...}}" se
    khong bi thay nham o luot sau (replace() tuan tu thi co)."""
    missing = set()

    def sub(m):
        key = m.group(1)
        if key not in mapping:
            missing.add(key)
            return m.group(0)
        value = mapping[key]
        return value if isinstance(value, str) else str(value)

    out = re.sub(r"\{\{([A-Z0-9_]+)\}\}", sub, tpl)
    if missing:
        print("WARN: placeholder chua duoc thay: %s" % ", ".join(sorted(missing)))
    return out


def load_template(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def file_version(path):
    if not path.exists():
        return "0"
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]


def write_page(rel_dir, html):
    """rel_dir: "" (trang chu) hoac "slug" hoac "slug/trang-2" -> html/<rel_dir>/index.html."""
    target = OUT / rel_dir / "index.html" if rel_dir else OUT / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")


def url_of(slug):
    return "/%s/" % slug


def asset_url(path):
    """Duong dan anh trong data luu dang tuong doi "images/..." (khong "/" dau)."""
    if not path:
        return ""
    if re.match(r"^https?://", path):
        return path
    return "/" + path.lstrip("/")


def absolute(domain, path):
    if not path:
        return ""
    if re.match(r"^https?://", path):
        return path
    return domain.rstrip("/") + "/" + path.lstrip("/")


def parse_date(value):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?)?", str(value or ""))
    if not m:
        return None
    parts = [int(x) if x else 0 for x in m.groups()]
    return datetime(*parts)


def date_display(value):
    d = parse_date(value)
    return d.strftime("%d/%m/%Y") if d else ""


def date_iso(value):
    """Du lieu luu gio Viet Nam (+07:00) - giu nguyen neu da co offset, thieu thi them."""
    s = str(value or "")
    if not s:
        return ""
    if re.search(r"(Z|[+-]\d{2}:\d{2})$", s):
        return s
    if "T" not in s:
        s += "T00:00:00"
    return s + "+07:00"


def rfc822(value):
    d = parse_date(value)
    if not d:
        return ""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return "%s, %02d %s %04d %02d:%02d:%02d +0700" % (
        days[d.weekday()], d.day, months[d.month - 1], d.year, d.hour, d.minute, d.second)


def strip_tags(html):
    text = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return htmllib.unescape(re.sub(r"\s+", " ", text)).strip()


def reading_minutes(html):
    words = len(strip_tags(html).split())
    return max(1, int(math.ceil(words / 200.0)))


def prepare_content(html):
    """Them loading=lazy/decoding=async cho anh trong noi dung (anh dau trang da la cover)."""
    def fix(m):
        tag = m.group(0)
        if "loading=" not in tag:
            tag = tag[:-1].rstrip("/").rstrip() + ' loading="lazy" decoding="async">'
        return tag
    return re.sub(r"<img\b[^>]*>", fix, html or "")


def json_ld(obj):
    data = json.dumps(obj, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return '  <script type="application/ld+json">\n%s\n  </script>' % data


def initial(name):
    name = (name or "").strip()
    return esc(name[:1].upper()) if name else "D"


# ---------- doc du lieu ----------

def load_data(data_dir):
    website = dict(DEFAULT_WEBSITE)
    website.update({k: v for k, v in load_json(data_dir / "website.json", {}).items() if v is not None})
    if not website.get("domain_url", "").endswith("/"):
        website["domain_url"] = website.get("domain_url", "") + "/"

    categories = [c for c in load_json(data_dir / "categories.json", []) if c.get("slug")]
    categories.sort(key=lambda c: (float(c.get("order") or 0), c.get("name", "")))

    posts = []
    for meta in load_json(data_dir / "posts.json", []):
        if meta.get("draft"):
            continue
        slug = meta.get("slug", "")
        if not slug or slug in RESERVED_SLUGS:
            print("WARN: bo qua bai co slug khong hop le: %r" % slug)
            continue
        detail = load_json(data_dir / "posts" / ("%s.json" % slug), None)
        if detail is None:
            print("WARN: thieu data/posts/%s.json - bo qua bai '%s'" % (slug, meta.get("title")))
            continue
        post = dict(meta)
        post["content_html"] = detail.get("content_html", "")
        posts.append(post)
    posts.sort(key=lambda p: str(p.get("date", "")), reverse=True)

    pages = [p for p in load_json(data_dir / "pages.json", []) if p.get("slug")]
    pages.sort(key=lambda p: (float(p.get("order") or 0), p.get("title", "")))
    return website, categories, posts, pages


# ---------- khoi dung chung ----------

class Site(object):
    def __init__(self, website, categories, posts, pages):
        self.website = website
        self.categories = categories
        self.cat_by_slug = {c["slug"]: c for c in categories}
        self.posts = posts
        self.pages = pages
        self.domain = website["domain_url"]
        self.css_version = file_version(OUT / "assets/css/style.css")
        self.js_version = file_version(OUT / "assets/js/main.js")
        self.tpl_head = load_template("partials/head.html")
        self.tpl_header = load_template("partials/header.html")
        self.tpl_footer = load_template("partials/footer.html")
        self.header_html = self._header()
        self.footer_html = self._footer()

    # --- head ---
    def head(self, title, description, canonical_path, og_type="website", og_image="",
             keywords="", extra_meta="", ld=None, robots="index, follow, max-image-preview:large", og_title=None):
        w = self.website
        default_og = w.get("og_image") or ""
        image = og_image or default_og
        ga = w.get("ga_id", "").strip()
        analytics = ""
        if re.match(r"^G-[A-Z0-9]+$", ga):
            analytics = (
                '  <script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>\n'
                "  <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                "gtag('js',new Date());gtag('config','%s');</script>" % (ga, ga))
        return render(self.tpl_head, {
            "TITLE": esc(title),
            "OG_TITLE": esc(og_title if og_title is not None else title),
            "DESCRIPTION": esc(description),
            "KEYWORDS": esc(keywords),
            "ROBOTS": robots,
            "CANONICAL": esc(self.domain.rstrip("/") + canonical_path),
            "OG_LOCALE": "vi_VN" if w.get("lang", "vi") == "vi" else esc(w.get("lang")),
            "OG_TYPE": og_type,
            "SITE_NAME": esc(w["site_name"]),
            "OG_IMAGE": esc(absolute(self.domain, image)) if image else "",
            "EXTRA_META": extra_meta,
            "FAVICON": esc(asset_url(w.get("favicon")) or "/assets/favicon.svg"),
            "CSS_VERSION": self.css_version,
            "JSON_LD": "\n".join(json_ld(x) for x in (ld or [])),
            "ANALYTICS": analytics,
            # Ma chen <head> tuy y do admin nhap (AdSense, Search Console...) - ghi RAW, chi
            # admin moi sua duoc (GAS.md muc VI-B).
            "HEAD_HTML": w.get("head_html", ""),
        })

    # --- header / footer ---
    def _header(self):
        w = self.website
        if w.get("logo"):
            brand = '<img src="%s" alt="%s" height="40">' % (esc(asset_url(w["logo"])), esc(w["site_name"]))
        else:
            brand = '<span class="brand-mark" aria-hidden="true">%s</span><span class="brand-name">%s</span>' % (
                initial(w["site_name"]), esc(w["site_name"]))
        items = ['          <li><a href="%s">%s</a></li>' % (url_of(c["slug"]), esc(c["name"])) for c in self.categories]
        items += ['          <li><a href="%s">%s</a></li>' % (url_of(p["slug"]), esc(p["title"]))
                  for p in self.pages if p.get("show_in_menu")]
        return render(self.tpl_header, {
            "SITE_NAME": esc(w["site_name"]),
            "BRAND": brand,
            "NAV_ITEMS": "\n".join(items),
        })

    def _footer(self):
        w = self.website
        cats = "\n".join('          <li><a href="%s">%s</a></li>' % (url_of(c["slug"]), esc(c["name"]))
                         for c in self.categories) or '          <li class="muted">Đang cập nhật</li>'
        pages = ['          <li><a href="%s">%s</a></li>' % (url_of(p["slug"]), esc(p["title"])) for p in self.pages]
        pages.append('          <li><a href="/tim-kiem/">Tìm kiếm</a></li>')
        contact = []
        if w.get("contact_email"):
            contact.append('          <li><span>Email</span><a href="mailto:%s">%s</a></li>' % (esc(w["contact_email"]), esc(w["contact_email"])))
        if w.get("contact_phone"):
            tel = re.sub(r"[^\d+]", "", w["contact_phone"])
            contact.append('          <li><span>Điện thoại</span><a href="tel:%s">%s</a></li>' % (esc(tel), esc(w["contact_phone"])))
        if w.get("contact_address"):
            contact.append('          <li><span>Địa chỉ</span>%s</li>' % esc(w["contact_address"]))
        if not contact:
            contact.append('          <li class="muted">Thông tin liên hệ đang được cập nhật.</li>')
        socials = []
        for key, label in (("facebook", "Facebook"), ("youtube", "YouTube"), ("tiktok", "TikTok"), ("instagram", "Instagram")):
            if w.get(key):
                socials.append('          <a href="%s" target="_blank" rel="noopener" aria-label="%s">%s</a>' % (esc(w[key]), label, label))
        social_html = '        <div class="socials">\n%s\n        </div>' % "\n".join(socials) if socials else ""
        return render(self.tpl_footer, {
            "SITE_NAME": esc(w["site_name"]),
            "FOOTER_ABOUT": esc(w.get("footer_about", "")),
            "SOCIAL_LINKS": social_html,
            "FOOTER_CATEGORIES": cats,
            "FOOTER_PAGES": "\n".join(pages),
            "FOOTER_CONTACT": "\n".join(contact),
            "YEAR": str(datetime.now().year),
            "JS_VERSION": self.js_version,
        })

    def shell(self, tpl_name, head_html, mapping):
        base = {
            "LANG": esc(self.website.get("lang", "vi")),
            "HEAD": head_html,
            "HEADER": self.header_html,
            "FOOTER": self.footer_html,
        }
        base.update(mapping)
        return render(load_template(tpl_name), base)

    # --- the bai viet ---
    def category_of(self, post):
        return self.cat_by_slug.get(post.get("category", ""))

    def card(self, p, variant="", eager=False, show_excerpt=True):
        cat = self.category_of(p)
        cover = (p.get("cover") or {}).get("sm") or (p.get("cover") or {}).get("lg") or ""
        if variant == "large":
            cover = (p.get("cover") or {}).get("lg") or cover
        loading = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
        cat_html = '<a class="card-cat" href="%s">%s</a>' % (url_of(cat["slug"]), esc(cat["name"])) if cat else ""
        excerpt = '<p class="card-excerpt">%s</p>' % esc(p.get("description", "")) if show_excerpt and p.get("description") else ""
        width, height = ("1200", "800") if variant == "large" else ("480", "320")
        return (
            '<article class="card %s">\n'
            '  <a class="card-media" href="%s" tabindex="-1" aria-hidden="true"><img src="%s" alt="%s" width="%s" height="%s" %s></a>\n'
            '  <div class="card-body">\n'
            '    %s\n'
            '    <h3 class="card-title"><a href="%s">%s</a></h3>\n'
            '    %s\n'
            '    <p class="card-meta"><time datetime="%s">%s</time><span aria-hidden="true">•</span>%s phút đọc</p>\n'
            '  </div>\n'
            '</article>'
        ) % (variant, url_of(p["slug"]), esc(asset_url(cover)), esc(p["title"]), width, height, loading,
             cat_html, url_of(p["slug"]), esc(p["title"]), excerpt,
             esc(date_iso(p.get("date"))), date_display(p.get("date")), reading_minutes(p.get("content_html", "")))

    def mini_item(self, p):
        cover = (p.get("cover") or {}).get("sm") or ""
        cat = self.category_of(p)
        return (
            '<article class="mini">\n'
            '  <a class="mini-media" href="%s" tabindex="-1" aria-hidden="true"><img src="%s" alt="%s" width="480" height="320" loading="lazy" decoding="async"></a>\n'
            '  <div>\n'
            '    %s\n'
            '    <h3 class="mini-title"><a href="%s">%s</a></h3>\n'
            '    <p class="card-meta"><time datetime="%s">%s</time></p>\n'
            '  </div>\n'
            '</article>'
        ) % (url_of(p["slug"]), esc(asset_url(cover)), esc(p["title"]),
             '<span class="card-cat">%s</span>' % esc(cat["name"]) if cat else "",
             url_of(p["slug"]), esc(p["title"]), esc(date_iso(p.get("date"))), date_display(p.get("date")))

    def grid(self, posts, cls="grid-3"):
        return '<div class="grid %s">\n%s\n</div>' % (cls, "\n".join(self.card(p) for p in posts))


# ---------- builders ----------

def build_home(site):
    w = site.website
    posts = site.posts
    sections = []
    if not posts:
        sections.append(
            '    <section class="section">\n      <div class="container empty-state">\n'
            '        <h2>Những câu chuyện đầu tiên đang được viết</h2>\n'
            '        <p>Website vừa được dựng xong. Hãy quay lại sau ít hôm nữa nhé.</p>\n'
            '      </div>\n    </section>')
    else:
        featured = [p for p in posts if p.get("featured")]
        hero = featured[0] if featured else posts[0]
        rest = [p for p in posts if p["slug"] != hero["slug"]]
        side = rest[:4]
        latest = rest[4:10]
        if len(latest) > 3:
            latest = latest[:len(latest) // 3 * 3]  # luoi 3 cot: khong de le 1-2 the o hang cuoi
        sections.append(
            '    <section class="section hero">\n      <div class="container hero-grid">\n'
            '        <div class="hero-main">\n%s\n        </div>\n'
            '        <div class="hero-side">\n          <h2 class="side-title">Mới cập nhật</h2>\n%s\n        </div>\n'
            '      </div>\n    </section>' % (site.card(hero, "large", eager=True), "\n".join(site.mini_item(p) for p in side)))
        if latest:
            sections.append(
                '    <section class="section">\n      <div class="container">\n'
                '        <div class="section-head"><h2>Câu chuyện mới</h2></div>\n%s\n'
                '      </div>\n    </section>' % site.grid(latest))
        for cat in site.categories:
            cat_posts = [p for p in posts if p.get("category") == cat["slug"]][:4]
            if not cat_posts:
                continue
            sections.append(
                '    <section class="section section-cat">\n      <div class="container">\n'
                '        <div class="section-head"><h2><a href="%s">%s</a></h2><a class="see-all" href="%s">Xem tất cả →</a></div>\n'
                '        %s\n%s\n      </div>\n    </section>' % (
                    url_of(cat["slug"]), esc(cat["name"]), url_of(cat["slug"]),
                    '<p class="section-desc">%s</p>' % esc(cat.get("description")) if cat.get("description") else "",
                    site.grid(cat_posts, "grid-4")))

    ld = [{
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": w["site_name"],
        "url": site.domain,
        "description": w.get("description", ""),
        "inLanguage": w.get("lang", "vi"),
        "potentialAction": {
            "@type": "SearchAction",
            "target": site.domain + "tim-kiem/?q={search_term_string}",
            "query-input": "required name=search_term_string",
        },
    }]
    title = w["site_name"] + (" - " + w["tagline"] if w.get("tagline") else "")
    head = site.head(title, w.get("description", ""), "/", ld=ld)
    write_page("", site.shell("home.html", head, {
        "SITE_NAME": esc(w["site_name"]),
        "TAGLINE": esc(w.get("tagline", "")),
        "HOME_SECTIONS": "\n".join(sections),
    }))


def pagination(base, page, total_pages):
    if total_pages <= 1:
        return ""
    def href(n):
        return base if n == 1 else "%strang-%d/" % (base, n)
    parts = []
    if page > 1:
        parts.append('<a class="page-link" href="%s" rel="prev">← Trước</a>' % href(page - 1))
    for n in range(1, total_pages + 1):
        if n == page:
            parts.append('<span class="page-link current" aria-current="page">%d</span>' % n)
        else:
            parts.append('<a class="page-link" href="%s">%d</a>' % (href(n), n))
    if page < total_pages:
        parts.append('<a class="page-link" href="%s" rel="next">Sau →</a>' % href(page + 1))
    return '<nav class="pagination" aria-label="Phân trang">%s</nav>' % "".join(parts)


def build_category(site, cat):
    cat_posts = [p for p in site.posts if p.get("category") == cat["slug"]]
    base = url_of(cat["slug"])
    total_pages = max(1, int(math.ceil(len(cat_posts) / float(POSTS_PER_PAGE))))
    for page in range(1, total_pages + 1):
        chunk = cat_posts[(page - 1) * POSTS_PER_PAGE: page * POSTS_PER_PAGE]
        path = base if page == 1 else "%strang-%d/" % (base, page)
        title = cat["name"] + (" - Trang %d" % page if page > 1 else "") + " | " + site.website["site_name"]
        desc = cat.get("description") or ("Các câu chuyện thuộc danh mục %s trên %s." % (cat["name"], site.website["site_name"]))
        ld = [{
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Trang chủ", "item": site.domain},
                {"@type": "ListItem", "position": 2, "name": cat["name"], "item": site.domain.rstrip("/") + base},
            ],
        }]
        extra = []
        if page > 1:
            prev = base if page == 2 else "%strang-%d/" % (base, page - 1)
            extra.append('  <link rel="prev" href="%s">' % esc(site.domain.rstrip("/") + prev))
        if page < total_pages:
            extra.append('  <link rel="next" href="%s">' % esc(site.domain.rstrip("/") + "%strang-%d/" % (base, page + 1)))
        og_image = ((chunk[0].get("cover") or {}).get("lg") if chunk else "") or ""
        head = site.head(title, desc, path, og_image=og_image, extra_meta="\n".join(extra), ld=ld)
        grid = site.grid(chunk) if chunk else '<div class="empty-state"><p>Danh mục này chưa có câu chuyện nào.</p></div>'
        write_page(path.strip("/"), site.shell("category.html", head, {
            "CATEGORY_NAME": esc(cat["name"]),
            "CATEGORY_DESCRIPTION": esc(cat.get("description", "")),
            "POST_COUNT": str(len(cat_posts)),
            "PAGE_LABEL": (" · Trang %d/%d" % (page, total_pages)) if total_pages > 1 else "",
            "POST_GRID": grid,
            "PAGINATION": pagination(base, page, total_pages),
        }))
    return total_pages


def build_post(site, post, index):
    w = site.website
    cat = site.category_of(post) or {"slug": "", "name": "Câu chuyện"}
    cat_url = url_of(cat["slug"]) if cat["slug"] else "/"
    path = url_of(post["slug"])
    canonical = site.domain.rstrip("/") + path
    author = post.get("author") or w.get("author_default") or w["site_name"]
    cover = post.get("cover") or {}
    tags = [t.strip() for t in (post.get("keywords") or "").split(",") if t.strip()]
    minutes = reading_minutes(post.get("content_html", ""))

    related = [p for p in site.posts if p.get("category") == post.get("category") and p["slug"] != post["slug"]][:3]
    if len(related) < 3:
        taken = {p["slug"] for p in related} | {post["slug"]}
        related += [p for p in site.posts if p["slug"] not in taken][:3 - len(related)]

    newer = site.posts[index - 1] if index > 0 else None
    older = site.posts[index + 1] if index + 1 < len(site.posts) else None
    prev_next = ""
    if newer or older:
        cells = []
        cells.append('<a class="pn pn-prev" href="%s"><span>← Bài trước</span><strong>%s</strong></a>' % (url_of(older["slug"]), esc(older["title"])) if older else "<span></span>")
        cells.append('<a class="pn pn-next" href="%s"><span>Bài tiếp →</span><strong>%s</strong></a>' % (url_of(newer["slug"]), esc(newer["title"])) if newer else "<span></span>")
        prev_next = '        <nav class="prev-next" aria-label="Bài khác">%s</nav>' % "".join(cells)

    extra = [
        '  <meta property="article:published_time" content="%s">' % esc(date_iso(post.get("date"))),
        '  <meta property="article:modified_time" content="%s">' % esc(date_iso(post.get("updated_at") or post.get("date"))),
        '  <meta property="article:section" content="%s">' % esc(cat["name"]),
        '  <meta property="article:author" content="%s">' % esc(author),
    ] + ['  <meta property="article:tag" content="%s">' % esc(t) for t in tags]

    image_abs = absolute(site.domain, cover.get("lg", ""))
    ld = [{
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "headline": post["title"],
        "description": post.get("description", ""),
        "image": [image_abs] if image_abs else [],
        "datePublished": date_iso(post.get("date")),
        "dateModified": date_iso(post.get("updated_at") or post.get("date")),
        "author": {"@type": "Person", "name": author},
        "publisher": {"@type": "Organization", "name": w["site_name"],
                      "logo": {"@type": "ImageObject", "url": absolute(site.domain, w.get("logo") or w.get("favicon") or "")}},
        "articleSection": cat["name"],
        "keywords": ", ".join(tags),
        "inLanguage": w.get("lang", "vi"),
    }, {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Trang chủ", "item": site.domain},
            {"@type": "ListItem", "position": 2, "name": cat["name"], "item": site.domain.rstrip("/") + cat_url},
            {"@type": "ListItem", "position": 3, "name": post["title"], "item": canonical},
        ],
    }]
    head = site.head(post["title"] + " | " + w["site_name"], post.get("description", ""), path,
                     og_type="article", og_image=cover.get("lg", ""), keywords=", ".join(tags),
                     extra_meta="\n".join(extra), ld=ld, og_title=post["title"])
    tags_html = ""
    if tags:
        tags_html = '        <div class="tags">%s</div>' % "".join(
            '<a class="tag" href="/tim-kiem/?q=%s">#%s</a>' % (esc(quote(t)), esc(t)) for t in tags)
    related_html = ""
    if related:
        related_html = (
            '    <section class="section related">\n      <div class="container">\n'
            '        <div class="section-head"><h2>Có thể bạn sẽ thích</h2></div>\n%s\n'
            '      </div>\n    </section>' % site.grid(related))
    write_page(post["slug"], site.shell("post.html", head, {
        "CATEGORY_URL": cat_url,
        "CATEGORY_NAME": esc(cat["name"]),
        "TITLE": esc(post["title"]),
        "DESCRIPTION": esc(post.get("description", "")),
        "AUTHOR": esc(author),
        "AUTHOR_INITIAL": initial(author),
        "DATE_ISO": esc(date_iso(post.get("date"))),
        "DATE_DISPLAY": date_display(post.get("date")),
        "READING_MINUTES": str(minutes),
        "COVER_LG": esc(asset_url(cover.get("lg", ""))),
        # Noi dung tu TinyMCE la HTML that - ghi RAW, khong escape.
        "CONTENT": prepare_content(post.get("content_html", "")),
        "TAGS": tags_html,
        "CANONICAL": esc(canonical),
        "CANONICAL_ENC": esc(quote(canonical, safe="")),
        "TITLE_ENC": esc(quote(post["title"], safe="")),
        "PREV_NEXT": prev_next,
        "RELATED": related_html,
    }))


def build_page(site, page):
    w = site.website
    path = url_of(page["slug"])
    desc = page.get("description") or w.get("description", "")
    head = site.head(page["title"] + " | " + w["site_name"], desc, path, og_title=page["title"])
    write_page(page["slug"], site.shell("page.html", head, {
        "TITLE": esc(page["title"]),
        "DESCRIPTION": esc(page.get("description", "")),
        "CONTENT": prepare_content(page.get("content_html", "")),
    }))


def build_search(site):
    w = site.website
    index = []
    for p in site.posts:
        cat = site.category_of(p)
        index.append({
            "t": p["title"],
            "u": url_of(p["slug"]),
            "d": p.get("description", ""),
            "k": p.get("keywords", ""),
            "c": cat["name"] if cat else "",
            "i": asset_url((p.get("cover") or {}).get("sm", "")),
            "dt": date_display(p.get("date")),
            "m": reading_minutes(p.get("content_html", "")),
        })
    (OUT / "search-index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    head = site.head("Tìm kiếm | " + w["site_name"], "Tìm câu chuyện trên " + w["site_name"], "/tim-kiem/",
                     robots="noindex, follow")
    write_page("tim-kiem", site.shell("search.html", head, {}))


def build_404(site):
    w = site.website
    head = site.head("Không tìm thấy trang | " + w["site_name"], w.get("description", ""), "/404.html", robots="noindex, follow")
    pills = "\n".join('          <a class="pill" href="%s">%s</a>' % (url_of(c["slug"]), esc(c["name"])) for c in site.categories)
    (OUT / "404.html").write_text(site.shell("404.html", head, {"CATEGORY_PILLS": pills}), encoding="utf-8")


def build_sitemap(site, cat_pages):
    d = site.domain.rstrip("/")
    urls = [(site.domain, site.posts[0].get("updated_at") if site.posts else "", "1.0")]
    for c in site.categories:
        urls.append((d + url_of(c["slug"]), "", "0.8"))
        for n in range(2, cat_pages.get(c["slug"], 1) + 1):
            urls.append((d + "%strang-%d/" % (url_of(c["slug"]), n), "", "0.5"))
    for p in site.posts:
        urls.append((d + url_of(p["slug"]), p.get("updated_at") or p.get("date"), "0.9"))
    for p in site.pages:
        urls.append((d + url_of(p["slug"]), p.get("updated_at", ""), "0.6"))
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, prio in urls:
        lm = "\n    <lastmod>%s</lastmod>" % esc(date_iso(lastmod)) if lastmod else ""
        parts.append("  <url>\n    <loc>%s</loc>%s\n    <priority>%s</priority>\n  </url>" % (esc(loc), lm, prio))
    parts.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(parts) + "\n", encoding="utf-8")


def build_feed(site):
    w = site.website
    d = site.domain.rstrip("/")
    items = []
    for p in site.posts[:20]:
        items.append(
            "    <item>\n      <title>%s</title>\n      <link>%s</link>\n      <guid isPermaLink=\"true\">%s</guid>\n"
            "      <pubDate>%s</pubDate>\n      <description>%s</description>\n    </item>" % (
                esc(p["title"]), esc(d + url_of(p["slug"])), esc(d + url_of(p["slug"])),
                rfc822(p.get("date")), esc(p.get("description", ""))))
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n  <channel>\n'
        "    <title>%s</title>\n    <link>%s</link>\n    <description>%s</description>\n    <language>%s</language>\n%s\n"
        "  </channel>\n</rss>\n") % (esc(w["site_name"]), esc(site.domain), esc(w.get("description", "")),
                                     esc(w.get("lang", "vi")), "\n".join(items))
    (OUT / "feed.xml").write_text(xml, encoding="utf-8")


def build_misc(site):
    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % site.domain, encoding="utf-8")
    ads = (site.website.get("ads_txt") or "").strip()
    if ads:
        (OUT / "ads.txt").write_text(ads + "\n", encoding="utf-8")


def check_slugs(categories, posts, pages):
    seen = {}
    ok = True
    for kind, items in (("danh muc", categories), ("bai viet", posts), ("trang", pages)):
        for it in items:
            slug = it["slug"]
            if slug in RESERVED_SLUGS:
                print("ERROR: %s '%s' dung slug danh rieng" % (kind, slug))
                ok = False
            if slug in seen:
                print("ERROR: slug '%s' trung giua %s va %s" % (slug, seen[slug], kind))
                ok = False
            seen[slug] = kind
    return ok


def main():
    parser = argparse.ArgumentParser(description="Build site tinh DanDan Stories")
    parser.add_argument("--demo", action="store_true", help="dung du lieu mau trong demo/ thay cho data/")
    args = parser.parse_args()

    data_dir = ROOT / ("demo/data" if args.demo else "data")
    website, categories, posts, pages = load_data(data_dir)
    if not check_slugs(categories, posts, pages):
        sys.exit(1)

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT)
    if args.demo and (ROOT / "demo/static").exists():
        shutil.copytree(ROOT / "demo/static", OUT, dirs_exist_ok=True)

    site = Site(website, categories, posts, pages)
    for i, post in enumerate(site.posts):
        build_post(site, post, i)
    cat_pages = {}
    for cat in site.categories:
        cat_pages[cat["slug"]] = build_category(site, cat)
    for page in site.pages:
        build_page(site, page)
    build_home(site)
    build_search(site)
    build_404(site)
    build_sitemap(site, cat_pages)
    build_feed(site)
    build_misc(site)
    print("Done (%s): %d bai, %d danh muc, %d trang tinh -> html/" % (
        "demo" if args.demo else "data", len(site.posts), len(site.categories), len(site.pages)))


if __name__ == "__main__":
    main()
