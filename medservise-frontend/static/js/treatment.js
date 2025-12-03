document.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("token");
  if (!token) {
    alert("Login required");
    window.location.href = "index.html";
    return;
  }

  // 🔥 Dynamic API base
  const BASE_URL = (window.API_BASE || location.origin.replace(/\/+$/, "")) + "/api/v1";

  const form = document.getElementById("room-form");
  const roomNameInput = document.getElementById("room-name");
  const capacityInput = document.getElementById("capacity");
  const floorInput = document.getElementById("floor");
  const priceInput = document.getElementById("price");

  const floor1 = document.getElementById("floor-1");
  const floor2 = document.getElementById("floor-2");

  form.addEventListener("submit", e => {
    e.preventDefault();

    const data = {
      name: roomNameInput.value.trim(),
      capacity: parseInt(capacityInput.value),
      floor: parseInt(floorInput.value),
      price_per_day: parseFloat(priceInput.value),
    };

    const editId = form.dataset.editId;

    // 🔧 FIXED URL
    const url = editId
      ? `${BASE_URL}/treatment-rooms/${editId}/`
      : `${BASE_URL}/treatment-rooms/`;

    const method = editId ? "PUT" : "POST";

    fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data)
    })
      .then(res => {
        if (!res.ok) throw new Error(`${method === "PUT" ? "Update" : "Create"} failed`);
        return res.json();
      })
      .then(() => {
        form.reset();
        delete form.dataset.editId;
        form.querySelector("button[type=submit]").textContent = "Add";
        loadRooms();
        alert(`✅ Room ${method === "PUT" ? "updated" : "registered"} successfully.`);
      })
      .catch(err => {
        console.error(err);
        alert("❌ Operation failed.");
      });
  });

  function loadRooms() {
    // 🔧 FIXED URL
    fetch(`${BASE_URL}/treatment-rooms/`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(rooms => {
      floor1.innerHTML = "";
      floor2.innerHTML = "";

      rooms.forEach(room => {
        const card = document.createElement("div");
        card.className = "card p-3 m-2 shadow-sm";
        card.style.width = "200px";
        card.innerHTML = `
          <h5>${room.name}</h5>
          <p>Soni: ${room.capacity}</p>
          <p>Kunlik Tulov: ${room.price_per_day} UZS</p>
          <div class="d-flex justify-content-between mt-2">
            <button class="btn btn-sm btn-warning edit-btn">Edit</button>
            <button class="btn btn-sm btn-danger delete-btn">Delete</button>
          </div>
        `;

        // Edit button handler
        card.querySelector(".edit-btn").addEventListener("click", () => {
          roomNameInput.value = room.name;
          capacityInput.value = room.capacity;
          floorInput.value = room.floor;
          priceInput.value = room.price_per_day;

          form.dataset.editId = room.id;
          form.querySelector("button[type=submit]").textContent = "Update";
        });

        // Delete button handler
        card.querySelector(".delete-btn").addEventListener("click", () => {
          if (confirm("Are you sure you want to delete this room?")) {
            
            // 🔧 FIXED URL
            fetch(`${BASE_URL}/treatment-rooms/${room.id}/`, {
              method: "DELETE",
              headers: { Authorization: `Bearer ${token}` }
            })
            .then(res => {
              if (res.ok) {
                loadRooms();
                alert("🗑️ Room deleted.");
              } else {
                alert("❌ Delete failed.");
              }
            });
          }
        });

        if (room.floor === 1) {
          floor1.appendChild(card);
        } else if (room.floor === 2) {
          floor2.appendChild(card);
        }
      });
    })
    .catch(err => {
      console.error("❌ Failed to load rooms", err);
    });
  }

  loadRooms();
});
