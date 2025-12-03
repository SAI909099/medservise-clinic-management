const token = localStorage.getItem("token");
const patientListDiv = document.getElementById("patient-list");
const searchInput = document.getElementById("search-input");
const yearFilter = document.getElementById("year-filter");
const refreshBtn = document.getElementById("refresh-btn");

// 🔥 FIXED — dynamic API base
const API_BASE = window.location.origin + "/api/v1";

let allPatients = [];

function fetchPatients() {
  patientListDiv.innerHTML = "<p>Yuklanmoqda...</p>";

  fetch(`${API_BASE}/patients/archive/`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  })
    .then((res) => {
      if (!res.ok) {
        throw new Error(`API response: ${res.status}`);
      }
      return res.json();
    })
    .then((patients) => {
      allPatients = patients;
      populateYearFilter(patients);
      displayPatients(patients);
    })
    .catch((err) => {
      console.error("❌ Error loading patients:", err);
      patientListDiv.innerHTML =
        "<p class='text-danger'>❌ Ma'lumotlar yuklanmadi. Qaytadan urinib ko'ring.</p>";
    });
}

function populateYearFilter(patients) {
  yearFilter.innerHTML = `<option value="">Barchasi</option>`;
  const years = [...new Set(patients.map((p) => new Date(p.created_at).getFullYear()))];
  years.sort((a, b) => b - a);
  years.forEach((y) => {
    const opt = document.createElement("option");
    opt.value = y;
    opt.textContent = y;
    yearFilter.appendChild(opt);
  });
}

function displayPatients(patients) {
  if (!patients.length) {
    patientListDiv.innerHTML = "<p>Hech qanday bemor topilmadi.</p>";
    return;
  }

  patientListDiv.innerHTML = "";
  patients.forEach((p) => {
    const div = document.createElement("div");
    div.className = "border p-3 mb-3 rounded";

    const doctorName = p.doctor
      ? `${p.doctor.first_name} ${p.doctor.last_name}`
      : "Noma'lum";
    const treatments = p.treatment_history?.length
      ? p.treatment_history
          .map(
            (t) =>
              `🛏 ${t.room} (${t.assigned_at} - ${t.discharged_at ?? "davom etmoqda"})`
          )
          .join("<br>")
      : "<i>Yo'q</i>";
    const labServices = p.lab_services?.length
      ? p.lab_services
          .map(
            (l) =>
              `🔬 ${l.service} (${l.price} so'm, ${l.status}, ${l.registered_at})`
          )
          .join("<br>")
      : "<i>Yo'q</i>";
    const totalPaid = p.total_payments ?? 0;

    div.innerHTML = `
      <h5>${p.first_name ?? "?"} ${p.last_name ?? "?"}</h5>
      <p><strong>Telefon:</strong> ${p.phone ?? "N/A"}</p>
      <p><strong>Ro'yxatdan o'tgan:</strong> ${new Date(p.created_at).toLocaleString("uz-UZ")}</p>
      <p><strong>Shifokor:</strong> ${doctorName}</p>
      <p><strong>Davolanish:</strong><br>${treatments}</p>
      <p><strong>Laboratoriya xizmatlari:</strong><br>${labServices}</p>
      <p><strong>To'langan summa:</strong> ${totalPaid} so'm</p>
      <a class="btn btn-sm btn-outline-info" href="/doctor/patient-detail/?patient_id=${p.id}">🔎 Batafsil</a>
    `;

    patientListDiv.appendChild(div);
  });
}

function applyFilters() {
  const searchTerm = searchInput.value.toLowerCase();
  const selectedYear = yearFilter.value;

  const filtered = allPatients.filter((p) => {
    const matchesSearch =
      p.first_name?.toLowerCase().includes(searchTerm) ||
      p.last_name?.toLowerCase().includes(searchTerm) ||
      p.phone?.includes(searchTerm);

    const matchesYear = selectedYear
      ? new Date(p.created_at).getFullYear().toString() === selectedYear
      : true;

    return matchesSearch && matchesYear;
  });

  displayPatients(filtered);
}

// Event listeners
searchInput.addEventListener("input", applyFilters);
yearFilter.addEventListener("change", applyFilters);
refreshBtn.addEventListener("click", fetchPatients);

// Fetch on load
fetchPatients();
