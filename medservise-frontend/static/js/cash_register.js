// medservise-frontend/static/js/cash_register.js
class CashRegister {
    constructor() {
        // Auto-detect API base (works on IP or same-origin)
        const origin = window.location.origin;
        this.apiBase = `${origin}/api/v1`;

        // Tokens
        this.token = localStorage.getItem("token");
        this.refresh = localStorage.getItem("refresh");

        if (!this.token) {
            alert("Iltimos, avval tizimga kiring");
            window.location.href = "/login.html";
            return;
        }

        // Init
        this.init();
    }

    async init() {
        // Filters
        document.getElementById("days-filter")?.addEventListener("change", (e) => {
            const v = e.target.value;
            this.setRecentListSize(v);            // resize panel based on selection
            this.loadRecentPatients(v);
        });

        // Form hooks
        document.getElementById("cash-form")?.addEventListener("submit", (e) => this.submitPayment(e));
        document.getElementById("transaction_type")?.addEventListener("change", (e) => this.toggleServiceSelect(e.target.value));

        // Load initial data
        await this.loadServices();

        // Initialize recent patients with current select value and proper size
        const sel = document.getElementById("days-filter");
        const initial = sel?.value || "3";
        this.setRecentListSize(initial);
        await this.loadRecentPatients(initial);
    }

    // ---------- helpers ----------
    formatAmount(amount) {
        return Number(amount || 0).toLocaleString("uz-UZ").replace(/,/g, ".");
    }

    formatCurrency(amount) {
        const n = Number(amount || 0);
        return `${n.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ".")} so'm`;
    }

    showErrorAlert(prefix, detail) {
        let msg = prefix || "Xato";
        if (detail) {
            if (typeof detail === "string") msg += `: ${detail}`;
            else if (typeof detail === "object") {
                // DRF error dict -> pretty text
                const lines = [];
                for (const [k, v] of Object.entries(detail)) {
                    const val = Array.isArray(v) ? v.join(", ") : String(v);
                    lines.push(`${k}: ${val}`);
                }
                msg += `:\n${lines.join("\n")}`;
            }
        }
        alert(`❌ ${msg}`);
    }

    // Dynamically adjust visible height of the recent-patients panel
    setRecentListSize(days) {
        const bodyEl = document.getElementById("recent-patients-body");
        const listEl = document.getElementById("patient-list");
        if (!bodyEl || !listEl) return;

        const val = String(days);
        const big = (val === "30" || val === "all");

        // Default (1/3/7): ~3–4 visible items
        // Big (30/all): ~7–8 visible items
        bodyEl.style.maxHeight = big ? "520px" : "300px";
        listEl.style.maxHeight = big ? "440px" : "220px";
        bodyEl.style.overflowY = "auto";
        listEl.style.overflowY = "auto";
    }

    // ---------- API ----------
    async authFetch(url, options = {}) {
        const opts = { ...options };
        opts.headers = opts.headers || {};
        if (!opts.headers["Content-Type"] && !(opts.body instanceof FormData)) {
            opts.headers["Content-Type"] = "application/json";
        }
        opts.headers["Authorization"] = `Bearer ${this.token}`;

        let res;
        try {
            res = await fetch(url, opts);
        } catch (e) {
            console.error("Network error:", e);
            throw new Error("Tarmoq xatosi");
        }

        if (res.status === 401) {
            const newToken = await this.refreshToken();
            if (newToken) {
                opts.headers["Authorization"] = `Bearer ${newToken}`;
                res = await fetch(url, opts);
            } else {
                // refresh failed → logout
                this.logout();
                throw new Error("Sessiya tugagan. Qayta kiring.");
            }
        }
        return res;
    }

    async refreshToken() {
        if (!this.refresh) return null;

        // Try both locations to match your Django routes
        const endpoints = [
            `${this.apiBase}/token/refresh/`,             // /api/v1/token/refresh/  (if you added alias in apps.urls)
            `${window.location.origin}/api/token/refresh/` // /api/token/refresh/    (root.urls)
        ];

        for (const url of endpoints) {
            try {
                const res = await fetch(url, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ refresh: this.refresh })
                });

