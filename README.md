# DanDan Stories

Website kể chuyện (blog tĩnh) + trang quản trị CMS, chi phí vận hành ~0đ.
Kiến trúc theo playbook `free-cms-static-site-pipeline` (giống dự án TrithucWorld, phần CMS theo
mẫu xevip). **Quyết định nghiệp vụ chốt ở [`GAS.md`](GAS.md) — đọc trước khi sửa code CMS.**

```
CMS (Google Apps Script, thư mục gas/)  ── đăng nhập OTP qua email, soạn bài, tải ảnh
   │  ghi qua GitHub Contents API
   ▼
Repo GitHub: data/*.json (nội dung) + static/images/** (ảnh)
   │  push vào 1 trong 4 file "chốt" data/{website,categories,posts,pages}.json
   ▼
GitHub Actions: python3 scripts/build.py -> html/ -> commit "CI: build html from data" vào repo
   │  html/ đổi
   ▼
Cloudflare Workers Builds (kết nối thẳng repo, không build gì): wrangler deploy html/
   ▼
Cloudflare Workers Static Assets (free, cho phép thương mại, băng thông không giới hạn)
```

URL đều dạng thư mục: bài viết, danh mục, trang tĩnh nằm ở `/<slug>/` (file `<slug>/index.html`),
phân trang danh mục `/<slug>/trang-2/`, tìm kiếm `/tim-kiem/`, quản trị `/admin/`.

## Cấu trúc thư mục

| Thư mục / file | Vai trò | Ai sửa |
|---|---|---|
| `templates/*.html`, `templates/partials/*.html` | Giao diện (placeholder `{{TOKEN}}`) | Dev, sửa tay |
| `static/assets/css/style.css`, `static/assets/js/main.js` | CSS/JS của site | Dev, sửa tay |
| `static/admin/index.html` | Trang `/admin/` nhúng CMS (biến `CMS_URL`) | Dev, 1 lần sau deploy CMS |
| `static/vendor/tinymce/` | Trình soạn thảo tự host (TinyMCE 6.8.5) | Không cần đụng |
| `static/images/**` | Ảnh bài viết/trang/site | CMS tự ghi |
| `data/*.json`, `data/posts/*.json` | Nội dung | CMS tự ghi — **không sửa tay** |
| `scripts/build.py` | Builder (Python stdlib, không cần cài gì) | Dev |
| `html/` | Output build — GitHub Actions xoá sạch, sinh lại và commit; Cloudflare deploy từ đây | Không ai sửa tay |
| `gas/` | Code CMS — **gitignore**, deploy bằng `clasp` | Dev |
| `demo/` | Dữ liệu mẫu để xem trước giao diện | Dev |

## Xem thử ở máy

```bash
python3 scripts/build.py --demo                     # dữ liệu mẫu (9 bài, 4 danh mục) -> html-demo/
python3 -m http.server 8000 --directory html-demo   # mở http://localhost:8000
python3 scripts/build.py                            # dữ liệu thật (data/) -> html/ (CI cũng chạy đúng lệnh này)
```

Kiểm tra trước khi deploy CMS:

```bash
node scripts/check_gas_client.mjs   # chạy thử client CMS với DOM giả (mọi quyền, mọi tab)
node scripts/test_gas_e2e.mjs       # chạy trọn luồng server CMS trên dịch vụ giả lập + build ra site
```

## Dựng website từ đầu

### 1. GitHub repo

1. Tạo repo (private hoặc public) — ví dụ `dandanstories`, nhánh `main`.
2. Đẩy code lên:
   ```bash
   git init -b main && git add . && git commit -m "Khởi tạo DanDan Stories"
   git remote add origin git@github.com:<owner>/dandanstories.git && git push -u origin main
   ```
   (`gas/` nằm trong `.gitignore`; `html/` ĐƯỢC commit - do GitHub Actions sinh ra.)
3. Tạo **fine-grained Personal Access Token**: chỉ chọn đúng repo này, quyền
   *Contents: Read and write*. Token này dành riêng cho CMS.

### 2. Build (GitHub Actions) + deploy (Cloudflare)

**GitHub Actions** (`.github/workflows/build.yml`) - không cần secret nào:
- Chạy khi 1 trong 4 file chốt `data/{posts,pages,categories,website}.json` đổi, hoặc khi đổi
  `templates/`, `static/` (trừ `static/images/`), `scripts/build.py`. Chạy tay: tab Actions ›
  *Build HTML DanDan Stories* › Run workflow.
- Build `html/` rồi commit `CI: build html from data` vào repo. Repo › Settings › Actions ›
  General › Workflow permissions phải là **Read and write** (workflow đã khai `contents: write`,
  nhưng org/repo đặt chế độ read-only thì vẫn bị chặn).

**Cloudflare** (Workers Builds, kết nối thẳng repo - không dùng API token):
1. Workers & Pages › Create › **Import a repository** › repo `dandanstories`, nhánh `master`.
2. Cấu hình:
   | Mục | Giá trị |
   |---|---|
   | Worker name | `dandanstories` (PHẢI trùng `name` trong `wrangler.toml`) |
   | Build command | để trống (`html/` đã được GitHub Actions build sẵn) |
   | Deploy command | `npx wrangler deploy` |
