#!/usr/bin/env python3
"""
Build site tinh DanDan Stories tu data/ + templates/ + static/ (chi dung Python stdlib).

Giao dien = giao dien TrithucWorld (templates/*.html scaffold 1 lan tu trithucworld/remake/templates,
giu nguyen HTML/CSS/JS inline, chi doi chu sang tieng Anh + placeholder {{TOKEN}}). Sua giao dien
thi sua thang templates/*.html.

Input (chot o GAS.md muc VIII):
  data/website.json         cai dat website (CMS tab "Cai dat website")
  data/categories.json      danh muc [{slug, name, description, order}]
  data/posts.json           index nhe moi bai (khong content)
  data/posts/<slug>.json    noi dung day du 1 bai ({"slug", "content_html"})
  data/pages.json           trang tinh, kem noi dung
  static/**                 anh, vendor, admin - copy nguyen vao html/

Output: html/ (XOA SACH va sinh lai moi lan build; GitHub Actions commit nguoc vao repo,
Cloudflare deploy tu do - khong sua tay):
  html/index.html             trang chu
  html/<slug>/index.html      bai viet, danh muc, trang tinh (URL "/<slug>/")
  html/404.html, sitemap.xml, feed.xml, robots.txt, ads.txt (neu co)

Chay:
  python3 scripts/build.py           # du lieu that (data/) -> html/
  python3 scripts/build.py --demo    # du lieu mau (demo/) -> html-demo/ (khong dung html/ that)
"""
import argparse
import html as htmllib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "html"  # --demo doi sang html-demo/ (xem main)

POSTS_PER_PAGE = 12
# Phai khop RESERVED_SLUGS trong gas/Code.js (gas/ khong nam trong git nen 2 cho nay KHONG tu
# dong bo duoc - sua 1 ben thi sua luon ben kia).
RESERVED_SLUGS = {"images", "assets", "vendor", "admin", "search", "page", "feed", "sitemap", "404"}

