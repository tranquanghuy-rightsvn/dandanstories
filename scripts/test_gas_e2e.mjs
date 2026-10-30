#!/usr/bin/env node
/**
 * Test end-to-end gas/Code.js KHÔNG cần deploy: giả lập dịch vụ Google (Properties, Cache, Sheet,
 * Mail, Utilities, HtmlService) + GitHub Contents API trong bộ nhớ, chạy trọn luồng CMS thật
 * (OTP -> danh mục -> ảnh bìa -> bài viết -> ảnh nội dung -> trang tĩnh -> cài đặt -> xoá), rồi
 * đổ "repo giả" ra thư mục tạm và chạy scripts/build.py trên đó để chắc dữ liệu CMS ghi ra build
 * được thành site.
 *
 * Dùng: node scripts/test_gas_e2e.mjs   (exit 0 = ổn)
 */
import { readFileSync, mkdirSync, writeFileSync, cpSync, rmSync, existsSync, mkdtempSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import vm from "node:vm";
import assert from "node:assert/strict";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OWNER = "owner@example.com";

// ---------- bytes kiểu GAS (mảng số có dấu) ----------
const toSigned = (buf) => Array.from(buf, (b) => (b > 127 ? b - 256 : b));
const toBuf = (arr) => Buffer.from(arr.map((b) => (b < 0 ? b + 256 : b)));

// ---------- GitHub giả ----------
const repo = new Map(); // path -> Buffer
let commits = 0;
const shaOf = (buf) => crypto.createHash("sha1").update(buf).digest("hex");

// Ảnh "trên mạng" cho API tải về (https://img.example/<tên>.<ext>).
const remoteImages = { "cover.jpg": "image/jpeg", "inline.png": "image/png", "anim.gif": "image/gif" };

function ghFetch(url, opts = {}) {
  const u = new URL(url);
  if (u.hostname === "img.example") {
    const name = u.pathname.slice(1);
    const type = remoteImages[name];
    const body = Buffer.from("remote-" + name);
    return {
      getResponseCode: () => (type ? 200 : 404),
      getContentText: () => "",
      getBlob: () => ({ getContentType: () => type, getBytes: () => toSigned(body) }),
    };
  }
  const m = u.pathname.match(/^\/repos\/o\/r\/contents\/(.*)$/);
  const res = (code, body) => ({ getResponseCode: () => code, getContentText: () => JSON.stringify(body) });
  if (!m) return res(404, { message: "not found" });
  const path = decodeURI(m[1]);
  const method = (opts.method || "get").toLowerCase();
  if (method === "get") {
    if (repo.has(path)) {
      const buf = repo.get(path);
      return res(200, { type: "file", sha: shaOf(buf), content: buf.toString("base64") });
    }
    const prefix = path + "/";
    const names = new Map();
    for (const k of repo.keys()) {
      if (!k.startsWith(prefix)) continue;
      const rest = k.slice(prefix.length);
      const [first, ...more] = rest.split("/");
      names.set(first, more.length ? "dir" : "file");
    }
    if (!names.size) return res(404, { message: "Not Found" });
    return res(200, [...names].map(([name, type]) => ({ name, type })));
  }
  const body = JSON.parse(opts.payload);
  if (method === "put") {
    if (repo.has(path) && body.sha !== shaOf(repo.get(path))) return res(409, { message: "sha mismatch" });
    if (!repo.has(path) && body.sha) return res(422, { message: "sha not expected" });
    repo.set(path, Buffer.from(body.content, "base64"));
    commits++;
    return res(201, { content: { path } });
  }
  if (method === "delete") {
    repo.delete(path);
    commits++;
    return res(200, {});
  }
  return res(400, {});
}

// ---------- Sheet giả ----------
function makeSheet() {
  let rows = [];
  const sheet = {
    name: "",
    setName(n) { this.name = n; },
    setFrozenRows() {},
    getRange(r, c, nr = 1, nc = 1) {
      return {
        setValues(vals) { vals.forEach((row, i) => row.forEach((v, j) => { (rows[r - 1 + i] ||= [])[c - 1 + j] = v; })); },
        setValue(v) { (rows[r - 1] ||= [])[c - 1] = v; },
      };
    },
    getDataRange() { return { getValues: () => rows.map((r) => r.slice()) }; },
    appendRow(row) { rows.push(row.slice()); },
    deleteRow(i) { rows.splice(i - 1, 1); },
  };
  return sheet;
}
const sheets = new Map();
const spreadsheet = {
  getSheets: () => [sheets.get("__first")],
  getId: () => "ss1",
  getUrl: () => "https://example/ss1",
  getSheetByName: (n) => [...sheets.values()].find((s) => s.name === n) || null,
};

// ---------- môi trường GAS ----------
const props = new Map([
  ["GITHUB_TOKEN", "t"], ["GITHUB_OWNER", "o"], ["GITHUB_REPO", "r"], ["GITHUB_BRANCH", "main"],
]);
const cache = new Map();
const mails = [];
const readGas = (name) => readFileSync(join(ROOT, "gas", name + ".html"), "utf8");

const ctx = {
  console,
  PropertiesService: {
    getScriptProperties: () => ({
      getProperty: (k) => (props.has(k) ? props.get(k) : null),
      setProperty: (k, v) => props.set(k, String(v)),
      deleteProperty: (k) => props.delete(k),
      getProperties: () => Object.fromEntries(props),
    }),
  },
  CacheService: {
    getScriptCache: () => ({
      get: (k) => (cache.has(k) ? cache.get(k) : null),
      put: (k, v) => cache.set(k, String(v)),
      remove: (k) => cache.delete(k),
    }),
  },
  SpreadsheetApp: {
    create: () => { const s = makeSheet(); sheets.set("__first", s); return spreadsheet; },
    openById: (id) => { if (id !== "ss1") throw new Error("no"); return spreadsheet; },
  },
  Session: { getEffectiveUser: () => ({ getEmail: () => OWNER }), getScriptTimeZone: () => "Asia/Ho_Chi_Minh" },
  MailApp: { sendEmail: (m) => mails.push(m), getRemainingDailyQuota: () => 100 },
  Logger: { log() {} },
  ScriptApp: { getService: () => ({ getUrl: () => "https://script.google.com/macros/s/TEST/exec" }) },
  UrlFetchApp: { fetch: ghFetch },
  HtmlService: {
    createTemplateFromFile: (n) => ({ evaluate: () => ({ getContent: () => readGas(n) }) }),
    createHtmlOutputFromFile: (n) => ({ getContent: () => readGas(n) }),
  },
  ContentService: { createTextOutput: (t) => ({ setMimeType: () => t }), MimeType: { JSON: "json" } },
  Utilities: {
    getUuid: () => crypto.randomUUID(),
    sleep() {},
    formatDate: (d, tz, fmt) => {
      const p = Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
        timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
      }).formatToParts(d).map((x) => [x.type, x.value]));
      return fmt.replace("yyyy", p.year).replace("MM", p.month).replace("dd", p.day)
        .replace("HH", p.hour === "24" ? "00" : p.hour).replace("mm", p.minute).replace("ss", p.second).replace(/'/g, "");
    },
    base64Encode: (bytes) => toBuf(bytes).toString("base64"),
    base64Decode: (s) => toSigned(Buffer.from(s, "base64")),
    newBlob: (data) => {
      const buf = typeof data === "string" ? Buffer.from(data, "utf8") : toBuf(data);
      return { getBytes: () => toSigned(buf), getDataAsString: () => buf.toString("utf8") };
    },
    computeDigest: (_a, s) => toSigned(crypto.createHash("md5").update(s).digest()),
    DigestAlgorithm: { MD5: "md5" },
    Charset: { UTF_8: "utf8" },
  },
};
vm.createContext(ctx);
vm.runInContext(readFileSync(join(ROOT, "gas/Code.js"), "utf8"), ctx, { filename: "gas/Code.js" });
vm.runInContext(readFileSync(join(ROOT, "gas/Api.js"), "utf8"), ctx, { filename: "gas/Api.js" });
const call = (fn, ...args) => ctx[fn](...args);
const throws = (fn, re, ...args) => assert.throws(() => call(fn, ...args), re, fn + " phải báo lỗi " + re);
const img = (ext) => "data:image/" + ext + ";base64," + Buffer.from("fake-" + ext + "-" + Math.random()).toString("base64");
const json = (p) => JSON.parse(repo.get(p).toString("utf8"));

