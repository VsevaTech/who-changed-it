/* Who Changed It? — minimal client. No dependencies, no storage, no analytics. */
(function () {
  "use strict";

  const form = document.getElementById("compare-form");
  const results = document.getElementById("results");
  const compareBtn = document.getElementById("compare-btn");
  let mode = "paste";

  // ---- mode switch -------------------------------------------------------------------
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      mode = tab.dataset.mode;
      document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
      document.getElementById("mode-paste").classList.toggle("hidden", mode !== "paste");
      document.getElementById("mode-upload").classList.toggle("hidden", mode !== "upload");
    });
  });

  // ---- file name display -------------------------------------------------------------
  document.querySelectorAll('input[type="file"]').forEach((input) => {
    input.addEventListener("change", () => {
      const label = document.querySelector(`.file-name[data-for="${input.id}"]`);
      const file = input.files && input.files[0];
      label.textContent = file ? `${file.name} (${Math.ceil(file.size / 1024)} KB)` : "Upload JSON";
      input.closest(".drop").classList.toggle("has-file", !!file);
    });
  });

  // ---- submit ------------------------------------------------------------------------
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData();
    data.append("identity_keys", form.elements.identity_keys.value || "");
    if (mode === "paste") {
      data.append("before_text", form.elements.before_text.value);
      data.append("after_text", form.elements.after_text.value);
    } else {
      const b = form.elements.before_file.files[0];
      const a = form.elements.after_file.files[0];
      if (b) data.append("before_file", b);
      if (a) data.append("after_file", a);
    }
    compareBtn.disabled = true;
    compareBtn.textContent = "Comparing…";
    try {
      const response = await fetch("/compare", { method: "POST", body: data });
      results.innerHTML = await response.text();
      wireResults();
      results.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      results.innerHTML =
        '<div class="panel error" role="alert"><h2>Request failed</h2><p>The server could not be reached.</p></div>';
    } finally {
      compareBtn.disabled = false;
      compareBtn.textContent = "Compare configurations";
    }
  });

  // ---- demo / clear ------------------------------------------------------------------
  document.getElementById("load-demo").addEventListener("click", async () => {
    const [b, a] = await Promise.all([fetch("/demo/before"), fetch("/demo/after")]);
    form.elements.before_text.value = await b.text();
    form.elements.after_text.value = await a.text();
    document.querySelector('.tab[data-mode="paste"]').click();
  });
  document.getElementById("clear").addEventListener("click", () => {
    form.reset();
    document.querySelectorAll(".file-name").forEach((l) => (l.textContent = "Upload JSON"));
    document.querySelectorAll(".drop").forEach((d) => d.classList.remove("has-file"));
    results.innerHTML = "";
  });

  // ---- filters + search (client-side, on rendered rows) --------------------------------
  function wireResults() {
    const panel = document.getElementById("results-panel");
    if (!panel) return;
    const filterButtons = panel.querySelectorAll(".filter");
    const search = panel.querySelector("#search");
    const empty = panel.querySelector("#empty-filter");
    let activeFilter = "all";

    function apply() {
      const q = (search && search.value.trim().toLowerCase()) || "";
      let visible = 0;
      panel.querySelectorAll(".change").forEach((row) => {
        const okType = activeFilter === "all" || row.dataset.type === activeFilter;
        const okSearch = !q || row.dataset.search.includes(q);
        const show = okType && okSearch;
        row.classList.toggle("hidden", !show);
        if (show) visible++;
      });
      panel.querySelectorAll(".group").forEach((group) => {
        const shown = group.querySelectorAll(".change:not(.hidden)").length;
        group.classList.toggle("hidden", shown === 0);
        const counter = group.querySelector(".group-count");
        if (counter) counter.textContent = String(shown);
      });
      if (empty) empty.classList.toggle("hidden", visible !== 0);
    }

    filterButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        activeFilter = btn.dataset.filter;
        filterButtons.forEach((b) => b.classList.toggle("active", b === btn));
        apply();
      });
    });
    if (search) search.addEventListener("input", apply);
  }
})();
