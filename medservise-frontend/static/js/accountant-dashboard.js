// medservise-frontend/static/js/accountant-dashboard.js

// 🔥 FIXED → dynamic API base (no more IP dependency)
const BASE_API = window.location.origin + "/api/v1/";

const token = localStorage.getItem("token");

/* -------------------- utils -------------------- */
function formatNumber(num) {
  const n = Number(num || 0);
  return n.toLocaleString("uz-UZ") + " so'm";
}
function formatDateTime(dt) {
  try { return new Date(dt).toLocaleString("uz-UZ"); }
  catch { return dt || "—"; }
}
function translateType(type) {
  return {
    consultation: "Konsultatsiya",
    treatment: "Davolash",
    service: "Xizmat",
    room: "Xona",
    other: "Boshqa",
    outcome: "Xarajat",
    income: "Daromad"
  }[type] || type;
}
function translateMethod(method) {
  return {
    cash: "Naqd",
    card: "Karta",
    transfer: "O‘tkazma",
    insurance: "Sug‘urta"
  }[method] || method || "—";
}
function translateCategory(cat) {
  return {
    salary: "Maosh",
    equipment: "Jihozlar",
    rent: "Ijaralar",
    supplies: "Materiallar",
    other: "Boshqa"
  }[cat] || cat || "—";
}

/* -------------------- dashboard -------------------- */
function fetchDashboardData(start = '', end = '') {
  const url = new URL("incomes/", BASE_API);
  if (start && end) {
    url.searchParams.append("start_date", start);
    url.searchParams.append("end_date", end);
  }

  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then(res => {
      if (!res.ok) throw new Error(`Dashboard fetch failed: ${res.status}`);
      return res.json();
    })
    .then(data => {
      renderSummary(data);
      renderServiceIncome(data.service_income);
      renderRoomIncome(data.room_income);

      const transUrl = new URL("recent-transactions/", BASE_API);
      if (start && end) {
        transUrl.searchParams.append("start_date", start);
        transUrl.searchParams.append("end_date", end);
      }
      return fetch(transUrl, { headers: { Authorization: `Bearer ${token}` } });
    })
    .then(res => {
      if (!res.ok) throw new Error(`Transactions fetch failed: ${res.status}`);
      return res.json();
    })
    .then(renderTransactions)
    .catch(err => {
      console.error("❌ Error fetching data:", err);
      const table = document.getElementById("transaction-table");
      if (table) {
        table.innerHTML = `<tr><td colspan="7" class="text-center">Xatolik yuz berdi: ${err.message}</td></tr>`;
      }
    });
}