// ---------- kịch bản ----------
// Repo khởi đầu như repo thật mới tạo (data rỗng).
for (const f of ["website", "categories", "posts", "pages"]) {
  repo.set("data/" + f + ".json", readFileSync(join(ROOT, "data", f + ".json")));
}

assert.equal(call("setup"), "OK");

// 1. Đăng nhập: người lạ bị chặn; chủ script đăng nhập được dù Sheet Users rỗng.
throws("requestOtp", /không có trong danh sách/, "stranger@example.com");
call("requestOtp", OWNER);
const code = /(\d{6})/.exec(mails.at(-1).body)[1];
throws("verifyOtp", /không đúng/, OWNER, "000000");
const { token } = call("verifyOtp", OWNER, code);
const boot0 = call("boot", token);
assert.equal(boot0.me.role, "root");
assert.equal(call("boot", "sai-token").me.role, null);

// 2. Người dùng: thêm editor, editor không được vào cài đặt.
call("saveUser", token, "editor@example.com", "editor");
throws("saveUser", /chính mình|chủ hệ thống/, token, OWNER, "admin");
call("requestOtp", "editor@example.com");
const edCode = /(\d{6})/.exec(mails.at(-1).body)[1];
const edToken = call("verifyOtp", "editor@example.com", edCode).token;
throws("saveWebsite", /Không đủ quyền/, edToken, { site_name: "x" });
throws("listUsersForAdmin", /Không đủ quyền/, edToken);

