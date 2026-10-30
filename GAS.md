# GAS.md — Quyết định nghiệp vụ CMS DanDan Stories

Nguồn chân lý cho mọi file trong `gas/` và `scripts/build.py`. Đọc TOÀN BỘ trước khi sửa code.
Đổi quyết định nào thì sửa code VÀ file này trong cùng 1 lượt (không để lệch pha).

Dự án theo playbook `free-cms-static-site-pipeline`, mô hình nội dung giống TrithucWorld
(bài viết + danh mục + trang tĩnh + cài đặt website), phần GAS dựa trên mẫu xevip.

## 0. Phạm vi

Website công khai **hoàn toàn tiếng Anh** (độc giả quốc tế): giao diện, chữ do build sinh,
định dạng ngày `Oct 28, 2026`, `lang=en`. **Giao diện giống hệt TrithucWorld** (template lấy từ
`trithucworld/remake/templates/`, chỉ dịch chữ + đổi link sang `/slug/`) — không tự thiết kế lại.
Trang quản trị (CMS) vẫn tiếng Việt cho người vận hành. Nội dung viết bằng tiếng Anh → slug tự
sinh từ tiêu đề cũng là tiếng Anh.

CMS quản lý ĐÚNG 6 mục: Bài viết, Danh mục, Trang tĩnh, Cài đặt website, Người dùng, Kết nối AI
(mục XI).
Site 100% tĩnh — không có form công khai, không bình luận, không tài khoản người đọc.
Website dựng được TỪ ĐẦU hoàn toàn qua CMS: repo khởi đầu với dữ liệu rỗng, build vẫn chạy và
trang chủ hiện trạng thái "đang chuẩn bị nội dung" cho tới khi có bài đầu tiên.

## I. Đăng nhập

1. Luồng: nhập email → nhận OTP qua email → nhập OTP → vào Admin. Không mật khẩu.
2. Chỉ email có trong Sheet `Users` mới được gửi OTP.
3. Chủ script (người deploy) LUÔN là `root` ngầm định, không cần (và không hiện) trong `Users`.
   `requestOtp` tự cho qua email chủ script (`ownerEmail_()`).
4. Phân quyền 3 cấp `root > admin > editor`:
   | Việc | editor | admin | root |
   |---|---|---|---|
   | Bài viết, Trang tĩnh, Danh mục (thêm/sửa/xoá) | ✔ | ✔ | ✔ |
   | Cài đặt website | | ✔ | ✔ |
   | Người dùng (chỉ thêm/sửa/xoá admin + editor) | | ✔ | ✔ |
   | Kết nối AI (tạo/thu hồi khoá API) | | ✔ | ✔ |
   Dòng `root` chỉ sửa tay trong Sheet. Không tự sửa/xoá chính mình qua CMS.
5. OTP sống 10 phút, cooldown 60 giây/email, sai 5 lần phải xin mã mới. Token sống 30 ngày,
   lưu `localStorage`. `verifyOtp` dọn token hết hạn (`purgeExpiredTokens_`), Đăng xuất thu hồi
   token phía server (`logout`).
6. Server tự `requireRole_` ở MỌI hàm — ẩn menu trên giao diện không phải bảo mật.

## II. Bài viết

1. Field có ô nhập:
   - Tiêu đề (bắt buộc)
   - Đường dẫn (slug) — tự sinh từ tiêu đề, bỏ dấu, gạch ngang. URL công khai `/<slug>/`.
   - Danh mục (bắt buộc, chọn từ tab Danh mục)
   - Mô tả ngắn — dùng cho thẻ bài ngoài danh sách VÀ meta description.
   - Từ khoá / thẻ (phân cách dấu phẩy) — meta keywords + `article:tag` + hiện cuối bài.
   - Tác giả — để trống thì lấy "Tác giả mặc định" trong Cài đặt website.
   - Ảnh bìa (bắt buộc) — crop 3:2, sinh 2 cỡ 1200x800 + 480x320 (WebP).
   - Nổi bật (checkbox) — ưu tiên vào khối lớn đầu trang chủ.
   - Bản nháp (checkbox) — lưu nhưng KHÔNG xuất bản lên website.
   - Nội dung: TinyMCE tự host. Toolbar: tiêu đề H2/H3/H4, đậm/nghiêng/gạch chân, trích dẫn,
     danh sách, liên kết, bảng, đường kẻ, **nút "Chèn ảnh" nhanh** (mở thẳng file picker, chọn
     nhiều ảnh). **CÓ chèn ảnh trong nội dung**: ảnh bọc `<figure>` + `<figcaption>`, alt = caption,
     caption trống thì alt = tiêu đề bài (đồng bộ sống khi đổi tiêu đề).
