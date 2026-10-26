/* 性格分析落地页 · 交互
   原则：JS 只做增强。数据在 window.XINGGE_DATA（由 tools/build_data.py 生成）。
   没有 JS 时，页面仍然可读：卡片内容已在 HTML 里，只是全部展开。 */
(function () {
  "use strict";

  var DATA = window.XINGGE_DATA;
  if (!DATA) {
    // 数据缺失时保留静态内容，不报错、不白屏。
    return;
  }

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  };

  /* ---------- 品牌与题数 ---------- */
  $$("[data-brand]").forEach(function (el) { el.textContent = DATA.brand; });
  $$("[data-total-questions]").forEach(function (el) {
    el.textContent = DATA.totalQuestions;
  });
  $$("[data-per-dim]").forEach(function (el) {
    el.textContent = DATA.dimensionCounts.EI || 7;
  });
  var src = $("[data-profile-source]");
  if (src) { src.textContent = DATA.profileSource; }

  /* ---------- Hero 配色墙 ---------- */
  var wall = $("#wall");
  if (wall) {
    DATA.personalities.forEach(function (p) {
      var li = document.createElement("li");
      li.style.background = p.color;
      li.textContent = p.code;
      li.title = p.code + " " + p.role + " · " + p.word;
      wall.appendChild(li);
    });
  }

  /* ---------- 四个维度卡 ---------- */
  var dimsBox = $("#dims");
  if (dimsBox) {
    DATA.dimIntro.forEach(function (d) {
      var count = DATA.dimensionCounts[d.code] || 0;
      var el = document.createElement("article");
      el.className = "dim";
      el.innerHTML =
        '<span class="dim__code">' + d.code + "</span>" +
        '<h3 class="dim__title">' + d.title + "</h3>" +
        '<span class="dim__pair">' + d.pair + "</span>" +
        '<p class="dim__line">' + d.line + "</p>" +
        '<p class="dim__count">本维度 ' + count + " 题</p>";
      dimsBox.appendChild(el);
    });
  }

  /* ---------- 图鉴筛选 ---------- */
  var chips = $$(".chips .chip[data-filter]");
  var cards = $$("#gallery .card");
  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var want = chip.getAttribute("data-filter");
      chips.forEach(function (c) {
        var on = c === chip;
        c.classList.toggle("is-on", on);
        c.setAttribute("aria-pressed", on ? "true" : "false");
      });
      cards.forEach(function (card) {
        var show = want === "all" || card.getAttribute("data-group") === want;
        card.classList.toggle("is-hidden", !show);
      });
    });
  });

  /* ---------- 报告样例：切换类型 ---------- */
  var typeChips = $$(".chips--types .chip[data-type]");
  var figures = $$(".pf-figure");
  var reportSec = $("#report");

  function showType(code) {
    typeChips.forEach(function (c) {
      var on = c.getAttribute("data-type") === code;
      c.classList.toggle("is-on", on);
      c.setAttribute("aria-pressed", on ? "true" : "false");
    });
    figures.forEach(function (f) {
      f.classList.toggle("is-active", f.getAttribute("data-type") === code);
    });
  }

  typeChips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      showType(chip.getAttribute("data-type"));
    });
  });

  // 卡片里的「看雷达图」：切类型 + 滚过去
  $$("[data-pick]").forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      showType(link.getAttribute("data-pick"));
      if (reportSec) {
        reportSec.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });

  /* ---------- 顶栏滚动态 ---------- */
  var topbar = $("#topbar");
  if (topbar) {
    var onScroll = function () {
      topbar.classList.toggle("is-stuck", window.scrollY > 8);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---------- 入场动效 ---------- */
  if (!window.matchMedia || !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var targets = $$(".section__title, .section__lead, .dim, .card, .pf-figure, .steps li, .faq__item, .qa-item, .cta h2, .qr-card");
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        });
      }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
      targets.forEach(function (el, i) {
        el.classList.add("reveal");
        el.style.transitionDelay = (i % 6) * 45 + "ms";
        io.observe(el);
      });
    }
  }
})();
