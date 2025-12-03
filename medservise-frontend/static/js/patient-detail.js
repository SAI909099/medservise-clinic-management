const token = localStorage.getItem("token");
const role = localStorage.getItem("role");
const urlParams = new URLSearchParams(window.location.search);
const patientId = urlParams.get("patient_id");

// 🔥 Auto-detect BASE API URL (works for any IP/domain/localhost)
const BASE_API_URL = (window.API_BASE || location.origin.replace(/\/+$/, "")) + "/api/v1/";

// ✅ Access check
if (!token || !patientId || !["admin", "doctor"].includes(role)) {
  alert("🔐 Tizimga kirilmagan yoki bemor ID mavjud emas.");
  window.location.href = "/doctor.html";
}

// 🔎 DOM elementlar
const patientInfoDiv = document.getElementById("patient-info");
const resultsListDiv = document.getElementById("results-list");

// ✅ Bemor ma’lumotlarini yuklash
fetch(`${BASE_API_URL}patients/${patientId}/`, {
  headers: { Authorization: `Bearer ${token}` }
})
  .then(res => {
    if (res.status === 401 || res.status === 403) {
      alert("⏳ Sessiya tugagan. Qayta kiring.");
      localStorage.clear();
      window.location.href = "/";
      throw new Error("Auth error");
    }
    if (!res.ok) throw new Error("Bemor topilmadi");
    return res.json();
  })
  .then(patient => {
    patientInfoDiv.innerHTML = `
      <h4>${patient.first_name ?? "?"} ${patient.last_name ?? "?"}</h4>
      <p><strong>📞 Telefon:</strong> ${patient.phone ?? "?"}</p>
      <p><strong>📍 Manzil:</strong> ${patient.address ?? "?"}</p>
      <p><strong>🕒 Ro‘yxatdan o‘tgan sana:</strong> ${new Date(patient.created_at).toLocaleString("uz-UZ")}</p>
      <a href="/archive/" class="btn btn-secondary btn-sm mt-2">⬅️ Orqaga</a>
    `;
  })
  .catch(err => {
    console.error("❌ Bemor maʼlumotini yuklashda xatolik", err);
    alert("❌ Bemor maʼlumotini yuklab bo‘lmadi.");
  });

// ✅ Natija yuklash formasi
document.getElementById("upload-form").addEventListener("submit", e => {
  e.preventDefault();

  const title = document.getElementById("result-title").value.trim();
  const file = document.getElementById("result-file").files[0];
  const desc = document.getElementById("result-description").value;

  if (!title || !file) {
    alert("❌ Sarlavha va fayl majburiy.");
    return;
  }

  const formData = new FormData();
  formData.append("title", title);
  formData.append("description", desc);
  formData.append("result_file", file);
  formData.append("patient", patientId);

  fetch(`${BASE_API_URL}patient-results/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: formData
  })
    .then(async res => {
      if (!res.ok) {
        const errText = await res.text();
        console.error("❌ Server error:", errText);
        throw new Error("Yuklashda xatolik");
      }
      return res.json();
    })
    .then(() => {
      alert("✅ Natija muvaffaqiyatli yuklandi.");
      document.getElementById("upload-form").reset();
      loadResults();
    })
    .catch(err => {
      console.error("❌ Yuklash xatoligi", err);
      alert("❌ Yuklab bo‘lmadi. Fayl yoki sarlavhani tekshiring.");
    });
});

// ✅ Natijalarni yuklash
function loadResults() {
  resultsListDiv.innerHTML = "<p>⏳ Yuklanmoqda...</p>";

  fetch(`${BASE_API_URL}patient-results/?patient=${patientId}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
    .then(res => {
      if (!res.ok) throw new Error("To‘plamlarni olishda xatolik");
      return res.json();
    })
    .then(results => {
      if (!results.length) {
        resultsListDiv.innerHTML = "<p>❕ Natijalar topilmadi.</p>";
        return;
      }

      resultsListDiv.innerHTML = "";
      results.forEach(result => {
        const div = document.createElement("div");
        div.className = "border p-3 mb-3 rounded bg-white shadow-sm";

        div.innerHTML = `
          <h6>${result.title}</h6>
          <p>${result.description ?? "Izoh yo‘q"}</p>
          <a href="${result.result_file}" target="_blank" class="btn btn-sm btn-outline-primary me-2">
            📄 Faylni ko‘rish
          </a>
          <button onclick="deleteResult(${result.id})" class="btn btn-sm btn-outline-danger">
            🗑 O‘chirish
          </button><br>
          <small class="text-muted">🕒 Yuklangan: ${new Date(result.uploaded_at).toLocaleString("uz-UZ")}</small>
        `;

        resultsListDiv.appendChild(div);
      });
    })
    .catch(err => {
      console.error("❌ Natijalarni yuklashda xatolik", err);
      resultsListDiv.innerHTML = "<p>❌ Yuklab bo‘lmadi.</p>";
    });
}

// ✅ Natijani o‘chirish
function deleteResult(id) {
  if (!confirm("🗑 Ushbu natijani o‘chirmoqchimisiz?")) return;

  fetch(`${BASE_API_URL}patient-results/${id}/`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`
    }
  })
    .then(res => {
      if (!res.ok) throw new Error("O‘chirishda xatolik");
      alert("🗑️ O‘chirildi");
      loadResults();
    })
    .catch(err => {
      console.error("❌ O‘chirish xatoligi", err);
      alert("❌ O‘chirib bo‘lmadi");
    });
}

// ⬇️ Boshlang‘ich yuklash
loadResults();