                // 200 OK → update token
                if (res.ok) {
                    const data = await res.json();
                    if (data?.access) {
                        localStorage.setItem("token", data.access);
                        this.token = data.access;
                        return data.access;
                    }
                } else {
                    // Try to log the body for debugging
                    const txt = await res.text();
                    console.warn("Refresh failed at:", url, res.status, txt);
                }
            } catch (e) {
                console.warn("Refresh error at:", url, e);
            }
        }

        return null;
    }

    logout() {
        localStorage.removeItem("token");
        localStorage.removeItem("refresh");
        window.location.href = "/login.html";
    }

    // ---------- Data loaders ----------
    async loadServices() {
        try {
            const res = await this.authFetch(`${this.apiBase}/services/`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const services = await res.json();

            const serviceButtons = document.getElementById("service-buttons");
            if (!serviceButtons) return;

            serviceButtons.innerHTML = "";
            services.forEach(service => {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "btn btn-outline-primary btn-sm";
                btn.textContent = `${service.name} (${this.formatAmount(service.price)} so'm)`;
                btn.dataset.id = service.id;
                btn.dataset.price = service.price;

                btn.addEventListener("click", () => {
                    btn.classList.toggle("btn-primary");
                    btn.classList.toggle("btn-outline-primary");
                    this.updateAmountFromServices();
                });

                serviceButtons.appendChild(btn);
            });
        } catch (err) {
            console.error("Xizmatlar yuklashda xatolik:", err);
            this.showErrorAlert("Xizmatlar roʻyxatini yuklab bo‘lmadi");
        }
    }

    updateAmountFromServices() {
        const selectedButtons = Array.from(document.querySelectorAll("#service-buttons .btn.btn-primary"));
        const total = selectedButtons.reduce((sum, btn) => sum + parseFloat(btn.dataset.price || 0), 0);
        const amountEl = document.getElementById("amount");
        if (amountEl) amountEl.value = Number(total || 0).toFixed(2);
    }

    toggleServiceSelect(type) {
        const container = document.getElementById("multi-service-container");
        if (container) container.style.display = type === "service" ? "block" : "none";

        // If user switches back to consultation, lock the amount to current balance
        const amountEl = document.getElementById("amount");
        if (amountEl) {
            if (type === "service") {
                // Amount auto-follows selected services
                this.updateAmountFromServices();
            }
            amountEl.readOnly = true; // keep read-only, values come from selection or computed balance
        }
    }

    async loadRecentPatients(days = 3) {
        try {
            // If "all" selected, map to a very large number so backend keeps working as-is.
            let d = String(days);
            if (d === "all") d = "36500";

            const res = await this.authFetch(`${this.apiBase}/recent-patients/?days=${encodeURIComponent(d)}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const patients = await res.json();

            const list = document.getElementById("patient-list");
            if (!list) return;

            list.innerHTML = "";

            patients.forEach(p => {
                if (!p || !p.first_name || !p.last_name || !p.phone) return;

                const info = p.patients_doctor?.user
                    ? `Shifokor: ${p.patients_doctor.user.first_name} ${p.patients_doctor.user.last_name}`
                    : p.patients_service
                        ? `Xizmat: ${p.patients_service.name}`
                        : "Biriktirilmagan";

                const li = document.createElement("li");
                li.className = "list-group-item list-group-item-action";
                li.innerHTML = `<strong>${p.first_name} ${p.last_name}</strong> (${p.phone})<br><small class="text-muted">${info}</small>`;
                li.addEventListener("click", () => this.selectPatient(p.id));
                list.appendChild(li);
            });

        } catch (err) {
            console.error("❌ Bemorlar ro'yxatini yuklashda xatolik:", err);
            this.showErrorAlert("Bemorlar ro‘yxatini yuklashda xatolik", err?.message);
        }
    }

    async selectPatient(patientId) {
        try {
            const res = await this.authFetch(`${this.apiBase}/cash-register/patient/${encodeURIComponent(patientId)}/`);
            const data = await res.json();

            if (!res.ok) {
                this.showErrorAlert("Bemorni yuklashda xatolik", data);
                return;
            }

            const { patient, balance, total_paid } = data.summary || {};
            if (!patient) throw new Error("Bemor ma'lumotlari topilmadi");

            document.getElementById("patient").value = patientId;
            document.getElementById("patient-id-display").textContent = patientId;
            document.getElementById("patient-name").textContent = patient.name || "—";
            document.getElementById("patient-phone").textContent = patient.phone || "—";
            document.getElementById("balance").textContent = `${this.formatAmount(balance || 0)} so'm`;
            document.getElementById("total-paid").textContent = `${this.formatAmount(total_paid || 0)} so'm`;

            document.getElementById("assigned-doctor").textContent = patient.patients_doctor?.user
                ? `${patient.patients_doctor.user.first_name} ${patient.patients_doctor.user.last_name}`
                : "—";

            document.getElementById("assigned-service").textContent = patient.patients_service
                ? `${patient.patients_service.name} (${this.formatAmount(patient.patients_service.price)} so'm)`
                : "—";

            const txType = patient.patients_doctor ? "consultation" : "service";
            const txSel = document.getElementById("transaction_type");
            if (txSel) txSel.value = txType;
            this.toggleServiceSelect(txType);

            const amountField = document.getElementById("amount");
            if (amountField) {
                const fallback = txType === "consultation" ? (balance || 0) : (patient.patients_service?.price || 0);
                amountField.value = parseFloat(fallback).toFixed(2);
                amountField.readOnly = true;
            }

            this.renderTransactions(data.transactions);
        } catch (err) {
            console.error("❌ Bemorni yuklashda xatolik:", err);
            this.showErrorAlert("Bemor tafsilotlarini yuklab bo‘lmadi", err?.message);
        }
    }

    renderTransactions(transactions) {
        const typeMap = {
            consultation: "Konsultatsiya",
            treatment: "Davolash",
            service: "Xizmat",
            room: "Xona",
            other: "Boshqa"
        };

        const methodMap = {
            cash: "Naqd",
            card: "Karta",
            insurance: "Sug‘urta",
            transfer: "Bank"
        };

        const tbody = document.querySelector("#cash-register-table tbody");
        if (!tbody) return;

        tbody.innerHTML = "";
        if (!transactions || transactions.length === 0) {
            tbody.innerHTML = "<tr><td colspan='7'>Hech qanday to‘lovlar topilmadi</td></tr>";
            return;
        }

        transactions.forEach(tx => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${tx.patient_name || "—"}</td>
                <td>${typeMap[tx.transaction_type] || tx.transaction_type || "—"}</td>
                <td>${tx.notes || "-"}</td>
                <td>${this.formatAmount(tx.amount)} so'm</td>
                <td>${methodMap[tx.payment_method] || tx.payment_method || "—"}</td>
                <td>${tx.created_at ? new Date(tx.created_at).toLocaleString() : "—"}</td>
                <td></td>
            `;
            tbody.appendChild(row);
        });
    }

    // ---------- Submit payment ----------
    async submitPayment(event) {
        event.preventDefault();

        const patientEl = document.getElementById("patient");
        const txTypeEl = document.getElementById("transaction_type");
        const amountEl = document.getElementById("amount");
        const methodEl = document.getElementById("payment_method");
        const notesEl = document.getElementById("notes");

        const patientId = parseInt(patientEl?.value || 0, 10);
        const txType = txTypeEl?.value || "";
        const amount = parseFloat(amountEl?.value || "0");
        const method = methodEl?.value || "";
        const notes = notesEl?.value || "";

        if (!patientId) return this.showErrorAlert("Bemor tanlanmagan");
        if (!txType) return this.showErrorAlert("To‘lov turi tanlanmagan");
        if (!method) return this.showErrorAlert("To‘lov usuli tanlanmagan");
        if (!(amount > 0)) return this.showErrorAlert("To‘lov summasi noto‘g‘ri");

        const payload = {
            patient: patientId,
            transaction_type: txType,
            amount: amount,
            payment_method: method,
            notes: notes
        };

        if (txType === "service") {
            const selectedServices = Array.from(document.querySelectorAll("#service-buttons .btn.btn-primary"))
                .map(btn => parseInt(btn.dataset.id, 10))
                .filter(Boolean);
            if (selectedServices.length === 0) {
                return this.showErrorAlert("Kamida bitta xizmat tanlang");
            }
            payload.service_ids = selectedServices;
        }

        try {
            const res = await this.authFetch(`${this.apiBase}/cash-register/`, {
                method: "POST",
                body: JSON.stringify(payload)
            });

            let body;
            try { body = await res.json(); } catch { body = null; }

            if (!res.ok) {
                console.error("❌ To‘lov xatosi payload:", body);
                this.showErrorAlert("To‘lov muvaffaqiyatsiz", body || `HTTP ${res.status}`);
                return;
            }

            alert("✅ To‘lov muvaffiyatli bajarildi!");
            document.getElementById("cash-form")?.reset();

            // Refresh patient panel & transactions
            await this.selectPatient(patientId);

            // Print receipt
            if (body?.id) {
                this.printReceipt(body.id).catch(e => console.warn("Print failed:", e));
            }
        } catch (err) {
            console.error("❌ To‘lov xatosi:", err);
            this.showErrorAlert("To‘lovni yozib bo‘lmadi", err?.message);
        }
    }

    // ---------- Printing ----------
    async printReceipt(id) {
        try {
            const res = await this.authFetch(`${this.apiBase}/cash-register/receipt/${encodeURIComponent(id)}/`);
            let data;
            try { data = await res.json(); } catch { data = null; }
            if (!res.ok || !data) throw new Error(`Chek ma'lumotlarini olishda xatolik (HTTP ${res.status})`);

            const lines = [];
            lines.push("NEURO PULS KLINIKASI");
            lines.push("-----------------------------");
            lines.push(`Chek raqami: ${data.receipt_number}`);
            lines.push(`Sana      : ${data.date}`);
            lines.push(`Bemor     : ${data.patient_name}`);
            lines.push(`Turi      : ${data.transaction_type}`);
            lines.push(`Miqdori   : ${this.formatCurrency(data.amount)}`);
            lines.push(`Usul      : ${data.payment_method}`);
            lines.push(`Qabulchi  : ${data.processed_by}`);
            if (data.notes) lines.push(`Izoh      : ${data.notes}`);
            lines.push("-----------------------------");
            lines.push("Rahmat! Kuningiz yaxshi otsin!");

            const qzReceiptText = lines.join("\n") + "\n\n\n\n\n\n\n\n\n\n";
            const browserReceiptText = lines.join("\n\n").trim();

            // QR-code as base64 (optional)
            let qrImageData = null;
            try {
                const qrContent = `${window.location.origin}/cash-register/receipt/${id}/`;
                const qrDataURL = await QRCode.toDataURL(qrContent); // base64 data URL
                qrImageData = qrDataURL.split(",")[1]; // strip "data:image/png;base64,"
            } catch (qrErr) {
                console.warn("QR Code generation failed:", qrErr);
            }

            // Try QZ Tray, otherwise browser fallback
            if (typeof qz !== "undefined" && qz.websocket) {
                try {
                    await qz.websocket.connect();
                    const config = qz.configs.create("XP-58C");

                    const dataToPrint = [{ type: "raw", format: "plain", data: qzReceiptText }];
                    if (qrImageData) dataToPrint.push({ type: "image", format: "base64", data: qrImageData });

                    await qz.print(config, dataToPrint);
                    console.log("✅ Receipt printed via QZ Tray");
                    await qz.websocket.disconnect();
                    return;
                } catch (qzErr) {
                    console.error("❌ QZ Tray Print Error:", qzErr);
                }
            }

            console.warn("⚠️ QZ Tray not available, using browser print fallback");
            const encodedReceipt = encodeURIComponent(browserReceiptText);
            window.location.href = `/static/print_receipt.html?receipt=${encodedReceipt}`;
        } catch (err) {
            console.error("❌ Print Error:", err);
            this.showErrorAlert("Chekni chop etish muvaffaqiyatsiz", err?.message);
        }
    }
}

const cashRegister = new CashRegister();
