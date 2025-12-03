document.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("token");

  // ✅ Dynamic API base (no more hardcoded IP)
  const BASE_API =
    (window.API_BASE || location.origin.replace(/\/+$/, "")) + "/api/v1/";

  function loadRooms() {
    fetch(`${BASE_API}treatment-rooms/`, {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    })
      .then(res => res.json())
      .then(data => {
        const list = document.getElementById("room-list");
        list.innerHTML = "";
        data.forEach(room => {
          const div = document.createElement("div");
          div.className = `card m-2 p-3 ${room.is_busy ? 'bg-danger text-white' : 'bg-success text-white'}`;
          div.style.width = '200px';
          div.innerHTML = `
            <h5>${room.name}</h5>
            <p>Capacity: ${room.capacity}</p>
            <p>Status: ${room.is_busy ? "Busy" : "Available"}</p>
          `;
          list.appendChild(div);
        });
      })
      .catch(err => {
        console.error("❌ Failed to load rooms:", err);
        alert("Xonalarni yuklashda xatolik yuz berdi.");
      });
  }

  document.getElementById("add-room-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const name = document.getElementById("room-name").value;
    const capacity = document.getElementById("room-capacity").value;

    fetch(`${BASE_API}treatment-rooms/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ name, capacity })
    })
      .then(res => {
        if (!res.ok) throw new Error("Xonani qo‘shib bo‘lmadi");
        return res.json();
      })
      .then(() => {
        loadRooms();
        e.target.reset();
      })
      .catch(err => {
        console.error("❌ Add room error:", err);
        alert("Xonani qo‘shishda xatolik yuz berdi.");
      });
  });

  loadRooms();
});
