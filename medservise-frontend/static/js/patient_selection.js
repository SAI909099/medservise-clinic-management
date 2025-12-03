(.venv) root@vmi2942268:/var/www/Medservise# cat medservise-frontend/static/js/patient_selection.js 
document.addEventListener("DOMContentLoaded", async function () {
  const token = localStorage.getItem("token");

  if (!token) {
    alert("Iltimos, tizimga kiring.");
    window.location.href = "/";
    return;
  }

  // Load today's patients by default
  loadPatients("today");

  // Setup search button
  document.getElementById("search-btn").addEventListener("click", function () {
    const name = document.getElementById("name-search").value;
    const phone = document.getElementById("phone-search").value;
    const dateRange = document.getElementById("date-range").value;
    searchPatients(name, phone, dateRange);
  });
});

const BASE_API = "http://89.39.95.150/api/v1/";

async function authFetch(url, options = {}) {
  const token = localStorage.getItem("token");
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${token}`,
    },
  });
}

async function loadPatients(dateRange = "today") {
  try {
    let url = `${BASE_API}patients/`;
    const params = new URLSearchParams();

    if (dateRange !== "all") {
      const startDate = new Date();
      if (dateRange === "3days") startDate.setDate(startDate.getDate() - 3);
      else if (dateRange === "7days") startDate.setDate(startDate.getDate() - 7);

      params.append("start_date", startDate.toISOString().split("T")[0]);
    }

    const response = await authFetch(`${url}?${params.toString()}`);
    if (!response.ok) throw new Error("Bemorlar ro‘yxatini yuklab bo‘lmadi");

    const patients = await response.json();
    renderPatients(patients);
  } catch (error) {
    console.error("❌ Bemorlarni yuklashda xatolik:", error);
    alert(`Xatolik: ${error.message}`);
  }
}

async function searchPatients(name, phone, dateRange) {
  try {
    const params = new URLSearchParams();
    if (name) params.append("name", name);
    if (phone) params.append("phone", phone);

    if (dateRange !== "all") {
      const startDate = new Date();
      if (dateRange === "3days") startDate.setDate(startDate.getDate() - 3);
      else if (dateRange === "7days") startDate.setDate(startDate.getDate() - 7);

      params.append("start_date", startDate.toISOString().split("T")[0]);
    }

    const response = await authFetch(`${BASE_API}patients/?${params.toString()}`);
    if (!response.ok) throw new Error("Qidiruv bajarilmadi");

    const patients = await response.json();
    renderPatients(patients);
  } catch (error) {
    console.error("❌ Qidiruv xatoligi:", error);
    alert(`Xatolik: ${error.message}`);
  }
}

function renderPatients(patients) {
  const tbody = document.getElementById("patients-body");
  tbody.innerHTML = "";

  if (!patients || patients.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center text-muted">Bemorlar topilmadi</td>
      </tr>
    `;
    return;
  }

  patients.forEach((patient) => {
    const row = document.createElement("tr");

    const balance = Number(patient.balance);
    const formattedBalance = isNaN(balance) ? "Nomaʼlum" : `${balance.toLocaleString()} so'm`;
    const lastVisit = patient.last_visit ? new Date(patient.last_visit).toLocaleDateString("uz-UZ") : "—";

    row.innerHTML = `
      <td>${patient.id}</td>
      <td>${patient.first_name} ${patient.last_name}</td>
      <td>${patient.phone}</td>
      <td class="${balance > 0 ? 'text-danger' : 'text-success'}">
        ${formattedBalance}
      </td>
      <td>${lastVisit}</td>
      <td>
        <button class="btn btn-sm btn-outline-primary" onclick="selectPatient(${patient.id})">
          To‘lov
        </button>
      </td>
    `;
    tbody.appendChild(row);
  });
}

function selectPatient(patientId) {
  window.location.href = `/cash-register.html?patient_id=${patientId}`;
}
(.venv) root@vmi2942268:/var/www/Medservise# 
