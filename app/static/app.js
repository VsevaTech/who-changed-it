/* Minimal vanilla JS: submit the form via fetch, swap the result HTML,
   client-side filters/search, and export via the same form data.
   Inputs live only in the form/JS memory — never in hidden fields or storage. */
(function () {
  "use strict";

  const form = document.getElementById("compare-form");
  const result = document.getElementById("result");
  const status = document.getElementById("status");
  const compareBtn = document.getElementById("compare-btn");
  let mode = "paste";

  // ---- tabs -------------------------------------------------------------------
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      mode = tab.dataset.mode;
      document.querySelectorAll(".tab").forEach((t) => {
        const active = t === tab;
        t.classList.toggle("active", active);
        t.setAttribute("aria-selected", String(active));
      });
      document.querySelector(".mode-paste").classList.toggle("hidden", mode !== "paste");
      document.querySelector(".mode-upload").classList.toggle("hidden", mode !== "upload");
    });
  });

  // ---- build form data for the active mode only ---------------------------------
  function buildFormData() {
    const fd = new FormData();
    if (mode === "paste") {
      fd.append("before_text", document.getElementById("before_text").value);
      fd.append("after_text", document.getElementById("after_text").value);
    } else {
      const b = document.getElementById("before_file").files[0];
      const a = document.getElementById("after_file").files[0];
      if (b) fd.append("before_file", b);
      if (a) fd.append("after_file", a);
    }
    return fd;
  }

  // ---- compare ----------------------------------------------------------------
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    compareBtn.disabled = true;
    status.textContent = "Comparing…";
    try {
      const res = await fetch("/compare", { method: "POST", body: buildFormData() });
      result.innerHTML = await res.text();
      status.textContent = "";
      wireResult();
      result.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      status.textContent = "Request failed. Is the server running?";
    } finally {
      compareBtn.disabled = false;
    }
  });

  // ---- export -----------------------------------------------------------------
  async function download(kind) {
    const res = await fetch("/export/" + kind, { method: "POST", body: buildFormData() });
    if (!res.ok) {
      status.textContent = "Export failed: " + (await res.text());
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "change-report." + kind;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // ---- filters + search ---------------------------------------------------------
  function applyFilters() {
    const activeFilter = result.querySelector(".filter.active");
    const type = activeFilter ? activeFilter.dataset.filter : "all";
    const search = result.querySelector("#search");
    const q = search ? search.value.trim().toLowerCase() : "";
    let visible = 0;
    result.querySelectorAll("li.change").forEach((li) => {
      const okType = type === "all" || li.dataset.type === type;
      const okSearch = !q || li.dataset.search.includes(q);
      const show = okType && okSearch;
      li.classList.toggle("hidden", !show);
      if (show) visible++;
    });
    result.querySelectorAll("section.group").forEach((sec) => {
      const any = sec.querySelector("li.change:not(.hidden)");
      sec.classList.toggle("hidden", !any);
    });
    const empty = result.querySelector("#empty-filter");
    if (empty) empty.classList.toggle("hidden", visible !== 0);
  }

  function wireResult() {
    result.querySelectorAll(".filter").forEach((btn) => {
      btn.addEventListener("click", () => {
        result.querySelectorAll(".filter").forEach((b) => b.classList.toggle("active", b === btn));
        applyFilters();
      });
    });
    const search = result.querySelector("#search");
    if (search) search.addEventListener("input", applyFilters);
    result.querySelectorAll("[data-export]").forEach((btn) => {
      btn.addEventListener("click", () => download(btn.dataset.export));
    });
  }

  // ---- example loader -------------------------------------------------------------
  document.getElementById("load-example").addEventListener("click", async () => {
    const [b, a] = await Promise.all([
      fetch("/examples/merchant-before.json").then((r) => r.text()),
      fetch("/examples/merchant-after.json").then((r) => r.text()),
    ]);
    document.querySelector('.tab[data-mode="paste"]').click();
    document.getElementById("before_text").value = b;
    document.getElementById("after_text").value = a;
    status.textContent = "Example loaded — press Compare.";
  });
})();
