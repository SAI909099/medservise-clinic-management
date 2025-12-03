// 🔥 Dynamic BASE_URL — works on any IP/domain/localhost
const BASE_URL =
  (window.API_BASE || location.origin.replace(/\/+$/, "")) + "/api/v1";

const token = localStorage.getItem("token");

if (!token) {
  alert("You are not logged in. Please log in first.");
  window.location.href = "/login.html";
}

const headers = {
  "Content-Type": "application/json",
  Authorization: `Bearer ${token}`,
};

const doctorPrices = {};
const servicePrices = {};
const roomPrices = {};

document.addEventListener("DOMContentLoaded", () => {
  fetchDoctors();
  fetchServices();
  fetchRooms();
});

// ===========================
// DOCTORS
// ===========================
function fetchDoctors() {
  fetch(`${BASE_URL}/doctor-list/`, { headers })
    .then((res) => res.json())
    .then((doctors) => {
      const list = document.getElementById("doctor-price-list");
      list.innerHTML = "";
      doctors.forEach((doc) => {
        doctorPrices[doc.id] = doc.consultation_price;
        const li = document.createElement("li");
        li.className =
          "list-group-item d-flex justify-content-between align-items-center";
        li.innerHTML = `
          <span>${doc.name}</span>
          <input type="number" step="0.01" class="form-control form-control-sm w-25"
                 value="${doc.consultation_price}" onchange="doctorPrices[${doc.id}] = this.value">
        `;
        list.appendChild(li);
      });
    })
    .catch((err) => {
      console.error("Failed to fetch doctors:", err);
      alert("Could not load doctor prices.");
    });
}

function confirmDoctorPriceChanges() {
  Object.entries(doctorPrices).forEach(([id, price]) => {
    fetch(`${BASE_URL}/doctor-list/${id}/`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ consultation_price: price }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to update");
        console.log(`Doctor ${id} updated`);
      })
      .catch((err) => alert(`Doctor ${id} update error: ` + err.message));
  });
  alert("✅ Doctor prices updated");
}

// ===========================
// SERVICES
// ===========================
function fetchServices() {
  fetch(`${BASE_URL}/services/`, { headers })
    .then((res) => res.json())
    .then((services) => {
      const list = document.getElementById("service-price-list");
      list.innerHTML = "";
      services.forEach((service) => {
        servicePrices[service.id] = service.price;
        const li = document.createElement("li");
        li.className =
          "list-group-item d-flex justify-content-between align-items-center";
        li.innerHTML = `
          <span>${service.name} (${service.doctor?.name || "No Doctor"})</span>
          <input type="number" step="0.01" class="form-control form-control-sm w-25"
                 value="${service.price}" onchange="servicePrices[${service.id}] = this.value">
        `;
        list.appendChild(li);
      });
    })
    .catch((err) => {
      console.error("Failed to fetch services:", err);
      alert("Could not load services.");
    });
}

function confirmServicePriceChanges() {
  Object.entries(servicePrices).forEach(([id, price]) => {
    fetch(`${BASE_URL}/services/${id}/`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ price: price }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to update");
        console.log(`Service ${id} updated`);
      })
      .catch((err) => alert(`Service ${id} update error: ` + err.message));
  });
  alert("✅ Service prices updated");
}

// ===========================
// ROOMS
// ===========================
function fetchRooms() {
  fetch(`${BASE_URL}/treatment-rooms/`, { headers })
    .then((res) => res.json())
    .then((rooms) => {
      const list = document.getElementById("room-price-list");
      list.innerHTML = "";
      rooms.forEach((room) => {
        roomPrices[room.id] = room.price_per_day;
        const li = document.createElement("li");
        li.className =
          "list-group-item d-flex justify-content-between align-items-center";
        li.innerHTML = `
          <span>${room.name} (Floor ${room.floor})</span>
          <input type="number" step="0.01" class="form-control form-control-sm w-25"
                 value="${room.price_per_day}" onchange="roomPrices[${room.id}] = this.value">
        `;
        list.appendChild(li);
      });
    })
    .catch((err) => {
      console.error("Failed to fetch rooms:", err);
      alert("Could not load treatment rooms.");
    });
}

function confirmRoomPriceChanges() {
  Object.entries(roomPrices).forEach(([id, price]) => {
    fetch(`${BASE_URL}/treatment-rooms/${id}/`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ price_per_day: price }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to update");
        console.log(`Room ${id} updated`);
      })
      .catch((err) => alert(`Room ${id} update error: ` + err.message));
  });
  alert("✅ Room prices updated");
}
