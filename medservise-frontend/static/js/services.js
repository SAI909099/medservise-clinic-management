// ==== Dynamic API Base (fix) ====
const BASE_URL =
  (window.API_BASE || location.origin.replace(/\/+$/, "")) + "/api/v1";

const token = localStorage.getItem("token");

if (!token) {
  alert("🔐 Iltimos, tizimga kiring.");
  window.location.href = "/";
}

document.addEventListener("DOMContentLoaded", () => {
  const doctorList = document.getElementById("doctor-list");
  const serviceForm = document.getElementById("service-form");
  const serviceList = document.getElementById("service-list");
  const doctorSelect = document.getElementById("doctor-select");

  function loadDoctors() {
    fetch(`${BASE_URL}/doctor-list/`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        if (doctorList) doctorList.innerHTML = "";
        if (doctorSelect) doctorSelect.innerHTML = '<option disabled selected>Doktor tanlang</option>';

        data.forEach(doc => {
          if (doctorList) {
            const li = document.createElement("li");
            li.className =
              "list-group-item d-flex justify-content-between align-items-center";
            li.innerHTML = `<div><strong>${doc.name}</strong> — ${
              doc.specialty || "—"
            }</div>`;
            doctorList.appendChild(li);
          }

          if (doctorSelect) {
            const option = document.createElement("option");
            option.value = doc.id;
            option.textContent = doc.name;
            doctorSelect.appendChild(option);
          }
        });
      });
  }

  function loadServices() {
    fetch(`${BASE_URL}/services/`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        if (serviceList) serviceList.innerHTML = "";
        data.forEach(service => {
          const li = document.createElement("li");
          li.className =
            "list-group-item d-flex justify-content-between align-items-center";
          li.innerHTML = `<div><strong>${service.name}</strong> — ${
            service.price
          } so'm (${service.doctor?.name || "Doktor yo‘q"})</div>`;
          serviceList.appendChild(li);
        });
      });
  }

  if (serviceForm) {
    serviceForm.addEventListener("submit", e => {
      e.preventDefault();

      const name = document.getElementById("service-name").value.trim();
      const price = parseFloat(document.getElementById("service-price").value);
      const doctorId = parseInt(document.getElementById("doctor-select").value);

      if (!name || !price || !doctorId) {
        alert("❗ Barcha maydonlarni to‘ldiring.");
        return;
      }

      fetch(`${BASE_URL}/services/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          name,
          price,
          doctor_id: doctorId
        })
      })
        .then(res => {
          if (!res.ok)
            return res.json().then(err => {
              throw err;
            });
          return res.json();
        })
        .then(() => {
          alert("✅ Xizmat qo‘shildi.");
          serviceForm.reset();
          loadServices();
        })
        .catch(err => {
          console.error("❌ Xatolik:", err);
          alert("❌ Saqlashda xatolik.");
        });
    });
  }

  loadDoctors();
  loadServices();
});
