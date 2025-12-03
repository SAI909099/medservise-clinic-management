document.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("token");
  const role = localStorage.getItem("role");

  // 🔥 FIXED: dynamic auto-detect API base
  const BASE_API_URL = `${window.location.origin}/api/v1/`;

  const tbody = document.querySelector("#payments-table tbody");

  // Allow only doctors, admins, or accountants
  const allowedRoles = ["doctor", "admin", "accountant"];
  if (!token || !allowedRoles.includes(role)) {
    alert("Avval tizimga kirishingiz kerak!");
    window.location.href = "/"; // redirect to login
    return;
  }

  function formatAmount(amount) {
    const num = Number(amount);
    return isNaN(num) ? "Nomaʼlum" : `${num.toLocaleString()} so'm`;
  }

  function formatDate(dateStr) {
    if (!dateStr) return "Nomaʼlum sana";
    const date = new Date(dateStr);
    return date.toLocaleString("uz-UZ");
  }

  function loadDoctorPayments() {
    fetch(`${BASE_API_URL}doctor-payments/`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => {
        if (res.status === 401 || res.status === 403) {
          alert("Sessiya muddati tugagan. Qayta kiring.");
          localStorage.clear();
          window.location.href = "/";
          throw new Error("Auth failed");
        }
        if (!res.ok) throw new Error("To‘lovlarni yuklab bo‘lmadi");
        return res.json();
      })
      .then((data) => {
        tbody.innerHTML = "";
        if (data.length === 0) {
          tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">To‘lovlar topilmadi</td></tr>`;
          return;
        }

        data.forEach((payment) => {
          const tr = document.createElement("tr");

          const patientName = `${payment.patient_first_name || ''} ${payment.patient_last_name || ''}`.trim() || "Nomaʼlum bemor";
          const doctorName = `${payment.doctor_first_name || ''} ${payment.doctor_last_name || ''}`.trim() || "Nomaʼlum shifokor";
          const amount = formatAmount(payment.amount_paid);
          const date = formatDate(payment.created_at);
          const notes = payment.notes || "";

          tr.innerHTML = `
            <td>${patientName}</td>
            <td>${doctorName}</td>
            <td>${amount}</td>
            <td>${date}</td>
            <td>${notes}</td>
          `;
          tbody.appendChild(tr);
        });
      })
      .catch((err) => {
        tbody.innerHTML = `<tr><td colspan="5" class="text-danger">Xatolik: ${err.message}</td></tr>`;
        console.error("To‘lovlarni yuklashda xatolik:", err);
      });
  }

  loadDoctorPayments();
});