2. Server tự suy (không có ô nhập): `date` (lúc Lưu lần đầu, giữ nguyên khi sửa), `updated_at`,
   `reading_minutes` (build tự tính), đường dẫn ảnh bìa (tất định theo slug).
3. Danh sách bài trong Admin: index nhẹ `data/posts.json` lấy qua `boot()` (đọc GitHub Contents
   API), cache localStorage stale-while-revalidate.
4. Ảnh: nén/resize ở client bằng canvas → WebP (q 0.82; trình duyệt không xuất được WebP thì
   JPEG). Ảnh nội dung rộng tối đa 1200px. Ảnh **RIÊNG 1-1 cho từng bài**, nằm trong
   `static/images/posts/<slug>/` → xoá bài xoá luôn cả thư mục ảnh (an toàn).
   Đường dẫn ảnh lưu trong nội dung là TUYỆT ĐỐI theo domain (`/images/posts/<slug>/content-N.webp`),
   không phụ thuộc độ sâu trang.

## III. Sửa bài viết / trang / danh mục

- Slug BẤT BIẾN sau lần Lưu đầu — chặn ở server (throw) + disable ô ở client. Tải ảnh bìa hoặc
  chèn ảnh nội dung cũng khoá slug ngay (ảnh đặt tên theo slug).
- Slug phải DUY NHẤT trên toàn site (bài viết, danh mục, trang tĩnh cùng nằm ở `/<slug>/`) và
  không trùng đường dẫn dành riêng: `images assets vendor admin search page feed sitemap 404`.
- Ảnh trong editor hiển thị bằng URL tuyệt đối `raw.githubusercontent.com/<owner>/<repo>/<branch>/static/...`,
  đổi ngược về `/images/...` ngay trước khi lưu.
- Form dùng chung DOM giữa tạo mới / sửa → mở form tạo mới phải tự bật lại ô slug.

## IV. Xoá

- Bài viết: xoá `data/posts/<slug>.json` + thư mục ảnh `static/images/posts/<slug>/` + gỡ khỏi
  `data/posts.json` (ghi SAU CÙNG).
- Trang tĩnh: gỡ khỏi `data/pages.json` + thư mục ảnh `static/images/pages/<slug>/`.
- Danh mục: CHẶN nếu còn bài viết thuộc danh mục đó (kể cả bản nháp).
- Luôn có popup xác nhận Huỷ/Xoá trước khi gọi server.

## V. Form công khai loại 1

Không áp dụng cho dự án này (site không có form liên hệ — liên hệ hiển thị tĩnh ở footer/trang
Liên hệ qua email/điện thoại). `doPost` trả 404.

## VI. Form công khai loại 2

Không áp dụng cho dự án này.

## VI-B. Danh mục, Trang tĩnh, Cài đặt website

- **Danh mục**: tên, slug (`/<slug>/`, bất biến), mô tả (meta + đầu trang danh mục), thứ tự
  (số nhỏ hiện trước trên menu + trang chủ). Trang danh mục `/<slug>/` hiện toàn bộ bài
  của danh mục (không phân trang, giống TrithucWorld).
- **Trang tĩnh** (Giới thiệu, Liên hệ, Chính sách...): tiêu đề, slug, mô tả, nội dung TinyMCE,
  thứ tự, "Hiện ở menu trên" (checkbox, mặc định tắt — luôn hiện ở footer).
- **Cài đặt website** (admin trở lên): tên website, khẩu hiệu, mô tả SEO trang chủ, tên miền
  (`domain_url`, có `/` cuối), ngôn ngữ, tác giả mặc định, đoạn giới thiệu ở footer, email/điện
  thoại/địa chỉ liên hệ, link Facebook/YouTube/TikTok/Instagram, Google Analytics ID (`G-...`),
  mã chèn `<head>` tuỳ ý (vd AdSense), nội dung `ads.txt` (lưu trong `website.json`, build ghi
  ra `html/ads.txt` khi có nội dung). Ảnh: logo (cao 96px), favicon
  (vuông 192px PNG), ảnh chia sẻ mặc định (1200x630 JPEG).

## VII. UX chung Admin

- 2 modal riêng: XÁC NHẬN (Huỷ/Xoá) trước khi xử lý; THÔNG BÁO kết quả (1 nút Đóng) sau xử lý.
  Không `alert()`/`confirm()` native, không toast tự ẩn.
