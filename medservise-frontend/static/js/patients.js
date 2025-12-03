document.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("token");
  const role = localStorage.getItem("role");

  // 🔥 Dynamic API base — works on any server/ip
  const BASE_API =
    (window.API_BASE || location.origin.replace(/\/+$/, "")) + "/api/v1/";

  if (!token || !["admin", "doctor", "registration"].includes(role)) {
    alert("Iltimos, tizimga kiring.");
    location.href = "/";
    return;
  }

  fetch(`${BASE_API}register-patient/`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  })
    .then(res => {
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          alert("Sessiya tugagan. Qaytadan kiring.");
          localStorage.clear();
          location.href = "/";
          throw new Error("Unauthorized");
        }
        throw new Error("Bemorlar ro‘yxatini yuklab bo‘lmadi.");
      }
      return res.json();
    })
    .then(patients => {
      const tbody = document.getElementById("patient-table-body");
      tbody.innerHTML = "";

      if (!patients.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Bemorlar topilmadi</td></tr>`;
        return;
      }

      patients.forEach((patient, index) => {
        const tr = document.createElement("tr");
        const doctorName = patient.patients_doctor_name || "—";
        const createdDate = patient.created_at
          ? new Date(patient.created_at).toLocaleString("uz-UZ")
          : "—";

        tr.innerHTML = `
          <td>${index + 1}</td>
          <td>${patient.first_name} ${patient.last_name}</td>
          <td>${patient.phone}</td>
          <td>${doctorName}</td>
          <td>${createdDate}</td>
          <td>
            <a href="patient-detail.html?patient_id=${patient.id}" class="btn btn-sm btn-outline-info">
              📄 Info
            </a>
          </td>
        `;
        tbody.appendChild(tr);
      });
    })
    .catch(err => {
      console.error("❌ Xatolik bemorlarni yuklashda:", err);
      alert("❌ Bemorlar ro‘yxatini yuklab bo‘lmadi.");
    });
});