DEFAULT_WEBSITE = {
    "site_name": "DanDan Stories",
    "tagline": "Small stories that stay with you.",
    "description": "DanDan Stories - everyday stories, memories, journeys and short fiction, told slowly and honestly.",
    "domain_url": "https://rapidfanpost.com/",
    "lang": "en",
    "author_default": "DanDan",
    "footer_about": "A quiet corner of the internet for telling and reading everyday stories - slow, honest and warm.",
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




def write_page(rel_dir, html):
    """rel_dir: "" (trang chu) hoac "slug" hoac "slug/page/2" -> html/<rel_dir>/index.html."""
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


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def date_display(value):
    """"Oct 28, 2026" - tu ghep, khong phu thuoc locale cua may build."""
    d = parse_date(value)
    return "%s %d, %d" % (MONTHS[d.month - 1], d.day, d.year) if d else ""


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






def prepare_content(html):
    """Them loading=lazy/decoding=async cho anh trong noi dung (anh dau trang da la cover)."""
    def fix(m):
        tag = m.group(0)
        if "loading=" not in tag:
            tag = tag[:-1].rstrip("/").rstrip() + ' loading="lazy" decoding="async">'
        return tag
    return re.sub(r"<img\b[^>]*>", fix, html or "")


def json_ld(obj):
    obj = {k: v for k, v in obj.items() if v is not None}
    data = json.dumps(obj, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return '  <script type="application/ld+json">\n%s\n  </script>' % data




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
    """Gia tri dung chung moi trang (header logo, menu, footer...) theo dung markup trithucworld."""

    def __init__(self, website, categories, posts, pages):
        self.website = website
        self.categories = categories
        self.cat_by_slug = {c["slug"]: c for c in categories}
        self.posts = posts
        self.pages = pages
        self.domain = website["domain_url"]

    def category_of(self, post):
        return self.cat_by_slug.get(post.get("category", ""))

    def common(self):
        w = self.website
        name = esc(w["site_name"])
        if w.get("logo"):
            logo = '<img src="%s" alt="Logo %s">' % (esc(asset_url(w["logo"])), name)
            footer_logo = '<img src="%s" alt="Logo" class="footer-logo">' % esc(asset_url(w["logo"]))
        else:
            # Chua co logo: hien ten website (cung mau do --main-red cua giao dien).
            logo = '<span style="font-size:1.6rem;font-weight:800;color:#c00;white-space:nowrap">%s</span>' % name
            footer_logo = '<span style="display:inline-block;font-size:1.3rem;font-weight:800;color:#c00;margin-bottom:12px">%s</span>' % name
        ga = (w.get("ga_id") or "").strip()
        analytics = ""
        if re.match(r"^G-[A-Z0-9]+$", ga):
            analytics = (
                '<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>\n'
                "    <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                "gtag('js',new Date());gtag('config','%s');</script>" % (ga, ga))
        return {
            "LANG": esc(w.get("lang", "en")),
            "GOOGLE_ANALYTICS_CODE": analytics,
            # Ma chen <head> tuy y do admin nhap (AdSense, Search Console...) - ghi RAW.
            "HEAD_HTML": w.get("head_html", ""),
            "SITE_NAME": name,
            "WEBSITE_NAME": name,
            "AUTHOR": esc(w.get("author_default") or w["site_name"]),
            "WEBSITE_DESCRIPTION": esc(w.get("description", "")),
            "DOMAIN_URL": esc(self.domain),
            "FAVICON": esc(asset_url(w.get("favicon")) or "/assets/favicon.svg"),
            "YEAR": str(datetime.now().year),
            "LOGO_IMG": logo,
            "FOOTER_LOGO": footer_logo,
            "NAV_CATEGORIES": self.nav(mobile=False),
            "MOBILE_NAV_CATEGORIES": self.nav(mobile=True),
            "FOOTER_PAGE_LINKS": self.footer_page_links(),
            "FOOTER_CONTACT": self.footer_contact(),
            "JSON_LD": "",
            "SEO_TAGS": "",
        }

    def page(self, tpl_name, mapping):
        values = self.common()
        values.update(mapping)
        return render(load_template(tpl_name), values)

    def og_default(self):
        """Anh chia se mac dinh: anh trong Cai dat website, chua co thi lay anh bia bai moi nhat."""
        img = self.website.get("og_image") or ""
        if not img and self.posts:
            img = (self.posts[0].get("cover") or {}).get("lg", "")
        return absolute(self.domain, img) if img else ""

    def seo_tags(self, title, description, image="", image_size=None, extra=None):
        """Khoi the SEO bo sung chen sau <link rel=canonical> moi trang (placeholder {{SEO_TAGS}}):
        og:locale, og:image (+ kich thuoc that), Twitter/X card, RSS, apple-touch-icon."""
        w = self.website
        lang = w.get("lang", "en")
        tags = ['    <meta property="og:locale" content="%s">' % {"en": "en_US", "vi": "vi_VN"}.get(lang, esc(lang))]
        if image:
            tags.append('    <meta property="og:image" content="%s">' % esc(image))
            if image_size:
                tags.append('    <meta property="og:image:width" content="%d">' % image_size[0])
                tags.append('    <meta property="og:image:height" content="%d">' % image_size[1])
            tags.append('    <meta property="og:image:alt" content="%s">' % esc(title))
        tags.append('    <meta name="twitter:card" content="%s">' % ("summary_large_image" if image else "summary"))
        tags.append('    <meta name="twitter:title" content="%s">' % esc(title))
        tags.append('    <meta name="twitter:description" content="%s">' % esc(description))
        if image:
            tags.append('    <meta name="twitter:image" content="%s">' % esc(image))
        tags += extra or []
        tags.append('    <link rel="alternate" type="application/rss+xml" title="%s" href="%sfeed.xml">' % (esc(w["site_name"]), esc(self.domain)))
        tags.append('    <link rel="apple-touch-icon" href="%s">' % esc(asset_url(w.get("favicon")) or "/assets/favicon.svg"))
        return "\n".join(tags)

    def og_size(self, url):
        """Kich thuoc that cua anh chia se: anh bia bai 1200x800, anh mac dinh 1200x630."""
        if not url:
            return None
        if "/cover-" in url or "/cover." in url:
            return (1200, 800)
        if (self.website.get("og_image") or "x").split("?")[0] in url:
            return (1200, 630)
        return None

    def publisher_ld(self):
        w = self.website
        org = {"@type": "Organization", "name": w["site_name"], "url": self.domain}
        logo = w.get("logo") or w.get("favicon")
        if logo:
            org["logo"] = {"@type": "ImageObject", "url": absolute(self.domain, logo)}
        return org

    def nav(self, mobile):
        items = [(url_of(c["slug"]), c["name"]) for c in self.categories]
        items += [(url_of(p["slug"]), p["title"]) for p in self.pages if p.get("show_in_menu")]
        cls = "" if mobile else ' class="parent"'
        return "\n".join(
            '          <li%s>\n            <a href="%s" title="%s">%s</a>\n          </li>' % (cls, u, esc(n), esc(n))
            for u, n in items)

    def footer_page_links(self):
        return "\n".join(
            '            <li>\n              <a href="%s">%s</a>\n            </li>' % (url_of(p["slug"]), esc(p["title"]))
            for p in self.pages)

    def footer_contact(self):
        w = self.website
        lines = []
        if w.get("contact_email"):
            lines.append('Email: <a href="mailto:%s">%s</a>' % (esc(w["contact_email"]), esc(w["contact_email"])))
        if w.get("contact_phone"):
            tel = re.sub(r"[^\d+]", "", w["contact_phone"])
            lines.append('Phone: <a href="tel:%s">%s</a>' % (esc(tel), esc(w["contact_phone"])))
        if w.get("contact_address"):
            lines.append("Address: %s" % esc(w["contact_address"]))
        for key, label in (("facebook", "Facebook"), ("youtube", "YouTube"), ("tiktok", "TikTok"), ("instagram", "Instagram")):
            if w.get(key):
                lines.append('%s: <a href="%s" target="_blank" rel="noopener">%s</a>' % (
                    label, esc(w[key]), esc(re.sub(r"^https?://(www\.)?", "", w[key]).rstrip("/"))))
        return "\n".join("            <p>%s</p>" % l for l in lines)


# ---------- card renderers: giu nguyen markup cua trithucworld (scripts/build.py ban goc) ----------
# Anh: "lg" = 1200x800 (crop 3:2), "sm" = 480x320. Ban goc co 3 co 480x320/240x160/120x80 - o day
# moi cho nho dung "sm" (cung ti le 3:2, CSS cua giao dien tu co kich thuoc hien thi).

def img(p, size="sm"):
    cover = p.get("cover") or {}
    return esc(asset_url(cover.get(size) or cover.get("sm") or cover.get("lg") or ""))


def home_col1_card(p):
    return ('          <article class="post">\n'
            '              <a href="%s">\n'
            '                <img src="%s" alt="%s" fetchpriority="high" width="480" height="320">\n'
            '              </a>\n'
            '              <div class="body">\n'
            '              <h3><a href="%s">%s</a></h3>\n'
            '              <p>%s</p>\n'
            '            </div>\n'
            '          </article>') % (url_of(p["slug"]), img(p, "lg"), esc(p["title"]), url_of(p["slug"]), esc(p["title"]), esc(p.get("description", "")))


def home_col2_card(p):
    return ('          <article class="post">\n'
            '              <a href="%s">\n'
            '                <img src="%s" alt="%s">\n'
            '              </a>\n'
            '              <div class="body">\n'
            '              <h3><a href="%s">%s</a></h3>\n'
            '            </div>\n'
            '          </article>') % (url_of(p["slug"]), img(p), esc(p["title"]), url_of(p["slug"]), esc(p["title"]))


def home_col3_card(p):
    return ('        <article class="post">\n'
            '            <a href="%s">\n'
            '              <img src="%s" alt="%s">\n'
            '            </a>\n'
            '            <div class="body">\n'
            '              <h3><a href="%s">%s</a></h3>\n'
            '          </div>\n'
            '          </article>') % (url_of(p["slug"]), img(p), esc(p["title"]), url_of(p["slug"]), esc(p["title"]))


def slider_item(p):
    return ('            <div class="slide-4-item">\n'
            '                  <a href="%s">\n'
            '                    <img src="%s" alt="%s">\n'
            '                  </a>\n'
            '                  <h3><a href="%s">%s</a></h3>\n'
            '                  <p class="slide-desc">%s</p>\n'
            '                </div>') % (url_of(p["slug"]), img(p), esc(p["title"]), url_of(p["slug"]), esc(p["title"]), esc(p.get("description", "")))


def main_post_a(p):
    """Link boc ca article (posts[8:14] trang chu, posts[8:12] trang danh muc)."""
    return ('          <a href="%s">\n'
            '            <article class="main-post">\n'
            '              <img src="%s" alt="%s">\n'
            '              <div class="main-content">\n'
            '                <h3>%s</h3>\n'
            '                <p>%s</p>\n'
            '              </div>\n'
            '            </article>\n'
            '          </a>') % (url_of(p["slug"]), img(p), esc(p["title"]), esc(p["title"]), esc(p.get("description", "")))


def main_post_b(p):
    """posts[18:] trang danh muc - link nam trong article."""
    return ('          <article class="main-post">\n'
            '            <a href="%s">\n'
            '              <img src="%s" alt="%s">\n'
            '              <div class="main-content">\n'
            '                <h3>%s</h3>\n'
            '                <p>%s</p>\n'
            '              </div>\n'
            '            </a>\n'
            '          </article>') % (url_of(p["slug"]), img(p), esc(p["title"]), esc(p["title"]), esc(p.get("description", "")))


def home_side_post(p):
    return ('              <article class="side-post">\n'
            '                <a href="%s">\n'
            '                  <img src="%s" alt="%s">\n'
            '                  <h3>%s</h3>\n'
            '                </a>\n'
            '              </article>') % (url_of(p["slug"]), img(p), esc(p["title"]), esc(p["title"]))


def cat_side_post(p):
    return ('          <a href="%s">\n'
            '            <article class="side-post">\n'
            '              <img src="%s" alt="%s">\n'
            '              <h3>%s</h3>\n'
            '            </article>\n'
            '          </a>') % (url_of(p["slug"]), img(p), esc(p["title"]), esc(p["title"]))


def category_post_card(p):
    return ('              <a href="%s">\n'
            '                  <div class="category-post">\n'
            '                    <img src="%s" alt="%s">\n'
            '                    <h3>%s</h3>\n'
            '                    <p>%s</p>\n'
            '                  </div>\n'
            '                </a>') % (url_of(p["slug"]), img(p), esc(p["title"]), esc(p["title"]), esc(p.get("description", "")))


def cate_side_post(p):
    return ('              <a href="%s">\n'
            '                <article>\n'
            '                  <h3>%s</h3>\n'
            '                  <img src="%s" alt="%s">\n'
            '                </article>\n'
            '              </a>') % (url_of(p["slug"]), esc(p["title"]), img(p), esc(p["title"]))


def cat_featured_col1(p):
    return ('          <article class="post">\n'
            '              <a href="%s">\n'
            '                <img src="%s" alt="%s" fetchpriority="high" width="480" height="320">\n'
            '              </a>\n'
            '              <div class="body">\n'
            '              <a href="%s">\n'
            '                <h3>%s</h3>\n'
            '              </a>\n'
            '              <p>%s</p>\n'
            '            </div>\n'
            '          </article>') % (url_of(p["slug"]), img(p, "lg"), esc(p["title"]), url_of(p["slug"]), esc(p["title"]), esc(p.get("description", "")))


def cat_featured_col2(p):
    return ('          <article class="post">\n'
            '            <a href="%s">\n'
            '              <img src="%s" alt="%s">\n'
            '            </a>\n'
            '            <div class="body">\n'
            '              <a href="%s">\n'
            '                  <h3>%s</h3>\n'
            '              </a>\n'
            '            </div>\n'
            '          </article>') % (url_of(p["slug"]), img(p), esc(p["title"]), url_of(p["slug"]), esc(p["title"]))


def cat_featured_col3(p):
    return ('          <a href="%s">\n'
            '            <article class="post">\n'
            '              <img src="%s" alt="%s">\n'
            '              <div class="body">\n'
            '                <h3>%s</h3>\n'
            '              </div>\n'
            '            </article>\n'
            '          </a>') % (url_of(p["slug"]), img(p), esc(p["title"]), esc(p["title"]))


def featured_item(p, author):
    """Sidebar "Featured stories" o trang bai viet / trang tinh."""
    return ('            <article class="featured-item">\n'
            '                <a href="%s">\n'
            '                  <img src="%s" alt="%s">\n'
            '                </a>\n'
            '                <div class="featured-body">\n'
            '                  <h4>\n'
            '                    <a href="%s">%s</a>\n'
            '                  </h4>\n'
            '                  <p class="f-meta">• %s</p>\n'
            '                </div>\n'
            '              </article>') % (url_of(p["slug"]), img(p), esc(p["title"]), url_of(p["slug"]), esc(p["title"]), esc(author))


def related_item(p):
    return ('            <article class="related-card">\n'
            '              <a href="%s">\n'
            '                <img src="%s" alt="%s">\n'
            '              </a>\n'
            '              <h4>\n'
            '                <a href="%s">%s</a>\n'
            '              </h4>\n'
            '            </article>') % (url_of(p["slug"]), img(p), esc(p["title"]), url_of(p["slug"]), esc(p["title"]))


def homepage_category_block(site, category, even):
    cat_posts = [p for p in site.posts if p.get("category") == category["slug"]]
    if not cat_posts:
        return ""
    cls = "category cate-even" if even else "category"
    return ('        <section class="%s">\n'
            '          <div class="category-header">\n'
            '            <h2>\n'
            '              <a href="%s">%s</a>\n'
            '            </h2>\n'
            '          </div>\n'
            '          <div class="category-content">\n'
            '%s\n'
            '            <div class="cate-side-posts">\n'
            '%s\n'
            '            </div>\n'
            '          </div>\n'
            '        </section>') % (cls, url_of(category["slug"]), esc(category["name"]),
                                     category_post_card(cat_posts[0]), "\n".join(cate_side_post(p) for p in cat_posts[1:5]))


# ---------- builders ----------

def breadcrumb_ld(site, items):
    return json_ld({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(items)
        ],
    })


def build_home(site):
    w = site.website
    posts = site.posts
    # Bai danh dau "Noi bat" len o lon dau trang, cac bai con lai theo thu tu moi nhat.
    featured = [p for p in posts if p.get("featured")]
    ordered = (featured[:1] + [p for p in posts if not featured or p["slug"] != featured[0]["slug"]]) if posts else []

    empty = ""
    if not posts:
        empty = ('\n        <div style="grid-column:1/-1;text-align:center;padding:60px 20px;background:#fff;'
                 'border-radius:8px;box-shadow:0 6px 18px rgba(16,24,40,.06)">'
                 '<h2 style="margin:0 0 8px">The first stories are being written</h2>'
                 '<p style="margin:0;color:#555">This site has just been set up. Please come back soon.</p></div>')

    slider = ""
    slider_cat = site.categories[0] if site.categories else None
    slider_posts = [p for p in posts if slider_cat and p.get("category") == slider_cat["slug"]][:8]
    if slider_posts:
        slider = ('      <section class="slide-4">\n'
                  '        <div class="slide-4-header">\n'
                  '          <h2>\n'
                  '            <a href="%s">%s</a>\n'
                  '          </h2>\n'
                  '          <div class="slide-4-controls">\n'
                  '            <button id="prevBtn" class="slide-btn" aria-label="Previous">&#8249;</button>\n'
                  '            <button id="nextBtn" class="slide-btn" aria-label="Next">&#8250;</button>\n'
                  '          </div>\n'
                  '        </div>\n'
                  '        <div class="slide-4-container">\n'
                  '          <div class="slide-4-track">\n%s\n'
                  '          </div>\n'
                  '        </div>\n'
                  '      </section>') % (url_of(slider_cat["slug"]), esc(slider_cat["name"]),
                                         "\n".join(slider_item(p) for p in slider_posts))

    left, side = ordered[8:14], ordered[14:20]
    posts_section = ""
    if left or side:
        posts_section = ('      <section class="posts-section">\n'
                         '        <div class="left-col">\n%s\n'
                         '        </div>\n'
                         '        <div class="right-col">\n'
                         '          <h3>You may also like</h3>\n'
                         '          <div class="side-posts">\n%s\n'
                         '          </div>\n'
                         '        </div>\n'
                         '      </section>') % ("\n".join(main_post_a(p) for p in left),
                                                "\n".join(home_side_post(p) for p in side))

    # Ban goc co dinh 6 khoi (category 1..6); o day lap theo so danh muc thuc te, 2 khoi/hang.
    blocks = [b for b in (homepage_category_block(site, c, i % 2 == 0) for i, c in enumerate(site.categories[1:])) if b]
    rows = []
    for i in range(0, len(blocks), 2):
        rows.append('      <div class="categories">\n%s\n      </div>' % "\n\n".join(blocks[i:i + 2]))

    home_title = w["site_name"] + (" - " + w["tagline"] if w.get("tagline") else "")
    og = site.og_default()
    publisher = site.publisher_ld()
    ld = "\n".join([json_ld(dict({"@context": "https://schema.org"}, **publisher)), json_ld({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": w["site_name"],
        "url": site.domain,
        "description": w.get("description", ""),
        "inLanguage": w.get("lang", "en"),
        "publisher": {"@type": "Organization", "name": w["site_name"]},
    })])
    write_page("", site.page("home.html", {
        "HOME_TITLE": esc(home_title),
        "SEO_TAGS": site.seo_tags(home_title, w.get("description", ""), og, site.og_size(og)),
        "JSON_LD": ld,
        "EMPTY_STATE": empty,
        "COL_1": "\n".join(home_col1_card(p) for p in ordered[0:1]),
        "COL_2": "\n\n".join(home_col2_card(p) for p in ordered[1:3]),
        "COL_3": "\n".join(home_col3_card(p) for p in ordered[3:8]),
        "SLIDER_SECTION": slider,
        "POSTS_SECTION": posts_section,
        "CATEGORY_BLOCKS": "\n\n".join(rows),
    }))


def build_category(site, cat):
    cat_posts = [p for p in site.posts if p.get("category") == cat["slug"]]
    main_posts = "\n".join(main_post_a(p) for p in cat_posts[8:12])
    tail_posts = "\n".join(main_post_b(p) for p in cat_posts[18:])
    og = absolute(site.domain, (cat_posts[0].get("cover") or {}).get("lg", "")) if cat_posts else site.og_default()
    desc = cat.get("description") or ("Stories in %s on %s." % (cat["name"], site.website["site_name"]))
    cat_url = site.domain + cat["slug"] + "/"
    collection = json_ld({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": cat["name"],
        "description": desc,
        "url": cat_url,
        "inLanguage": site.website.get("lang", "en"),
        "isPartOf": {"@type": "WebSite", "name": site.website["site_name"], "url": site.domain},
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": site.domain + p["slug"] + "/", "name": p["title"]}
                for i, p in enumerate(cat_posts[:30])
            ],
        },
    })
    write_page(cat["slug"], site.page("category.html", {
        "CATEGORY_NAME": esc(cat["name"]),
        "CATEGORY_URL": cat["slug"] + "/",
        "CATEGORY_DESCRIPTION": esc(desc),
        "SEO_TAGS": site.seo_tags(cat["name"] + " | " + site.website["site_name"], desc, og, site.og_size(og)),
        "JSON_LD": collection + "\n" + breadcrumb_ld(site, [("Home", site.domain), (cat["name"], cat_url)]),
        "FEATURED_COL_1": "\n".join(cat_featured_col1(p) for p in cat_posts[0:1]),
        "FEATURED_COL_2": "\n\n".join(cat_featured_col2(p) for p in cat_posts[1:3]),
        "FEATURED_COL_3": "\n".join(cat_featured_col3(p) for p in cat_posts[3:8]),
        "MAIN_POSTS": "\n\n".join(x for x in [main_posts, tail_posts] if x),
        "SIDE_POSTS": "\n".join(cat_side_post(p) for p in cat_posts[12:18]),
    }))