// 3. Danh mục + chặn slug hệ thống.
throws("saveCategory", /đường dẫn hệ thống/, edToken, { isNew: true, name: "Admin" });
call("saveCategory", edToken, { isNew: true, name: "Đời thường", description: "Chuyện mỗi ngày", order: 1 });
call("saveCategory", edToken, { isNew: true, name: "Hành trình", order: 2 });
throws("saveCategory", /đã tồn tại/, edToken, { isNew: true, name: "Đời thường" });
assert.deepEqual(json("data/categories.json").map((c) => c.slug), ["doi-thuong", "hanh-trinh"]);

// 4. Bài viết: thiếu ảnh bìa bị chặn; có ảnh bìa + ảnh nội dung thì lưu được.
const title = 'Bát cơm "chiều" mưa & nỗi nhớ';
throws("savePost", /ảnh bìa/, edToken, { isNew: true, title, category: "doi-thuong" });
const cover = call("uploadPostCover", edToken, "bat-com-chieu-mua-noi-nho", img("webp"), img("webp"));
assert.match(cover.lg, /^images\/posts\/bat-com-chieu-mua-noi-nho\/cover-lg\.webp\?v=/);
const c1 = call("uploadContentImage", edToken, "post", "bat-com-chieu-mua-noi-nho", img("webp"));
const c2 = call("uploadContentImage", edToken, "post", "bat-com-chieu-mua-noi-nho", img("jpeg"));
assert.equal(c1.src, "/images/posts/bat-com-chieu-mua-noi-nho/content-1.webp");
assert.equal(c2.src, "/images/posts/bat-com-chieu-mua-noi-nho/content-2.jpg");
const content = '<p>Mở đầu {{TITLE}} không được bị thay.</p><figure><img src="' + c1.src + '" alt="x"><figcaption>Ảnh 1</figcaption></figure>';
const meta = call("savePost", edToken, {
  isNew: true, title, category: "doi-thuong", description: "Mô tả <ngắn>", keywords: "gia đình,  mưa ,",
  featured: true, cover, content_html: content,
});
assert.equal(meta.slug, "bat-com-chieu-mua-noi-nho");
assert.equal(meta.keywords, "gia đình, mưa");
throws("savePost", /đã tồn tại/, edToken, { isNew: true, title, category: "doi-thuong", cover });
// Sửa: giữ ngày đăng gốc.
const meta2 = call("savePost", edToken, { isNew: false, slug: meta.slug, title: title + " (sửa)", category: "hanh-trinh", cover, content_html: content });
assert.equal(meta2.date, meta.date);
assert.equal(call("getPost", edToken, meta.slug).content_html, content);

// Bản nháp: lưu được, build bỏ qua.
const draftCover = call("uploadPostCover", edToken, "ban-nhap", img("jpeg"), img("jpeg"));
call("savePost", edToken, { isNew: true, title: "Bản nháp", category: "doi-thuong", draft: true, cover: draftCover, content_html: "<p>nháp</p>" });

// 5. Slug duy nhất toàn site: trang tĩnh trùng slug bài viết bị chặn.
throws("savePage", /đã được dùng/, edToken, { isNew: true, title: "Bản nháp" });
call("savePage", edToken, { isNew: true, title: "Giới thiệu", description: "Về chúng tôi", show_in_menu: true, content_html: "<p>Xin chào</p>" });
call("savePage", edToken, { isNew: true, title: "Liên hệ", content_html: "<p>Email</p>" });

