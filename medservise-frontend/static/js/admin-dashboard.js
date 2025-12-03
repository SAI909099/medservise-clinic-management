// 🔥 FIXED — dynamically use your current domain/IP
const API_BASE = window.location.origin + "/api/v1";

let doctorChart = null;
let serviceChart = null;
let monthlyChart = null;

function formatNumber(num) {
  return parseInt(num).toLocaleString("uz-UZ");
}

function loadStatistics(startDate = '', endDate = '') {
  loadIncomeData(startDate, endDate);
  loadAdminStats(startDate, endDate);
}

function loadIncomeData(startDate = '', endDate = '') {
  const url = new URL(`${API_BASE}/incomes/`);
  if (startDate && endDate) {
    url.searchParams.append('start_date', startDate);
    url.searchParams.append('end_date', endDate);
  }

  fetch(url, authHeader())
    .then(res => res.json())
    .then(data => {
      document.getElementById('total-income').innerText = formatNumber(data.total_income || 0) + " so'm";
      document.getElementById('total-outcome').innerText = formatNumber(data.total_outcome || 0) + " so'm";
      document.getElementById('balance').innerText = formatNumber(data.balance || 0) + " so'm";
    })
    .catch(err => console.error("❌ Daromad/xarajat/balans statistikasi yuklanmadi:", err));
}

function loadAdminStats(startDate = '', endDate = '') {
  const url = new URL(`${API_BASE}/admin-statistics/`);
  if (startDate && endDate) {
    url.searchParams.append('start_date', startDate);
    url.searchParams.append('end_date', endDate);
  }

  fetch(url, authHeader())
    .then(res => res.json())
    .then(data => {
      document.getElementById('treatment-room-profit').innerText = formatNumber(data.treatment_room_profit || 0) + " so'm";
      document.getElementById('doctor-profit').innerText = formatNumber(data.doctor_profit || 0) + " so'm";
      document.getElementById('service-profit').innerText = formatNumber(data.service_profit || 0) + " so'm";
    })
    .catch(err => console.error("❌ Admin statistikasi yuklanmadi:", err));
}

function loadRecentTransactions(startDate = '', endDate = '') {
  const url = new URL(`${API_BASE}/recent-transactions/`);
  if (startDate && endDate) {
    url.searchParams.append('start_date', startDate);
    url.searchParams.append('end_date', endDate);
  }

  fetch(url, authHeader())
    .then(res => res.json())
    .then(data => {
      const table = document.getElementById('transaction-table');
      if (!table) return;

      table.innerHTML = '';
      if (data.length === 0) {
        table.innerHTML = `<tr><td colspan="7" class="text-center">Hech qanday to‘lovlar topilmadi.</td></tr>`;
        return;
      }

      data.slice(0, 50).forEach(tx => {
        const services = tx.services?.join(', ') || '—';
        const transactionTypeUz = {
          consultation: "Konsultatsiya",
          treatment: "Davolash",
          service: "Xizmat",
          room: "Xona",
          other: "Boshqa"
        }[tx.transaction_type] || tx.transaction_type;

        const paymentMethodUz = {
          cash: "Naqd",
          card: "Karta",
          insurance: "Sug'urta",
          transfer: "O'tkazma"
        }[tx.payment_method] || tx.payment_method;

        const row = `
          <tr>
            <td>${tx.id}</td>
            <td>${tx.patient_name || '—'}</td>
            <td>${transactionTypeUz}</td>
            <td>${paymentMethodUz}</td>
            <td>${services}</td>
            <td>${formatNumber(tx.amount)} so'm</td>
            <td>${new Date(tx.created_at).toLocaleString("uz-UZ")}</td>
          </tr>`;
        table.innerHTML += row;
      });
    })
    .catch(err => console.error("❌ Tranzaksiyalarni yuklab bo‘lmadi:", err));
}

function generateColors(count) {
  const baseColors = ['#4e79a7', '#f28e2c', '#e15759', '#76b7b2', '#59a14f', '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ab'];
  return Array.from({ length: count }, (_, i) => baseColors[i % baseColors.length]);
}

function drawBarChart(canvasId, title, items, chartRefName) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (window[chartRefName]) window[chartRefName].destroy();

  window[chartRefName] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: items.map(i => i.name),
      datasets: [{
        label: title,
        data: items.map(i => i.profit),
        backgroundColor: generateColors(items.length)
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        title: { display: true, text: title }
      },
      scales: {
        y: {
          ticks: {
            callback: value => value.toLocaleString("uz-UZ")
          }
        }
      }
    }
  });
}

function drawMonthlyComparisonChart(monthlyData) {
  const canvas = document.getElementById("monthlyComparisonChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (monthlyChart) monthlyChart.destroy();

  const current = monthlyData.this_month || {};
  const last = monthlyData.last_month || {};

  monthlyChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Shifokor", "Xizmat"],
      datasets: [
        { label: "Joriy oy", backgroundColor: "#4e79a7", data: [current.doctor_profit || 0, current.service_profit || 0] },
        { label: "O‘tgan oy", backgroundColor: "#f28e2c", data: [last.doctor_profit || 0, last.service_profit || 0] }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        title: { display: true, text: "Joriy oy vs O‘tgan oy" }
      },
      scales: {
        y: {
          ticks: {
            callback: value => value.toLocaleString("uz-UZ")
          }
        }
      }
    }
  });
}

function loadCharts(startDate = '', endDate = '') {
  const url = new URL(`${API_BASE}/admin-chart-data/`);
  if (startDate && endDate) {
    url.searchParams.append('start_date', startDate);
    url.searchParams.append('end_date', endDate);
  }

  fetch(url, authHeader())
    .then(res => res.json())
    .then(data => {
      drawBarChart("doctorProfitChart", "Shifokor daromadi", data.doctors || [], 'doctorChart');
      drawBarChart("serviceProfitChart", "Xizmat daromadi", data.services || [], 'serviceChart');
      drawMonthlyComparisonChart(data.monthly_comparison || {});
    })
    .catch(err => console.error("❌ Diagrammalarni yuklab bo‘lmadi:", err));
}

function authHeader() {
  const token = localStorage.getItem("token");
  return {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  };
}

// Filter listener
const filterForm = document.getElementById('filter-form');
if (filterForm) {
  filterForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    loadStatistics(start, end);
    loadRecentTransactions(start, end);
    loadCharts(start, end);
  });
}

// Check superuser
window.addEventListener('DOMContentLoaded', async () => {
  const token = localStorage.getItem("token");

  if (!token) {
    alert("❌ Tizimga kirilmagan.");
    localStorage.clear();
    window.location.href = "/";
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/user-profile/`, authHeader());
    const user = await res.json();

    if (!user.is_superuser) {
      alert("❌ Sizda admin panelga kirish huquqi yo‘q.");
      localStorage.clear();
      window.location.href = "/";
      return;
    }

    loadStatistics();
    loadRecentTransactions();
    loadCharts();
  } catch (err) {
    console.error("❌ Profilni aniqlashda xatolik:", err);
    alert("❌ Profilni aniqlashda xatolik.");
    localStorage.clear();
    window.location.href = "/";
  }
});