def suggestions(site, exclude_slug, count):
    """Bai noi bat cho sidebar: uu tien bai danh dau Noi bat, roi bai moi nhat."""
    pool = [p for p in site.posts if p["slug"] != exclude_slug]
    ordered = [p for p in pool if p.get("featured")] + [p for p in pool if not p.get("featured")]
    return ordered[:count]


def build_post(site, post):
    w = site.website
    cat = site.category_of(post) or {"slug": "", "name": "Stories"}
    canonical = site.domain + post["slug"] + "/"
    author = post.get("author") or w.get("author_default") or w["site_name"]
    tags = [t.strip() for t in (post.get("keywords") or "").split(",") if t.strip()]
    related = [p for p in site.posts if p.get("category") == post.get("category") and p["slug"] != post["slug"]][:4]
    if len(related) < 4:
        taken = {p["slug"] for p in related} | {post["slug"]}
        related += [p for p in site.posts if p["slug"] not in taken][:4 - len(related)]
    related_slugs = {p["slug"] for p in related}
    featured = [p for p in suggestions(site, post["slug"], 10) if p["slug"] not in related_slugs][:3]
    og = absolute(site.domain, (post.get("cover") or {}).get("lg", ""))

    published = date_iso(post.get("date"))
    modified = date_iso(post.get("updated_at") or post.get("date"))
    article_meta = [
        '    <meta property="article:published_time" content="%s">' % esc(published),
        '    <meta property="article:modified_time" content="%s">' % esc(modified),
        '    <meta property="article:section" content="%s">' % esc(cat["name"]),
        '    <meta property="article:author" content="%s">' % esc(author),
    ]
    words = len(re.sub(r"<[^>]+>", " ", post.get("content_html", "")).split())
    ld = "\n".join([json_ld({
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "url": canonical,
        "headline": post["title"][:110],
        "description": post.get("description", ""),
        "keywords": ", ".join(tags),
        "articleSection": cat["name"],
        "wordCount": words,
        "inLanguage": w.get("lang", "en"),
        "image": {"@type": "ImageObject", "url": og, "width": 1200, "height": 800} if og else None,
        "datePublished": published,
        "dateModified": modified,
        "author": {"@type": "Person", "name": author},
        "publisher": site.publisher_ld(),
    }), breadcrumb_ld(site, [("Home", site.domain), (cat["name"], site.domain + (cat["slug"] + "/" if cat["slug"] else "")),
                             (post["title"], canonical)])])
    write_page(post["slug"], site.page("post.html", {
        "TITLE": esc(post["title"]),
        "DESCRIPTION": esc(post.get("description", "")),
        "KEYWORDS": esc(", ".join(tags)),
        "AUTHOR": esc(author),
        "SEO_TAGS": site.seo_tags(post["title"], post.get("description", ""), og, (1200, 800) if og else None, article_meta),
        "POST_URL": post["slug"] + "/",
        "ARTICLE_TAGS": "\n".join('    <meta property="article:tag" content="%s">' % esc(t) for t in tags),
        "CATEGORY_NAME": esc(cat["name"]),
        "CATEGORY_URL": url_of(cat["slug"]) if cat["slug"] else "/",
        "CREATED_AT": date_display(post.get("date")),
        "JSON_LD": ld,
        # Noi dung tu trinh soan thao la HTML that - ghi RAW, khong escape.
        "CONTENT": prepare_content(post.get("content_html", "")),
        "FEATURED_ITEMS": "\n".join(featured_item(p, p.get("author") or author) for p in featured),
        "RELATED_ITEMS": "\n".join(related_item(p) for p in related),
    }))


