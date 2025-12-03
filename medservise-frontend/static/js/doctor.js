const token = localStorage.getItem("token");
if (!token) {
  alert("Avval tizimga kiring!");
  window.location.href = "/";
}

// ⛳ Auto-detect API base dynamically
const API = window.location.origin.replace(/\/+$/, "") + "/api/v1/";

document.addEventListener("DOMContentLoaded", () => {
  // 🔒 User check
  fetch(`${API}profile/`, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((res) => {
      if (!res.ok) throw new Error("Foydalanuvchi aniqlanmadi");
      return res.json();
    })
    .then((user) => {
      if (!user || !user.id) {
        alert("Foydalanuvchi topilmadi");
        localStorage.clear();
        window.location.href = "/";
      }
    })
    .catch((err) => {
      console.error("Foydalanuvchini tekshirishda xatolik:", err);
      localStorage.clear();
      window.location.href = "/";
    });

  const dateFilter = document.getElementById("date-filter");
  const searchName = document.getElementById("search-name");
  const tableBody = document.querySelector("#appointments-table tbody");

  function loadAppointments(date = null, search = "") {
    fetch(`${API}my-appointments/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Qabul ma'lumotlarini olishda xatolik");
        return res.json();
      })
      .then((data) => {
        tableBody.innerHTML = "";
        let appointments = data.appointments;

        if (date) {
          const selectedDate = new Date(date).toDateString();
          appointments = appointments.filter(app =>
            new Date(app.created_at).toDateString() === selectedDate
          );
        }

        if (search.trim() !== "") {
          const lowerSearch = search.toLowerCase();
          appointments = appointments.filter(app =>
            `${app.patient.first_name} ${app.patient.last_name}`.toLowerCase().includes(lowerSearch)
          );
        }

        appointments.forEach((app) => {
          const row = document.createElement("tr");
          const createdAt = new Date(app.created_at).toLocaleString();
          const fullName = `${app.patient.first_name} ${app.patient.last_name}`;
          const isQueued = app.status === "queued";

          const buttons = `
            <div class="d-flex flex-column gap-1">
              ${isQueued ? `
                <button class="btn btn-sm btn-warning" onclick="callPatient(${app.id})">📣 Chaqirish</button>
                <button class="btn btn-sm btn-success" onclick="markDone(${app.id})">✅ Bajarildi</button>
              ` : ""}
              <button class="btn btn-sm btn-info" onclick="viewInfo(${app.patient.id})">ℹ️ Maʼlumot</button>
              <button class="btn btn-sm btn-danger" onclick="confirmDelete(${app.id})">🗑️ Oʻchirish</button>
            </div>
          `;

          row.innerHTML = `
            <td>${fullName}</td>
            <td>${app.reason}</td>
            <td>${app.status}</td>
            <td>${createdAt}</td>
            <td>${buttons}</td>
          `;
          tableBody.appendChild(row);
        });
      })
      .catch(err => {
        console.error("Qabul ro'yxatini yuklashda xatolik:", err);
      });
  }

  // 🔃 Auto-refresh every 5 seconds
  setInterval(() => {
    const selectedDate = dateFilter?.value || null;
    const nameQuery = searchName?.value || "";
    loadAppointments(selectedDate, nameQuery);
  }, 5000);

  document.getElementById("filter-today-btn")?.addEventListener("click", () => {
    const today = new Date().toISOString().split("T")[0];
    dateFilter.value = today;
    loadAppointments(today, searchName.value);
  });

  document.getElementById("apply-filters-btn")?.addEventListener("click", () => {
    const selectedDate = dateFilter.value;
    const nameQuery = searchName.value;
    loadAppointments(selectedDate || null, nameQuery);
  });

  loadAppointments();
});

function markDone(id) {
  fetch(`${API}my-appointments/${id}/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ status: "done" }),
  })
    .then(res => {
      if (!res.ok) throw new Error("Qabulni yangilab boʻlmadi.");
      return res.json();
    })
    .then(() => fetch(`${API}clear-call/${id}/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` }
    }))
    .catch(err => {
      console.error("Yakuni bo'yicha xatolik:", err);
      alert("❌ Qabulni yakunlab boʻlmadi.");
    });
}

function callPatient(appointmentId) {
  fetch(`${API}call-patient/${appointmentId}/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
    .then((res) => {
      if (!res.ok) throw new Error("Chaqirishda xatolik");
      return res.json();
    })
    .then(() => {
      new Audio("/static/sound/beepmm.wav").play();
      const btn = document.querySelector(`button[onclick="callPatient(${appointmentId})"]`);
      if (btn) {
        btn.textContent = "🔁 Qayta chaqirish";
        btn.classList.remove("btn-warning");
        btn.classList.add("btn-secondary");
      }
    })
    .catch((err) => {
      console.error("Chaqirishda xatolik:", err);
    });
}

function confirmDelete(id) {
  if (confirm("Rostdan ham ushbu qabuli o‘chirmoqchimisiz?")) {
    deleteApp(id);
  }
}

function deleteApp(id) {
  fetch(`${API}my-appointments/${id}/`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
    .then((res) => {
      if (!res.ok) throw new Error("Qabulni o'chirib boʻlmadi.");
    })
    .catch(err => {
      console.error("O'chirishda xatolik:", err);
      alert("❌ Oʻchirishda xatolik.");
    });
}

function viewInfo(patientId) {
  window.location.href = `/doctor/patient-detail/?patient_id=${patientId}`;
}

function logout() {
  localStorage.clear();
  window.location.href = "/";
}
