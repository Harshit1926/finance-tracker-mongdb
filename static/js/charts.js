/* ==========================================================================
   Chart.js setup — dark theme defaults + two chart builders used across
   the User and Analyst dashboards.

   Chart.js config is guarded: auth pages (login/signup/OTP) don't need
   charts, and if the CDN is blocked or slow this must not stop the rest
   of the file (password toggle, phone validation) from running.
   ========================================================================== */

if (typeof Chart !== "undefined") {
  Chart.defaults.color = "#9a9daa";
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.borderColor = "#2a2e3a";
}

function buildExpenseDoughnut(canvasId, labels, values, colors) {
  if (typeof Chart === "undefined") return;
  const el = document.getElementById(canvasId);
  if (!el) return;

  new Chart(el, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: "#191c24",
        borderWidth: 3,
        hoverOffset: 6,
      }],
    },
    options: {
      cutout: "68%",
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#20242e",
          borderColor: "#2a2e3a",
          borderWidth: 1,
          padding: 10,
          titleFont: { family: "'Fraunces', serif", size: 13 },
          bodyFont: { family: "'Inter', sans-serif", size: 12 },
          callbacks: {
            label: (ctx) => ` ₹${ctx.parsed.toLocaleString("en-IN")}`,
          },
        },
      },
    },
  });
}

function buildTrendLine(canvasId, labels, income, expense) {
  if (typeof Chart === "undefined") return;
  const el = document.getElementById(canvasId);
  if (!el) return;

  const ctx2d = el.getContext("2d");
  const goldGradient = ctx2d.createLinearGradient(0, 0, 0, 240);
  goldGradient.addColorStop(0, "rgba(58, 140, 104, 0.25)");
  goldGradient.addColorStop(1, "rgba(58, 140, 104, 0)");

  const roseGradient = ctx2d.createLinearGradient(0, 0, 0, 240);
  roseGradient.addColorStop(0, "rgba(176, 73, 90, 0.22)");
  roseGradient.addColorStop(1, "rgba(176, 73, 90, 0)");

  new Chart(el, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Income",
          data: income,
          borderColor: "#3a8c68",
          backgroundColor: goldGradient,
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: "#3a8c68",
          borderWidth: 2,
        },
        {
          label: "Expense",
          data: expense,
          borderColor: "#b0495a",
          backgroundColor: roseGradient,
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: "#b0495a",
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "top",
          align: "end",
          labels: { boxWidth: 8, boxHeight: 8, usePointStyle: true, padding: 16 },
        },
        tooltip: {
          backgroundColor: "#20242e",
          borderColor: "#2a2e3a",
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ₹${ctx.parsed.y.toLocaleString("en-IN")}`,
          },
        },
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          grid: { color: "#22252f" },
          ticks: {
            callback: (v) => "₹" + v.toLocaleString("en-IN"),
          },
        },
      },
    },
  });
}

/* Auto-dismiss flash messages after a few seconds */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });

  // "Other" category custom-label field toggle on the add-transaction form
  const categorySelect = document.getElementById("category-select");
  const customField = document.getElementById("custom-category-field");
  if (categorySelect && customField) {
    const toggle = () => {
      customField.style.display = categorySelect.value === "Other" ? "flex" : "none";
    };
    categorySelect.addEventListener("change", toggle);
    toggle();
  }

  // Password show/hide toggle — applies to every .password-toggle button
  document.querySelectorAll(".password-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      // Look inside the wrapper rather than relying on exact sibling order
      const wrapper = btn.closest(".password-field");
      const input = wrapper
        ? wrapper.querySelector("input")
        : btn.previousElementSibling;
      if (!input) return;

      const isPassword = input.type === "password";
      input.type = isPassword ? "text" : "password";
      btn.classList.toggle("showing", isPassword);
      btn.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
    });
  });

  // Phone fields: strip anything non-numeric and cap at 10 digits, live as the user types
  document.querySelectorAll('input[type="tel"]').forEach((input) => {
    input.addEventListener("input", () => {
      input.value = input.value.replace(/\D/g, "").slice(0, 10);
    });
  });
});