def build_page(site, page):
    w = site.website
    canonical = site.domain + page["slug"] + "/"
    author = w.get("author_default") or w["site_name"]
    desc = page.get("description") or w.get("description", "")
    og = site.og_default()
    webpage = json_ld({
        "@context": "https://schema.org",
        "@type": {"about": "AboutPage", "contact": "ContactPage", "contact-us": "ContactPage"}.get(page["slug"], "WebPage"),
        "name": page["title"],
        "description": desc,
        "url": canonical,
        "inLanguage": w.get("lang", "en"),
        "dateModified": date_iso(page.get("updated_at")) or None,
        "isPartOf": {"@type": "WebSite", "name": w["site_name"], "url": site.domain},
        "publisher": site.publisher_ld(),
    })
    write_page(page["slug"], site.page("page.html", {
        "PAGE_TITLE": esc(page["title"]),
        "PAGE_DESCRIPTION": esc(desc),
        "PAGE_URL": page["slug"] + "/",
        "SEO_TAGS": site.seo_tags(page["title"] + " | " + w["site_name"], desc, og, site.og_size(og)),
        "JSON_LD": webpage + "\n" + breadcrumb_ld(site, [("Home", site.domain), (page["title"], canonical)]),
        "CONTENT": prepare_content(page.get("content_html", "")),
        "FEATURED_ITEMS": "\n".join(featured_item(p, p.get("author") or author) for p in suggestions(site, "", 3)),
    }))


