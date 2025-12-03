document.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("token");
  if (!token) {
    alert("Login required.");
    location.href = "/";
    return;
  }

  // ✅ Dynamic BASE_URL — works on ANY IP, domain, localhost, Docker, etc.
  const BASE_URL =
    (window.API_BASE || location.origin.replace(/\/+$/, "")) + "/api/v1/";

  const headers = { Authorization: `Bearer ${token}` };

  const doctorSelect = document.getElementById("doctor_id");
  const serviceContainer = document.getElementById("service-options");
  const form = document.getElementById("patient-form");

  let allServices = [];

  // Load doctors
  fetch(`${BASE_URL}doctor-list/`, { headers })
    .then(res => res.json())
    .then(doctors => {
      doctors.forEach(doc => {
        const option = document.createElement("option");
        option.value = doc.id;
        option.textContent = doc.name;
        option.dataset.price = doc.consultation_price || 0;
        doctorSelect.appendChild(option);
      });
    })
    .catch(err => console.error("❌ Failed to fetch doctors:", err));

  // Load services
  fetch(`${BASE_URL}services/`, { headers })
    .then(res => res.json())
    .then(data => {
      allServices = data;
    })
    .catch(err => console.error("❌ Failed to fetch services:", err));

  doctorSelect.addEventListener("change", () => {
    const selectedDoctorId = parseInt(doctorSelect.value);
    const selectedPrice = parseFloat(
      doctorSelect.options[doctorSelect.selectedIndex].dataset.price || 0
    );
    document.getElementById("expected_fee").value = selectedPrice.toFixed(2);

    serviceContainer.innerHTML = "";
    const filtered = allServices.filter(s => s.doctor?.id === selectedDoctorId);

    filtered.forEach(service => {
      const div = document.createElement("div");
      div.className = "form-check";
      div.innerHTML = `
        <input class="form-check-input service-checkbox" type="checkbox"
               id="service-${service.id}" value="${service.price}" data-id="${service.id}">
        <label class="form-check-label" for="service-${service.id}">
          ${service.name} (${service.price} so'm)
        </label>
      `;
      serviceContainer.appendChild(div);
    });

    updateTotalFee();
  });

  serviceContainer.addEventListener("change", updateTotalFee);

  function updateTotalFee() {
    const doctorFee = parseFloat(
      document.getElementById("expected_fee").value || 0
    );
    const selectedServices = document.querySelectorAll(
      ".service-checkbox:checked"
    );
    const serviceTotal = Array.from(selectedServices).reduce(
      (sum, el) => sum + parseFloat(el.value),
      0
    );
    const total = doctorFee + serviceTotal;
    document.getElementById("total_fee").value = total.toFixed(2);
  }

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const doctorId = parseInt(doctorSelect.value);
    if (isNaN(doctorId)) {
      alert("Please select a doctor.");
      return;
    }

    const selectedServiceIds = Array.from(
      document.querySelectorAll(".service-checkbox:checked")
    ).map(el => parseInt(el.dataset.id));

    const data = {
      first_name: document.getElementById("first_name").value.trim(),
      last_name: document.getElementById("last_name").value.trim(),
      age: parseInt(document.getElementById("age").value),
      phone: document.getElementById("phone").value.trim(),
      address: document.getElementById("address").value.trim(),
      doctor_id: doctorId,
      reason: document.getElementById("reason").value.trim(),
      services: selectedServiceIds,
      amount_paid: parseFloat(
        document.getElementById("total_fee").value || 0
      ),
      amount_owed: 0
    };

    try {
      const res = await fetch(`${BASE_URL}register-patient/`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error("Registration failed: " + errorText);
      }

      const result = await res.json();
      console.log("✅ Patient registered:", result);
      alert("✅ Bemor muvaffaqiyatli ro'yxatdan o'tdi!");

      const printData = {
        receipt_number:
          result.id || result.turn_number || "N/A",
        date:
          result.date ||
          new Date().toLocaleString("uz-UZ", {
            dateStyle: "short",
            timeStyle: "short"
          }),
        patient_name: `${result.patient.first_name} ${result.patient.last_name}`,
        doctor_name: result.doctor_name || "Nomaʼlum",
        turn_number: result.turn_number || "N/A",
        patient_id: result.patient.id || "N/A",
        amount:
          parseFloat(
            document.getElementById("total_fee").value || 0
          )
            .toFixed(0)
            .replace(/\B(?=(\d{3})+(?!\d))/g, ".") + " so'm",
        payment_method: result.payment_method || "Naqd",
        status: result.status || "PAID",
        notes: result.reason || "Yoʻq",
        processed_by: result.processed_by || "Tizim"
      };

      openPrintWindow(printData);

      form.reset();
      serviceContainer.innerHTML = "";
      document.getElementById("expected_fee").value = "";
      document.getElementById("total_fee").value = "";
    } catch (err) {
      console.error("❌ Error:", err.message);
      alert("❌ Xatolik: " + err.message);
    }
  });

  function openPrintWindow(data) {
    const win = window.open("", "PrintWindow", "width=400,height=600");

    const lines = [
      "MEDSERVISE CLINIC",
      "-----------------------------",
      `Chek raqami: ${data.receipt_number}`,
      `Sana: ${data.date}`,
      `Bemor: ${data.patient_name}`,
      `Shifokor: ${data.doctor_name}`,
      `Navbat raqami: ${data.turn_number}`,
      `Miqdori: ${data.amount}`,
      `To'lov usuli: ${data.payment_method}`,
      `Holat: ${data.status}`,
      `Izoh: ${data.notes}`,
      `Qabulchi: ${data.processed_by}`,
      "-----------------------------",
      "Rahmat! Kuningiz yaxshi otsin!"
    ];

    const encodedReceipt = encodeURIComponent(lines.join("\n"));

    win.document.write(`
      <html lang="uz">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Ro'yxatdan o'tish cheki</title>
          <style>
            body { font-family: Arial, sans-serif; text-align:center; margin:20px; }
            .receipt { max-width:400px; margin:0 auto; border:1px solid #000; padding:20px; }
            .header { font-size:24px; font-weight:bold; margin-bottom:20px; }
            .details { text-align:left; margin-bottom:20px; }
            .details p { margin:5px 0; font-size:16px; }
            img { display:block; margin:10px auto; width:100px; height:100px; }
            button { padding:10px 20px; font-size:16px; cursor:pointer; margin:5px; }
            @media print { button { display:none; } @page { margin:0; } }
          </style>
        </head>
        <body>
          <div class="receipt">
            <div class="header">Ro'yxatdan o'tish cheki</div>
            <div class="details">
              <p><strong>Chek raqami:</strong> ${data.receipt_number}</p>
              <p><strong>Sana:</strong> ${data.date}</p>
              <p><strong>Bemor ismi:</strong> ${data.patient_name}</p>
              <p><strong>Shifokor ismi:</strong> ${data.doctor_name}</p>
              <p><strong>Navbat raqami:</strong> <span style="font-size:20px; font-weight:bold;">${data.turn_number}</span></p>
              <p><strong>Summa:</strong> ${data.amount}</p>
              <p><strong>To'lov usuli:</strong> ${data.payment_method}</p>
              <p><strong>Holat:</strong> ${data.status}</p>
              <p><strong>Izoh:</strong> ${data.notes}</p>
              <p><strong>Qabul qilgan:</strong> ${data.processed_by}</p>
            </div>
            <img id="qr-code" src="https://api.qrserver.com/v1/create-qr-code/?data=${encodedReceipt}&size=100x100">
            <button onclick="window.print()">Chop etish</button>
            <button onclick="window.close()">Yopish</button>
          </div>
          <script>
            window.onload = () => {
              window.focus();
              setTimeout(() => { window.print(); window.onafterprint = () => window.close(); }, 600);
            };
          </script>
        </body>
      </html>
    `);

    win.document.close();
  }
});

function logout() {
  localStorage.removeItem("token");
  location.href = "/";
}
