(() => {
  const root = document.documentElement;
  const theme = document.getElementById("theme");
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  let preference = null;
  try {
    preference = localStorage.getItem("cargo-hub.diagnostic-theme");
  } catch {}
  const apply = (dark) => {
    root.classList.toggle("dark", dark);
    theme.textContent = dark ? "Tema claro" : "Tema escuro";
    theme.setAttribute(
      "aria-label",
      dark ? "Usar tema claro" : "Usar tema escuro",
    );
  };
  apply(preference ? preference === "dark" : media.matches);
  media.addEventListener("change", (event) => {
    if (!preference) apply(event.matches);
  });
  theme.addEventListener("click", () => {
    preference = root.classList.contains("dark") ? "light" : "dark";
    try {
      localStorage.setItem("cargo-hub.diagnostic-theme", preference);
    } catch {}
    apply(preference === "dark");
  });
  const data = () => document.getElementById("report-data").textContent;
  const feedback = (text) => {
    document.getElementById("feedback").textContent = text;
  };
  document.getElementById("copy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(data());
      feedback("Dados copiados.");
    } catch {
      feedback(
        "Não foi possível copiar. Use Baixar JSON para salvar os dados.",
      );
    }
  });
  document.getElementById("download").addEventListener("click", () => {
    const url = URL.createObjectURL(
      new Blob([data()], { type: "application/json;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "dacte-diagnostic.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  document
    .getElementById("print")
    .addEventListener("click", () => window.print());
  document.querySelectorAll("[data-filter]").forEach((button) =>
    button.addEventListener("click", () => {
      const filter = button.dataset.filter;
      document
        .querySelectorAll("[data-filter]")
        .forEach((item) =>
          item.setAttribute("aria-pressed", String(item === button)),
        );
      let visible = 0;
      document.querySelectorAll(".check-row").forEach((item) => {
        item.hidden =
          filter === "attention"
            ? !["error", "warning"].includes(item.dataset.status)
            : filter === "pending"
              ? item.dataset.status !== "pending"
              : false;
        if (!item.hidden) visible++;
      });
      document.querySelectorAll("#checks section").forEach((section) => {
        section.hidden = !section.querySelector(".check-row:not([hidden])");
      });
      document.getElementById("empty").hidden = visible > 0;
    }),
  );
})();