def build_404(site):
    contact = next((p for p in site.pages if p["slug"] in ("contact", "contact-us")), None)
    pills = "\n".join('          <a class="notfound-pill" href="%s">%s</a>' % (url_of(c["slug"]), esc(c["name"]))
                      for c in site.categories)
    (OUT / "404.html").write_text(site.page("404.html", {
        "CATEGORY_PILLS": pills,
        "CONTACT_URL": url_of(contact["slug"]) if contact else "/",
        "SEO_TAGS": "",
    }), encoding="utf-8")


def cms_url():
    """URL /exec cua he thong quan tri - khai DUY NHAT trong static/admin/config.js."""
    cfg = STATIC / "admin" / "config.js"
    m = re.search(r"DANDAN_CMS_URL\s*=\s*['\"]([^'\"]+)['\"]", cfg.read_text(encoding="utf-8")) if cfg.exists() else None
    return m.group(1) if m else ""


def build_admin_api(site):
    """Trang huong dan API cho AI: html/admin/api/index.html (GAS.md muc XI). Dia chi API ghi
    THANG vao HTML (khong dien bang JS) de AI tai trang ve doc la thay ngay."""
    api_url = cms_url()
    if not api_url:
        print("WARN: static/admin/config.js chua co DANDAN_CMS_URL - trang /admin/api/ thieu dia chi API")
    values = site.common()
    values.update({"API_URL": esc(api_url) or "&lt;API URL&gt;", "SITE_URL": esc(site.domain)})
    html = render(load_template("admin-api.html"), values).replace("__KEY__", "&lt;KEY&gt;")
    write_page("admin/api", html)