- Mọi nút async: disable + spinner (`withLoading`), tự phục hồi kể cả lỗi.
- Sau Lưu/Xoá thành công: quay về danh sách của chính mục đó, danh sách tự cập nhật, boot cache
  đồng bộ ngay (`syncBootCache_`), nhắc "Website sẽ cập nhật sau 1-2 phút".
- Chuyển tab chỉ ẩn/hiện, không tải lại. Mở Admin: 1 lượt `boot()`; lần sau hiện ngay từ cache
  rồi revalidate ngầm.
- Mọi key localStorage (trừ token) mang hậu tố `CLIENT_BUILD` — server tự băm từ nội dung
  `app.html` + `js.html` (`clientBuild_()`), không gõ tay. Revalidate thấy `appHtml` đổi thì tự
  vẽ lại (trừ khi đang mở form soạn).
- Không lộ tên hạ tầng (Sheet/Drive/Apps Script) trong bất kỳ file nào gửi xuống trình duyệt,
  kể cả comment và thông báo lỗi.

## VIII. Kiến trúc lưu trữ

- Google Sheet "DanDan Stories CMS Data" (tự tạo lần đầu): sheet `Users` — cột `email`, `role`
  (`admin` | `editor` | `root`).
- GitHub (Contents API) — đường dẫn cố định, đổi thì sửa luôn `scripts/build.py` +
  `.github/workflows/build.yml`:
  | Đường dẫn | Nội dung | Commit chốt? |
  |---|---|---|
  | `data/website.json` | cài đặt website | ✔ (Lưu cài đặt / tải ảnh site) |
  | `data/categories.json` | danh sách danh mục | ✔ |
  | `data/posts.json` | index nhẹ mọi bài (không content) | ✔ (Lưu/Xoá bài) |
  | `data/posts/<slug>.json` | nội dung đầy đủ 1 bài | |
  | `data/pages.json` | toàn bộ trang tĩnh kèm nội dung | ✔ |
  | `static/images/posts/<slug>/cover-lg.webp`, `cover-sm.webp`, `content-N.webp` | ảnh bài | |
  | `static/images/pages/<slug>/content-N.webp` | ảnh trang tĩnh | |
  | `static/images/site/logo.*`, `favicon.png`, `og-default.jpg` | ảnh site | |
- File chốt LUÔN ghi SAU CÙNG trong 1 thao tác. GitHub Actions chỉ build khi file chốt đổi (hoặc code/giao
  diện đổi), KHÔNG chạy theo `static/images/**`.
- `html/` là output 100% của build — GitHub Actions xoá sạch, build lại, commit vào repo
  ("CI: build html from data"); Cloudflare Workers Builds thấy `html/` đổi thì deploy. Không sửa tay.
- Độ trễ Lưu → thấy trên site: ~1-2 phút (GitHub Actions build + Cloudflare deploy).

## IX. Bug đã gặp ở dự án này

(Chưa có — ghi lại ở đây khi gặp bug thật.)

Kiểm tra tự động trước mỗi lần deploy GAS: `node scripts/check_gas_client.mjs` (client, chạy
tự động qua hook khi sửa `gas/*.html`) và `node scripts/test_gas_e2e.mjs` (luồng server + build).

## X. Script Properties (tên cố định)

- `GITHUB_TOKEN` — fine-grained PAT, Contents: Read and write, đúng 1 repo.
- `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_BRANCH` — bắt buộc.
- `SPREADSHEET_ID` — KHÔNG cần điền, code tự tạo lần đầu.
- `SITE_URL` — KHÔNG cần điền: tên miền mặc định ghi trong code (`DEFAULT_SITE_URL` =
  `https://rapidfanpost.com/` ở `gas/Code.js`). Chỉ điền khi đổi sang tên miền khác mà chưa sửa code.
  Trình soạn thảo tải từ `<tên miền>vendor/tinymce/` (tự host).

## XI. API cho công cụ AI (khoá kết nối) — theo mẫu dolphinhouse.vn

Mục đích: chủ website ra lệnh cho công cụ AI chạy trên máy họ (Claude, ChatGPT...) để nó tự đăng
bài viết / trang tĩnh / danh mục / ảnh, không cần mở Admin.