// 6. Cài đặt website (admin/root).
throws("saveWebsite", /https:\/\//, token, { site_name: "DanDan", domain_url: "dandan.com" });
const w = call("saveWebsite", token, { site_name: "DanDan Stories", domain_url: "https://rapidfanpost.com", ga_id: "G-ABC123", ads_txt: "google.com, pub-1, DIRECT" });
assert.equal(w.domain_url, "https://rapidfanpost.com/");
call("uploadSiteImage", token, "logo", img("png"));
const w2 = call("uploadSiteImage", token, "logo", img("webp"));
assert.ok(!repo.has("static/images/site/logo.png"), "logo đuôi cũ phải bị xoá");
assert.match(w2.logo, /^images\/site\/logo\.webp\?v=/);

// 7. Xoá: danh mục còn bài bị chặn; xoá bài kéo theo ảnh.
throws("deleteCategory", /Còn 1 bài viết/, edToken, "hanh-trinh");
call("deletePost", edToken, "ban-nhap");
assert.ok(![...repo.keys()].some((k) => k.startsWith("static/images/posts/ban-nhap/")), "ảnh bài đã xoá phải bị xoá");
call("deletePage", edToken, "lien-he");

// 7b. API cho AI (GAS.md mục XI).
throws("createApiKey", /Không đủ quyền/, edToken, "x");
const { key: apiKey } = call("createApiKey", token, "Máy ở nhà");
assert.match(apiKey, /^dds_[0-9a-f]{64}$/);
assert.equal(call("boot", apiKey).me.role, null, "khoá không mở được giao diện quản trị");
throws("saveWebsite", /Không đủ quyền/, apiKey, { site_name: "x" });
const api = (payload, method = "POST") => call("handleApi_", payload, method);
assert.equal(api({ action: "ping" }).ok, false);
assert.match(api({ action: "ping", key: "dds_sai" }).error, /Invalid or revoked/);
assert.match(api({ action: "nope", key: apiKey }).error, /Unknown action/);
const ping = api({ action: "ping", key: apiKey }, "GET");
assert.equal(ping.ok, true);
assert.equal(ping.data.guide, "https://rapidfanpost.com/admin/api/");
assert.match(api({ action: "post.create", key: apiKey, title: "X" }, "GET").error, /must be called with POST/);
assert.match(api({ action: "post.create", key: apiKey, title: "A Night Train", category: "nope", cover: "https://img.example/cover.jpg" }).error, /Category "nope" does not exist/);
assert.match(api({ action: "post.create", key: apiKey, title: "A Night Train", category: "hanh-trinh" }).error, /Missing "cover"/);
assert.match(api({ action: "post.create", key: apiKey, title: "Gif", category: "hanh-trinh", cover: "https://img.example/anim.gif" }).error, /Use JPEG, PNG or WebP/);
const created = api({
  action: "post.create", key: apiKey, title: "A Night Train to Hue", category: "hanh-trinh",
  description: "Thirteen hours on a sleeper train.", keywords: ["night train", "slow travel"],
  cover: "https://img.example/cover.jpg",
  content_html: '<h1>Big</h1><p onclick="x()">Hello</p><script>alert(1)</script><figure><img src="https://img.example/inline.png" alt="Window"><figcaption>Window</figcaption></figure>',
});
assert.equal(created.ok, true, created.error);
const rec = created.data.record;
assert.equal(rec.slug, "a-night-train-to-hue");
assert.equal(rec.url, "https://rapidfanpost.com/a-night-train-to-hue/");
assert.equal(rec.keywords, "night train, slow travel");
assert.match(rec.cover.lg, /^images\/posts\/a-night-train-to-hue\/cover-lg\.jpg/);
const got = api({ action: "post.get", key: apiKey, slug: rec.slug }, "GET").data;
assert.ok(!/script|onclick|<h1/i.test(got.content_html), "HTML từ API phải được lọc: " + got.content_html);
assert.ok(got.content_html.includes('src="/images/posts/a-night-train-to-hue/content-1.png"'), "ảnh ngoài phải được tải về: " + got.content_html);
assert.match(api({ action: "post.create", key: apiKey, title: "A Night Train to Hue", category: "hanh-trinh", cover: "https://img.example/cover.jpg" }).error, /already exists/);
const upd = api({ action: "post.update", key: apiKey, slug: rec.slug, featured: true });
assert.equal(upd.ok, true, upd.error);
assert.equal(upd.data.record.featured, true);
assert.equal(upd.data.record.title, "A Night Train to Hue", "field không gửi phải giữ nguyên");
assert.equal(api({ action: "post.get", key: apiKey, slug: rec.slug }).data.content_html, got.content_html, "update không gửi content giữ nguyên nội dung");
assert.equal(api({ action: "post.list", key: apiKey, q: "night train" }, "GET").data.total, 1);
const up = api({ action: "image.upload", key: apiKey, kind: "post", slug: rec.slug, data: Buffer.from("x").toString("base64"), filename: "a.webp" });
assert.equal(up.data.path, "/images/posts/a-night-train-to-hue/content-2.webp");
const cat = api({ action: "category.create", key: apiKey, name: "Short Fiction", order: 9 });
assert.equal(cat.data.record.slug, "short-fiction");
assert.equal(api({ action: "category.update", key: apiKey, slug: "short-fiction", description: "Tiny tales" }).data.record.description, "Tiny tales");
const pg = api({ action: "page.create", key: apiKey, title: "Privacy Policy", content_html: "<p>We keep nothing.</p>" });
assert.equal(pg.ok, true, pg.error);
assert.equal(api({ action: "page.get", key: apiKey, slug: "privacy-policy" }).data.content_html, "<p>We keep nothing.</p>");
assert.equal(api({ action: "page.update", key: apiKey, slug: "privacy-policy", show_in_menu: true }).data.record.show_in_menu, true);
assert.equal(api({ action: "post.delete", key: apiKey, slug: rec.slug }).ok, true);
assert.ok(![...repo.keys()].some((k) => k.startsWith("static/images/posts/a-night-train-to-hue/")), "xoá bài qua API phải xoá ảnh");
assert.equal(api({ action: "category.delete", key: apiKey, slug: "short-fiction" }).ok, true);
assert.equal(call("listApiKeys", token)[0].calls > 5, true);
call("revokeApiKey", token, apiKey);
assert.match(api({ action: "ping", key: apiKey }).error, /Invalid or revoked/);
assert.equal(call("boot", token).apiUrl, "https://script.google.com/macros/s/TEST/exec");

// 8. Boot trả đủ dữ liệu.
const b = call("boot", token);
assert.equal(b.posts.length, 1);
assert.equal(b.pages.length, 2);
assert.equal(b.categories.length, 2);
assert.ok(b.appHtml.includes("tab-post-editor"));
assert.equal(call("logout", token).ok, true);
assert.equal(call("boot", token).me.role, null);

// ---------- build site từ repo giả ----------
const tmp = mkdtempSync(join(tmpdir(), "dandan-e2e-"));
try {
  for (const d of ["templates", "scripts", "static"]) cpSync(join(ROOT, d), join(tmp, d), { recursive: true });
  for (const [p, buf] of repo) {
    mkdirSync(dirname(join(tmp, p)), { recursive: true });
    writeFileSync(join(tmp, p), buf);
  }
  const out = execFileSync("python3", [join(tmp, "scripts/build.py")], { encoding: "utf8" });
  assert.match(out, /1 bai, 2 danh muc, 2 trang tinh/);
  assert.doesNotMatch(out, /WARN|ERROR/);
  const post = readFileSync(join(tmp, "html/bat-com-chieu-mua-noi-nho/index.html"), "utf8");
  assert.ok(post.includes("{{TITLE}} không được bị thay"), "nội dung chứa {{...}} phải giữ nguyên");
  assert.ok(post.includes("Bát cơm &quot;chiều&quot; mưa &amp; nỗi nhớ (sửa)"), "tiêu đề phải được escape");
  assert.ok(post.includes('src="/images/posts/bat-com-chieu-mua-noi-nho/content-1.webp" alt="x" loading="lazy"'));
  assert.ok(post.includes("G-ABC123"));
  assert.ok(existsSync(join(tmp, "html/images/posts/bat-com-chieu-mua-noi-nho/cover-lg.webp")));
  assert.ok(!existsSync(join(tmp, "html/ban-nhap")), "bài đã xoá không được build");
  assert.ok(existsSync(join(tmp, "html/hanh-trinh/index.html")) && existsSync(join(tmp, "html/gioi-thieu/index.html")));
  assert.equal(readFileSync(join(tmp, "html/ads.txt"), "utf8").trim(), "google.com, pub-1, DIRECT");
  const home = readFileSync(join(tmp, "html/index.html"), "utf8");
  assert.ok(home.includes('src="/images/site/logo.webp?v='), "logo phải lên header");
  assert.ok(home.includes('href="/gioi-thieu/"'), "trang hiện ở menu trên phải có trong nav");
} finally {
  rmSync(tmp, { recursive: true, force: true });
}

console.log("test_gas_e2e: OK (" + commits + " commit giả lập, " + mails.length + " mail OTP)");
