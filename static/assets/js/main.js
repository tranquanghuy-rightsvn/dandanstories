/* DanDan Stories - JS site (khong phu thuoc thu vien). Sua tay o static/, build.py copy sang html/. */
(function () {
  "use strict";

  // ---------- menu mobile ----------
  var drawer = document.getElementById("mobile-drawer");
  var toggle = document.querySelector(".menu-toggle");
  function setDrawer(open) {
    if (!drawer || !toggle) return;
    drawer.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.style.overflow = open ? "hidden" : "";
  }
  if (toggle) toggle.addEventListener("click", function () { setDrawer(true); });
  if (drawer) {
    drawer.addEventListener("click", function (e) {
      if (e.target === drawer || e.target.closest(".menu-close")) setDrawer(false);
    });
  }
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") setDrawer(false); });

  // ---------- danh dau menu dang mo ----------
  var here = location.pathname.split("/")[1];
  document.querySelectorAll(".main-nav a, .drawer-nav a").forEach(function (a) {
    var seg = (a.getAttribute("href") || "").split("/")[1];
    if (seg && seg === here) a.classList.add("active");
  });

  // ---------- thanh tien do doc + nut len dau trang ----------
  var progress = document.querySelector(".read-progress");
  var article = document.querySelector(".page-post .prose");
  var toTop = document.querySelector(".to-top");
  function onScroll() {
    var y = window.scrollY || document.documentElement.scrollTop;
    if (toTop) toTop.classList.toggle("show", y > 600);
    if (progress && article) {
      var rect = article.getBoundingClientRect();
      var total = article.offsetHeight - window.innerHeight * 0.6;
      var done = Math.min(1, Math.max(0, -rect.top / Math.max(total, 1)));
      progress.style.width = (done * 100).toFixed(1) + "%";
    }
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  if (toTop) toTop.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });

  // ---------- sao chep lien ket ----------
  document.querySelectorAll(".copy-link").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var url = btn.getAttribute("data-url") || location.href;
      var done = function () {
        var old = btn.textContent;
        btn.textContent = "Đã sao chép ✓";
        setTimeout(function () { btn.textContent = old; }, 1800);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, function () { window.prompt("Sao chép liên kết:", url); });
      else window.prompt("Sao chép liên kết:", url);
    });
  });

  // ---------- tim kiem (chi chay o /tim-kiem/) ----------
  var results = document.getElementById("search-results");
  if (!results) return;
  var input = document.getElementById("search-input");
  var status = document.getElementById("search-status");
  var index = null;

  function norm(s) {
    return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d");
  }
  function escHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function card(p) {
    return '<article class="card">' +
      '<a class="card-media" href="' + escHtml(p.u) + '" tabindex="-1" aria-hidden="true"><img src="' + escHtml(p.i) + '" alt="' + escHtml(p.t) + '" width="480" height="320" loading="lazy"></a>' +
      '<div class="card-body">' +
      (p.c ? '<span class="card-cat">' + escHtml(p.c) + '</span>' : "") +
      '<h3 class="card-title"><a href="' + escHtml(p.u) + '">' + escHtml(p.t) + '</a></h3>' +
      (p.d ? '<p class="card-excerpt">' + escHtml(p.d) + '</p>' : "") +
      '<p class="card-meta"><span>' + escHtml(p.dt) + '</span><span aria-hidden="true">•</span>' + escHtml(p.m) + ' phút đọc</p>' +
      '</div></article>';
  }
  function run(q) {
    var terms = norm(q).split(/\s+/).filter(Boolean);
    if (!terms.length) {
      results.innerHTML = index.slice(0, 9).map(card).join("");
      status.textContent = index.length ? "Gợi ý cho bạn: những câu chuyện mới nhất." : "Chưa có câu chuyện nào.";
      return;
    }
    var hits = index.filter(function (p) {
      var hay = norm(p.t + " " + p.d + " " + p.k + " " + p.c);
      return terms.every(function (t) { return hay.indexOf(t) !== -1; });
    });
    results.innerHTML = hits.map(card).join("");
    status.textContent = hits.length
      ? "Tìm thấy " + hits.length + " câu chuyện cho “" + q + "”."
      : "Không tìm thấy câu chuyện nào cho “" + q + "”. Thử từ khoá khác nhé.";
  }

  var q0 = new URLSearchParams(location.search).get("q") || "";
  input.value = q0;
  status.textContent = "Đang tải...";
  fetch("/search-index.json").then(function (r) { return r.json(); }).then(function (data) {
    index = data || [];
    run(q0);
  }).catch(function () { status.textContent = "Không tải được dữ liệu tìm kiếm."; });

  var timer = null;
  input.addEventListener("input", function () {
    if (!index) return;
    clearTimeout(timer);
    timer = setTimeout(function () {
      run(input.value.trim());
      var url = input.value.trim() ? "?q=" + encodeURIComponent(input.value.trim()) : location.pathname;
      history.replaceState(null, "", url);
    }, 160);
  });
  input.closest("form").addEventListener("submit", function (e) {
    e.preventDefault();
    if (index) run(input.value.trim());
  });
})();
