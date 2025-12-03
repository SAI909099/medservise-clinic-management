
document.addEventListener("DOMContentLoaded", function () {

  // 🔥 Auto-detected base API
  const API_BASE = (window.API_BASE || location.origin.replace(/\/+$/, '')) + "/api/v1/";

  const form = document.querySelector("form");

  // ------------------------ LOGIN FORM SUBMIT ------------------------
  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();

      const email = document.querySelector("input[name='email']").value;
      const password = document.querySelector("input[name='password']").value;

      fetch(API_BASE + "login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      })
        .then((response) => {
          if (!response.ok) throw new Error("Login ma'lumotlari noto‘g‘ri");
          return response.json();
        })
        .then((data) => {
          if (data.access) {
            localStorage.setItem("token", data.access);
            localStorage.setItem("refresh", data.refresh);

            return fetch(API_BASE + "user-profile/", {
              headers: { Authorization: `Bearer ${data.access}` },
            }).then(res => {
              if (!res.ok) throw new Error("Foydalanuvchi aniqlanmadi");
              return res.json();
            });
          } else {
            throw new Error("Access token topilmadi");
          }
        })
        .then((user) => {
          if (!user) throw new Error("Foydalanuvchi aniqlanmadi");

          localStorage.setItem("role", user.role || "");
          localStorage.setItem("is_superuser", user.is_superuser ? "true" : "false");

          console.log("✅ Role:", user.role);
          console.log("✅ Is Superuser:", user.is_superuser);

          alert("✅ Tizimga muvaffaqiyatli kirildi!");

          if (user.is_superuser === true) {
            window.location.href = "/admin-dashboard/";
          } else {
            switch (user.role) {
              case "doctor":
                window.location.href = "/doctor/";
                break;
              case "cashier":
                window.location.href = "/cash-register/";
                break;
              case "accountant":
                window.location.href = "/accounting-dashboard/";
                break;
              case "registration":
                window.location.href = "/registration/";
                break;
              default:
                alert("❌ Ruxsatsiz foydalanuvchi turi");
                localStorage.clear();
                window.location.href = "/";
            }
          }
        })
        .catch((error) => {
          alert("Kirishda xatolik: " + error.message);
          localStorage.clear();
        });
    });
  }

  // ------------------------ PAGE ACCESS CONTROLS ------------------------
  const path = window.location.pathname;
  const token = localStorage.getItem("token");
  const role = localStorage.getItem("role");
  const isSuperuser = localStorage.getItem("is_superuser") === "true";

  const redirectHome = () => {
    alert("❌ Sizda ushbu sahifaga kirish huquqi yo‘q.");
    localStorage.clear();
    window.location.href = "/";
  };

  if (path === "/admin-dashboard/" && (!token || !isSuperuser)) redirectHome();
  if (path === "/doctor/" && (!token || role !== "doctor")) redirectHome();
  if (path === "/cash-register/" && (!token || role !== "cashier")) redirectHome();
  if (path === "/accounting-dashboard/" && (!token || role !== "accountant")) redirectHome();
  if (path === "/registration/" && (!token || role !== "registration")) redirectHome();

  // ------------------------ DOCTOR DASHBOARD LOGIC ------------------------
  if (path === "/doctor/") {
    fetch(API_BASE + "my-appointments/", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Ma'lumotlarni olishda xatolik");
        return res.json();
      })
      .then((data) => {
        const tableBody = document.querySelector("#appointments-table tbody");
        if (!tableBody) return;

        tableBody.innerHTML = "";

        data.forEach((app) => {
          const row = document.createElement("tr");
          row.innerHTML = `
            <td>${app.patient.first_name} ${app.patient.last_name}</td>
            <td>${app.reason}</td>
            <td>${app.status}</td>
            <td>${new Date(app.created_at).toLocaleString()}</td>
            <td class="action-buttons">
              ${app.status === "queued"
                ? `<button class="btn btn-sm btn-success" onclick="markDone(${app.id})">Yakunlandi</button>`
                : ''}
              <button class="btn btn-sm btn-danger" onclick="deleteApp(${app.id})">Oʻchirish</button>
              <button class="btn btn-sm btn-info" onclick="viewUploads(${app.patient.id})">Fayllar</button>
            </td>
          `;
          tableBody.appendChild(row);
        });
      })
      .catch((err) => {
        console.error("Appointmentlarni olishda xatolik:", err);
        alert("Qabul roʻyxatini yuklab boʻlmadi.");
      });
  }
});

// ------------------------ MARK DONE ------------------------
function markDone(id) {
  const token = localStorage.getItem("token");
  const API_BASE = (window.API_BASE || location.origin.replace(/\/+$/, '')) + "/api/v1/";

  fetch(API_BASE + `doctor/appointments/${id}/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    },
    body: JSON.stringify({ status: "done" }),
  })
    .then((res) => {
      if (res.ok) {
        window.location.reload();
      } else {
        alert("Yakunlashda xatolik.");
      }
    });
}

// ------------------------ DELETE APPOINTMENT ------------------------
function deleteApp(id) {
  const token = localStorage.getItem("token");
  const API_BASE = (window.API_BASE || location.origin.replace(/\/+$/, '')) + "/api/v1/";

  fetch(API_BASE + `doctor/appointments/${id}/`, {
    method: "DELETE",
    headers: {
      "Authorization": `Bearer ${token}`,
    },
  })
    .then((res) => {
      if (res.ok) {
        window.location.reload();
      } else {
        alert("Oʻchirishda xatolik.");
      }
    });
}

// ------------------------ VIEW PATIENT UPLOADS ------------------------
function viewUploads(patientId) {
  const token = localStorage.getItem("token");
  const API_BASE = (window.API_BASE || location.origin.replace(/\/+$/, '')) + "/api/v1/";

  fetch(API_BASE + `patient-results/?patient=${patientId}`, {
    headers: {
      "Authorization": `Bearer ${token}`,
    },
  })
    .then((res) => res.json())
    .then((data) => {
      if (!data.length) {
        alert("Ushbu bemor uchun fayllar topilmadi.");
        return;
      }

      let msg = "Yuklangan fayllar:\n";
      data.forEach((result) => {
        msg += `• ${result.title} — ${new Date(result.uploaded_at).toLocaleString()}\n`;
      });

      alert(msg);
    })
    .catch((err) => {
      console.error("Fayllarni olishda xatolik:", err);
      alert("Fayllarni ko‘rsatib bo‘lmadi.");
    });
}

// ------------------------ LOGOUT FUNCTION ------------------------
function logout() {
  localStorage.clear();
  window.location.href = "/";
}