1. **Khoá kết nối** `dds_` + 64 hex, lưu Script Property `apikey_<khoá>` = JSON
   `{label, email, created_at, last_used_at, calls}`. Tối đa **10** khoá. Chỉ admin/root tạo/xem/thu
   hồi (`createApiKey`, `listApiKeys`, `revokeApiKey`, tab **Kết nối AI**). Thu hồi = xoá property,
   khoá chết ngay. Khoá KHÔNG lưu localStorage.
2. **Khoá luôn quyền `editor`** (chỉ nội dung): `whoAmI_()` nhận diện khoá theo tiền tố trước khi tra
   token phiên → mọi thao tác ghi đi qua đúng hàm Admin đang dùng (`savePost`, `savePage`,
   `saveCategory`, `uploadPostCover`, `uploadContentImage`, `delete*`). Khoá KHÔNG mở được giao diện
   quản trị (`boot()` từ chối), không đụng được Cài đặt website / Người dùng / khoá khác.
3. **Cổng vào**: cùng URL `/exec`. `doGet` có `?action=` → API (chỉ lệnh đọc `API_READ_ACTIONS`);
   `doPost` (JSON body) → API. Phản hồi luôn `{ok, action, data|error}` (HTTP luôn 200), lỗi viết
   tiếng Anh (người đọc là AI). Code ở file riêng `gas/Api.js`.
4. **Lệnh**: `ping`; `post.list|get|create|update|delete`; `category.list|create|update|delete`;
   `page.list|get|create|update|delete`; `image.upload`.
   - `create` từ chối slug đã có, `update` từ chối slug chưa có (không upsert ngầm). `update` trộn
     với bản cũ: field không gửi giữ nguyên.
   - Bài mới bắt buộc `title`, `category` (đã tồn tại), `cover`.
   - HTML từ API được lọc (`apiCleanHtml_`: bỏ script/style/iframe/form, `on*=`, `javascript:`,
     `<h1>` → `<h2>`). Ảnh `<img src="http...">`/`data:` trong nội dung tự tải về kho ảnh của
     bài/trang (tối đa 15 ảnh mới/lệnh).
5. **Ảnh**: URL http(s) (server tự tải), `{data: base64, filename}`, hoặc đường dẫn đã có. Chỉ
   JPEG/PNG/WebP, ≤ 5MB. Server KHÔNG resize được → ảnh bìa qua API dùng chung 1 file cho cỡ lớn/nhỏ;
   tài liệu yêu cầu AI gửi ảnh ngang 3:2.
6. **Khoá ghi advisory** (`api_write_lock` trong CacheService, chờ tối đa 45s, TTL 180s) — 2 lệnh ghi
   song song sẽ đọc-ghi đè index của nhau.
7. **Trang hướng dẫn** `/admin/api/` = `templates/admin-api.html`, build.py sinh ra (địa chỉ API ghi
   thẳng vào HTML để AI tải trang là đọc được). Đây là TÀI LIỆU DUY NHẤT cho AI — sửa action/field
   trong `gas/Api.js` thì sửa luôn trang này. Trang không chứa khoá; quy định nội dung phải viết
   **tiếng Anh**. "Chép lệnh cho AI" trong Admin (`buildAiPrompt_` ở `js.html`) chỉ gồm: đường dẫn
   trang hướng dẫn + địa chỉ + khoá + nhắc tiếng Anh (giống mục 11 của trang hướng dẫn).
8. Địa chỉ `/exec` khai **đúng 1 chỗ**: `static/admin/config.js` (`window.DANDAN_CMS_URL`), dùng cho
   cả `/admin/` lẫn trang hướng dẫn.
9. **Kiểm thử**: `node scripts/test_gas_e2e.mjs` có nhóm "API cho AI".

## XII. SEO trên site

Mọi trang (trừ 404 - `noindex, follow`) có: `<title>`, meta description, `<link rel=canonical>`,
robots `index, follow, max-image-preview:large`, Open Graph (`og:type/title/description/url/locale/
image` + kích thước thật), Twitter/X card, link RSS, `apple-touch-icon`. Khối thêm sinh bởi
`Site.seo_tags()` (placeholder `{{SEO_TAGS}}`). JSON-LD: trang chủ `Organization` + `WebSite`; danh
mục `CollectionPage` (ItemList) + `BreadcrumbList`; bài viết `BlogPosting` + `BreadcrumbList` +
`article:published_time/modified_time/section/author`; trang tĩnh `WebPage`/`AboutPage`/
`ContactPage` + `BreadcrumbList`. Ảnh chia sẻ: ảnh bìa bài; trang khác dùng "Ảnh chia sẻ mặc định"
trong Cài đặt, chưa có thì ảnh bìa bài mới nhất.

