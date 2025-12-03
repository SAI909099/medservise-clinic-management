document.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("token");
  if (!token) {
    alert("Tizimga avval kiring.");
    window.location.href = "/";
    return;
  }

  // === FIXED: Dynamic API base ===
  const API =
    (window.API_BASE || location.origin.replace(/\/+$/, "")) + "/api/v1/";
  const headers = { Authorization: `Bearer ${token}` };

  const doctorSelect = document.getElementById("doctor-select");
  const patientSelect = document.getElementById("patient-select");
  const roomSelect = document.getElementById("room-select");
  const assignBtn = document.getElementById("assign-btn");
  const roomGrid = document.getElementById("room-grid");

  // Load doctors into select
  function loadDoctors() {
    fetch(`${API}doctor-list/`, { headers })
      .then(res => res.json())
      .then(doctors => {
        doctorSelect.innerHTML = '<option value="">Barcha shifokorlar</option>';
        doctors.forEach(doc => {
          const opt = document.createElement("option");
          opt.value = doc.id;
          opt.textContent = doc.name;
          doctorSelect.appendChild(opt);
        });
      })
      .catch(err => {
        console.error("❌ Doktorlar yuklanmadi:", err);
        alert("❌ Doktorlar ro'yxatini yuklashda xatolik.");
      });
  }

  // Load patients filtered by date and doctor
  function loadPatients(doctorId = null) {
    fetch(`${API}patients/`, { headers })
      .then(res => res.json())
      .then(patients => {
        const twoDaysAgo = new Date();
        twoDaysAgo.setDate(twoDaysAgo.getDate() - 2);
        const minTime = twoDaysAgo.getTime();

        let filtered = patients.filter(
          p => new Date(p.created_at).getTime() >= minTime
        );

        if (doctorId) {
          filtered = filtered.filter(
            p => p.patients_doctor?.id === parseInt(doctorId)
          );
        }

        patientSelect.innerHTML =
          '<option disabled selected>Bemorni tanlang</option>';
        filtered.forEach(p => {
          const opt = document.createElement("option");
          opt.value = p.id;
          opt.textContent = `${p.first_name} ${p.last_name}`;
          patientSelect.appendChild(opt);
        });
      })
      .catch(err => {
        console.error("❌ Bemorlar yuklanmadi:", err);
        alert("❌ Bemorlar ro'yxatini yuklashda xatolik.");
      });
  }

  // Load treatment rooms and populate UI
  function loadRooms() {
    fetch(`${API}treatment-rooms/`, { headers })
      .then(res => res.json())
      .then(rooms => {
        roomSelect.innerHTML =
          '<option disabled selected>Yotoqxonani tanlang</option>';
        roomGrid.innerHTML = "";

        const floors = {};
        rooms.forEach(room => {
          if (!floors[room.floor]) floors[room.floor] = [];
          floors[room.floor].push(room);

          const opt = document.createElement("option");
          opt.value = room.id;
          opt.textContent = `${room.name} - ${room.floor}-Blok (${room.capacity} o'rin)`;
          roomSelect.appendChild(opt);
        });

        Object.keys(floors)
          .sort()
          .forEach(floor => {
            const floorHeader = document.createElement("h4");
            floorHeader.textContent = `🧱 ${floor}-Blok`;
            roomGrid.appendChild(floorHeader);

            const row = document.createElement("div");
            row.className = "d-flex flex-wrap gap-3 mb-4";

            floors[floor].forEach(room => {
              const patients = room.patients || [];
              const status =
                patients.length === 0
                  ? { text: "✅ Bo'sh", class: "bg-success" }
                  : patients.length < room.capacity
                  ? { text: "🟡 Qisman band", class: "bg-warning" }
                  : { text: "🚫 To‘la", class: "bg-danger" };

              const div = document.createElement("div");
              div.className = `card p-3 text-white ${status.class}`;
              div.style.width = "250px";

              let occupancyHTML = "<ul>";
              for (let i = 0; i < room.capacity; i++) {
                const patient = patients[i];
                occupancyHTML += `<li>${
                  patient
                    ? patient.first_name + " " + patient.last_name
                    : "<i>Bo'sh</i>"
                }</li>`;
              }
              occupancyHTML += "</ul>";

              div.innerHTML = `
                <h5>${room.name}</h5>
                <p><strong>Blok:</strong> ${room.floor}</p>
                <p><strong>Sig‘imi:</strong> ${room.capacity}</p>
                ${occupancyHTML}
                <p><strong>Status:</strong> ${status.text}</p>
              `;
              row.appendChild(div);
            });

            roomGrid.appendChild(row);
          });
      })
      .catch(err => {
        console.error("❌ Xonalar yuklanmadi:", err);
        alert("❌ Yotoqxona ma'lumotlarini yuklashda xatolik.");
      });
  }

  // Assign patient to room
  function assignPatient() {
    const patientId = patientSelect.value;
    const roomId = roomSelect.value;

    if (!patientId || !roomId) {
      return alert("❗ Iltimos, bemor va xona tanlang.");
    }

    fetch(`${API}assign-patient-to-room/`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ patient_id: patientId, room_id: roomId })
    })
      .then(res => {
        if (!res.ok) throw new Error("Xatolik yuz berdi");
        return res.json();
      })
      .then(() => {
        alert("✅ Bemor yotoqxonaga muvaffaqiyatli joylashtirildi.");
        loadRooms();
        loadPatients(doctorSelect.value);
      })
      .catch(err => {
        console.error("❌ Joylashtirishda xatolik:", err);
        alert("❌ Bemorni joylashtirishda xatolik.");
      });
  }

  // Event listeners
  assignBtn.addEventListener("click", assignPatient);
  doctorSelect.addEventListener("change", () => {
    loadPatients(doctorSelect.value || null);
  });

  // Initial load
  loadDoctors();
  loadRooms();
  loadPatients();
});