3. Settings › Build › **Build watch paths**: Include `html/*`, `wrangler.toml` - chỉ deploy khi
   bản build mới được commit, không deploy theo từng commit ảnh/dữ liệu của CMS.
4. Gắn tên miền: Worker › Settings › Domains & Routes › Custom Domain `dandanstories.com`.
   Kiểm tra: `curl -sI https://dandanstories.com/ | grep -i server` phải ra `cloudflare`.

### 3. CMS (Google Apps Script)

1. `npm i -g @google/clasp && clasp login`
2. Trong thư mục dự án: `clasp create --type webapp --title "DanDan Stories CMS" --rootDir gas`
   (lệnh này tạo `.clasp.json` — đã gitignore).
3. `clasp push`
4. Mở editor (`clasp open`) › Project Settings › Script Properties, điền:
   | Property | Giá trị |
   |---|---|
   | `GITHUB_TOKEN` | token ở bước 1.3 |
   | `GITHUB_OWNER` | user/org GitHub |
   | `GITHUB_REPO` | `dandanstories` |
   | `GITHUB_BRANCH` | `main` |
   | `SITE_URL` | `https://dandanstories.com/` — điền SAU khi site đã chạy (để trình soạn thảo tải từ chính site); trước đó để trống |
   | `SPREADSHEET_ID` | **không điền** — tự tạo lần đầu |
5. Chọn hàm `setup` › Run 1 lần trong editor: Google hỏi cấp quyền (Mail, Sheets, gọi URL ngoài),
   rồi tự tạo Sheet Users + kiểm tra đọc được repo (xem Execution log, phải ra "Đọc repo OK").
6. **Deploy › New deployment › Web app**: Execute as *Me*, Who has access *Anyone*. Copy URL `/exec`.
7. Dán URL đó vào biến `CMS_URL` trong `static/admin/index.html`, commit + push.

   URL đang dùng (deploy 30/10/2026 — sửa CMS thì deploy **New version**, URL này không đổi):
   `https://script.google.com/macros/s/AKfycbxyzZ9Cfnb0BC3MbsdpGvufPM5friJT4bPMQGgtiScO30iVE3gFoYdee9rsEx2uxwZlWQ/exec`
8. Mở `https://dandanstories.com/admin/` (hoặc thẳng URL `/exec`), đăng nhập bằng **email Google
   đã deploy** (luôn là quyền cao nhất, không cần khai báo).

Các lần sửa CMS sau: `clasp push` › Deploy › Manage deployments › Edit › **New version**
(KHÔNG dùng "New deployment" — sẽ sinh URL mới). Không cần tự đổi phiên bản client: server tự băm
từ nội dung `app.html` + `js.html`, cache cũ trên máy người dùng tự hết hiệu lực.

### 4. Nhập nội dung qua CMS (đúng thứ tự)

1. **Cài đặt website**: tên, khẩu hiệu, mô tả SEO, tên miền, thông tin liên hệ, mạng xã hội;
   tải logo, favicon, ảnh chia sẻ mặc định.
2. **Danh mục**: tạo ít nhất 1 danh mục (bài viết bắt buộc có danh mục).
3. **Trang tĩnh**: Giới thiệu, Liên hệ, Chính sách bảo mật...
4. **Bài viết**: tiêu đề → ảnh bìa → nội dung (nút ảnh trên thanh công cụ để chèn ảnh) → Lưu.
5. **Người dùng**: thêm email biên tập viên (`editor`) hoặc quản trị (`admin`).

Mỗi lần Lưu/Xoá, website tự build lại và cập nhật sau ~1-2 phút.

## Sửa giao diện

- Sửa `templates/` hoặc `static/assets/`, chạy `python3 scripts/build.py --demo` để xem, rồi
  commit + push — GitHub Actions build lại `html/`, Cloudflare deploy (CSS/JS có `?v=<hash>` nên không dính cache cũ).
- Trước khi push, nhớ `git pull`: CMS và GitHub Actions commit thẳng lên repo nên lịch sử 2 bên
  thường lệch. Không `push --force`. Không commit `html/` do mình tự build ở máy nếu khác với CI -
  cứ để GitHub Actions sinh (nếu lỡ lệch, lần build kế tiếp tự ghi đè).

## Lưu ý vận hành

- Quota Gmail 100 mail/ngày/tài khoản Google dùng cho mã OTP — thừa với vài người quản trị.
- Ảnh đặt tên cố định theo đường dẫn bài, xoá bài là xoá luôn ảnh. Đường dẫn (slug) **không đổi
  được** sau khi lưu lần đầu — muốn đổi thì xoá và tạo bài mới.
- Ảnh đã tải nhưng bỏ dở không lưu bài sẽ nằm lại trong `static/images/posts/<slug>/` (vô hại,
  xoá tay trên GitHub nếu muốn).
- Trang `/admin/` có `noindex` (meta + header `X-Robots-Tag` trong `static/_headers`), cố ý
  KHÔNG khai trong `robots.txt`. Bảo mật thật nằm ở đăng nhập OTP + kiểm tra quyền phía server.
- Nếu nhúng `/admin/` bị treo (trình duyệt đang đăng nhập Google Workspace của tổ chức), trang tự
  hiện nút "Mở ở tab riêng" sau 12 giây.