def build_sitemap(site):
    d = site.domain
    urls = [(d, site.posts[0].get("updated_at") if site.posts else "", "1.0")]
    for c in site.categories:
        urls.append((d + c["slug"] + "/", "", "0.8"))
    for p in site.posts:
        urls.append((d + p["slug"] + "/", p.get("updated_at") or p.get("date"), "0.9"))
    for p in site.pages:
        urls.append((d + p["slug"] + "/", p.get("updated_at", ""), "0.6"))
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, prio in urls:
        lm = "\n    <lastmod>%s</lastmod>" % esc(date_iso(lastmod)) if lastmod else ""
        parts.append("  <url>\n    <loc>%s</loc>%s\n    <priority>%s</priority>\n  </url>" % (esc(loc), lm, prio))
    parts.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(parts) + "\n", encoding="utf-8")


def build_feed(site):
    w = site.website
    items = []
    for p in site.posts[:20]:
        link = site.domain + p["slug"] + "/"
        items.append(
            "    <item>\n      <title>%s</title>\n      <link>%s</link>\n      <guid isPermaLink=\"true\">%s</guid>\n"
            "      <pubDate>%s</pubDate>\n      <description>%s</description>\n    </item>" % (
                esc(p["title"]), esc(link), esc(link), rfc822(p.get("date")), esc(p.get("description", ""))))
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n  <channel>\n'
        "    <title>%s</title>\n    <link>%s</link>\n    <description>%s</description>\n    <language>%s</language>\n%s\n"
        "  </channel>\n</rss>\n") % (esc(w["site_name"]), esc(site.domain), esc(w.get("description", "")),
                                     esc(w.get("lang", "en")), "\n".join(items))
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
    global OUT
    parser = argparse.ArgumentParser(description="Build site tinh DanDan Stories")
    parser.add_argument("--demo", action="store_true", help="du lieu mau demo/ -> html-demo/ (khong dung html/ that)")
    args = parser.parse_args()

    data_dir = ROOT / ("demo/data" if args.demo else "data")
    if args.demo:
        OUT = ROOT / "html-demo"
    website, categories, posts, pages = load_data(data_dir)
    if not check_slugs(categories, posts, pages):
        sys.exit(1)

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT)
    if args.demo and (ROOT / "demo/static").exists():
        shutil.copytree(ROOT / "demo/static", OUT, dirs_exist_ok=True)

    site = Site(website, categories, posts, pages)
    for post in site.posts:
        build_post(site, post)
    for cat in site.categories:
        build_category(site, cat)
    for page in site.pages:
        build_page(site, page)
    build_home(site)
    build_404(site)
    build_admin_api(site)
    build_sitemap(site)
    build_feed(site)
    build_misc(site)
    print("Done (%s): %d bai, %d danh muc, %d trang tinh -> %s/" % (
        "demo" if args.demo else "data", len(site.posts), len(site.categories), len(site.pages), OUT.name))


if __name__ == "__main__":
    main()
