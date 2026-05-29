/**
 * year-tabs.js
 * ────────────
 * Перетворює заголовки років (<h2>XXXX рік</h2>) на вкладки-браузер
 * з виділенням активного року підкресленням (underline-indicator).
 *
 * Підключення (перед </body> або з defer):
 *   <script src="year-tabs.js" defer></script>
 *
 * Не потребує змін у шаблоні — знаходить h2 автоматично.
 */

(function () {
  "use strict";

  /* ─── Налаштування ─────────────────────────────────────── */
  const SCROLL_OFFSET   = 72;   // px — відступ при прокрутці до блоку
  const ACCENT_COLOR    = "#3949ab";
  const INACTIVE_COLOR  = "#5c6780";
  const BAR_BG          = "#f5f7ff";
  const BAR_BORDER      = "#dde2f0";
  const UNDERLINE_H     = 3;    // px — товщина підкреслення
  /* ───────────────────────────────────────────────────────── */

  function init() {
    /* Знаходимо всі h2 у вигляді "XXXX рік" */
    const headings = Array.from(
      document.querySelectorAll("h2")
    ).filter((h) => /^\d{4}\s+рік/.test(h.textContent.trim()));

    if (headings.length < 2) return; // менше двох років — нічого робити

    /* Кожному блоку-року (h2 + усе до наступного h2) даємо обгортку */
    const blocks = headings.map((h2, i) => {
      const wrapper = document.createElement("div");
      wrapper.className = "year-block";
      const year = h2.textContent.match(/\d{4}/)[0];
      wrapper.dataset.year = year;

      /* Збираємо вузли: сам h2 + всі сусіди до наступного h2 */
      const nodes = [h2];
      let next = h2.nextElementSibling;
      while (next && next.tagName !== "H2") {
        nodes.push(next);
        next = next.nextElementSibling;
      }

      /* Вставляємо обгортку перед h2 і переміщуємо вузли */
      h2.parentNode.insertBefore(wrapper, h2);
      nodes.forEach((n) => wrapper.appendChild(n));

      return { year, wrapper };
    });

    /* ── Будуємо tabbar ── */
    const bar = document.createElement("div");
    bar.className = "year-tabbar";
    Object.assign(bar.style, {
      position:       "sticky",
      top:            "0",
      zIndex:         "100",
      display:        "flex",
      alignItems:     "stretch",
      gap:            "0",
      background:     BAR_BG,
      borderBottom:   `1px solid ${BAR_BORDER}`,
      overflowX:      "auto",
      scrollbarWidth: "none",   /* Firefox */
      WebkitOverflowScrolling: "touch",
      padding:        "0 8px",
      marginBottom:   "24px",
    });
    /* Прибираємо скролбар WebKit */
    const style = document.createElement("style");
    style.textContent = `
      .year-tabbar::-webkit-scrollbar { display: none; }

      .year-tab {
        position: relative;
        padding: 12px 20px 10px;
        font-family: Arial, sans-serif;
        font-size: 15px;
        font-weight: 600;
        color: ${INACTIVE_COLOR};
        background: none;
        border: none;
        cursor: pointer;
        white-space: nowrap;
        transition: color .2s;
        outline: none;
        flex-shrink: 0;
      }
      .year-tab::after {
        content: "";
        position: absolute;
        bottom: 0; left: 50%; right: 50%;
        height: ${UNDERLINE_H}px;
        background: ${ACCENT_COLOR};
        border-radius: ${UNDERLINE_H}px ${UNDERLINE_H}px 0 0;
        transition: left .25s ease, right .25s ease;
      }
      .year-tab[aria-selected="true"] {
        color: ${ACCENT_COLOR};
      }
      .year-tab[aria-selected="true"]::after {
        left: 8px;
        right: 8px;
      }
      .year-tab:hover { color: ${ACCENT_COLOR}; }

      .year-block-hidden { display: none !important; }
    `;
    document.head.appendChild(style);

    /* Кнопки */
    const tabs = blocks.map(({ year }) => {
      const btn = document.createElement("button");
      btn.className  = "year-tab";
      btn.type       = "button";
      btn.textContent = year;
      btn.dataset.year = year;
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", "false");
      bar.appendChild(btn);
      return btn;
    });

    /* Вставляємо tabbar перед першим блоком */
    blocks[0].wrapper.parentNode.insertBefore(bar, blocks[0].wrapper);

    /* ── Логіка показу ── */
    let activeYear = null;

    function showYear(year) {
      blocks.forEach(({ year: y, wrapper }) => {
        wrapper.classList.toggle("year-block-hidden", y !== year);
      });
      tabs.forEach((t) =>
        t.setAttribute("aria-selected", t.dataset.year === year ? "true" : "false")
      );
      activeYear = year;
      scrollTabIntoView(year);
    }

    function showAll() {
      blocks.forEach(({ wrapper }) => wrapper.classList.remove("year-block-hidden"));
      tabs.forEach((t) => t.setAttribute("aria-selected", "false"));
      activeYear = null;
    }

    /* Клік по вкладці */
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        if (tab.dataset.year === activeYear) {
          /* Повторний клік — показати всі роки */
          showAll();
        } else {
          showYear(tab.dataset.year);
          /* Скрол до блоку */
          const block = blocks.find((b) => b.year === tab.dataset.year);
          if (block) {
            const top =
              block.wrapper.getBoundingClientRect().top +
              window.scrollY - SCROLL_OFFSET;
            window.scrollTo({ top, behavior: "smooth" });
          }
        }
      });
    });

    /* ── IntersectionObserver — підсвічуємо вкладку при скролі (режим "всі") ── */
    const observer = new IntersectionObserver(
      (entries) => {
        if (activeYear !== null) return; /* фільтр активний — не реагуємо */
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const year = entry.target.dataset.year;
          tabs.forEach((t) =>
            t.setAttribute("aria-selected", t.dataset.year === year ? "true" : "false")
          );
          scrollTabIntoView(year);
        });
      },
      { rootMargin: `-${SCROLL_OFFSET}px 0px -60% 0px`, threshold: 0 }
    );
    blocks.forEach(({ wrapper }) => observer.observe(wrapper));

    /* ── Допоміжна: прокручуємо tabbar щоб активна вкладка була видна ── */
    function scrollTabIntoView(year) {
      const tab = tabs.find((t) => t.dataset.year === year);
      if (!tab) return;
      const tabLeft  = tab.offsetLeft;
      const tabRight = tabLeft + tab.offsetWidth;
      const barLeft  = bar.scrollLeft;
      const barRight = barLeft + bar.offsetWidth;
      if (tabLeft < barLeft) {
        bar.scrollTo({ left: tabLeft - 16, behavior: "smooth" });
      } else if (tabRight > barRight) {
        bar.scrollTo({ left: tabRight - bar.offsetWidth + 16, behavior: "smooth" });
      }
    }

    /* ── Початковий стан: показуємо найновіший рік ── */
    showYear(blocks[0].year);
  }

  /* Запуск після завантаження DOM */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
