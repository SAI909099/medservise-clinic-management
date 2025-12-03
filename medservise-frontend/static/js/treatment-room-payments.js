// medservise-frontend/static/js/treatment-room-payments.js
// compat v7: "Hisob" shows accrued room cost (days * price_per_day) for active patients
(function () {
  'use strict';

  // --- Auth guard ---
  var JWT = localStorage.getItem('token') || null;
  if (!JWT) { alert('Tizimga avval kiring.'); location.href = '/'; return; }

  // --- Dynamic API base ---
  var API = (function () {
    try {
      var base = (window.API_BASE || window.API) || '';
      if (base) return base.replace(/\/+$/, '') + '/api/v1';
      var origin = (location.origin || (location.protocol + '//' + location.host));
      return origin.replace(/\/+$/, '') + '/api/v1';
    } catch (e) { return '/api/v1'; }
  })();

  function extend(target) {
    target = target || {};
    for (var i = 1; i < arguments.length; i++) {
      var src = arguments[i] || {};
      for (var k in src) if (Object.prototype.hasOwnProperty.call(src, k)) target[k] = src[k];
    }
    return target;
  }

  function hdr(json) {
    if (typeof json === 'undefined') json = true;
    var h = { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache', Authorization: 'Bearer ' + JWT };
    var m = (document.cookie || '').match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (m) h['X-CSRFToken'] = decodeURIComponent(m[1]);
    if (json) h['Content-Type'] = 'application/json';
    return h;
  }

  function j(url, opts) {
    opts = opts || {};
    var base = { credentials: 'same-origin', cache: 'no-store', headers: hdr(false) };
    var merged = extend({}, base, opts);
    return fetch(url, merged).then(function (r) {
      if (r.status === 204) return null;
      return r.text().then(function (text) {
        if (!r.ok) throw new Error('HTTP ' + r.status + ': ' + (text || r.statusText));
        try { return text ? JSON.parse(text) : null; } catch (e) { return text; }
      });
    });
  }

  function fmt(n) {
    var x = Number(n || 0);
    var s = Math.round(x).toString();
    return s.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  // ---------- Payments modal (history) ----------
  var paymentsModalId = 'paymentsModal';

  function ensurePaymentsModal() {
    if (document.getElementById(paymentsModalId)) return;
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div class="modal fade" id="'+paymentsModalId+'" tabindex="-1" aria-hidden="true">' +
      '  <div class="modal-dialog modal-lg"><div class="modal-content">' +
      '    <div class="modal-header">' +
      '      <h5 class="modal-title">To‘lovlar</h5>' +
      '      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Yopish"></button>' +
      '    </div>' +
      '    <div class="modal-body">' +
      '      <div class="d-flex justify-content-between align-items-center mb-2">' +
      '        <div>' +
      '          <div class="fw-bold" id="payPatientName">—</div>' +
      '          <div class="small text-muted">ID: <span id="payPatientId">—</span></div>' +
      '        </div>' +
      '        <div class="text-end">' +
      '          <div>Jami hisob: <span id="payTotalBilled">0</span> so’m</div>' +
      '          <div>To‘langan: <span id="payTotalPaid">0</span> so’m</div>' +
      '          <div class="fw-bold">Qoldiq: <span id="payBalance">0</span> so’m</div>' +
      '        </div>' +
      '      </div>' +
      '      <div class="table-responsive">' +
      '        <table class="table table-sm align-middle">' +
      '          <thead><tr><th>#</th><th>Turi</th><th>Xizmat</th><th>Miqdor</th><th>Holat</th><th>Sana</th></tr></thead>' +
      '          <tbody id="payRows"><tr><td colspan="6" class="text-muted">Yuklanmoqda…</td></tr></tbody>' +
      '        </table>' +
      '      </div>' +
      '    </div>' +
      '    <div class="modal-footer">' +
      '      <button class="btn btn-outline-secondary" id="printPaymentsBtn">Chop etish</button>' +
      '      ' +
      '      <button class="btn btn-primary" data-bs-dismiss="modal">Yopish</button>' +
      '    </div>' +
      '  </div></div>' +
      '</div>';
    document.body.appendChild(wrap.firstChild);
    var printBtn = document.getElementById('printPaymentsBtn');
    if (printBtn) printBtn.addEventListener('click', function(){ window.print(); });
  }

  function showModal(id) {
    var el = document.getElementById(id);
    if (!el) return;
    if (window.bootstrap && window.bootstrap.Modal) new window.bootstrap.Modal(el).show();
    else {
      el.classList.add('show'); el.style.display = 'block';
      var bd = document.createElement('div'); bd.className='modal-backdrop fade show'; document.body.appendChild(bd);
      var closes = el.querySelectorAll('[data-bs-dismiss="modal"]');
      for (var i=0;i<closes.length;i++) closes[i].onclick=function(){ el.classList.remove('show'); el.style.display='none'; bd.remove(); };
    }
  }
  function hideModal(id) {
    var el = document.getElementById(id);
    if (!el) return;
    if (window.bootstrap && window.bootstrap.Modal) {
      (window.bootstrap.Modal.getInstance(el) || new window.bootstrap.Modal(el)).hide();
    } else {
      el.classList.remove('show'); el.style.display='none';
      var bd = document.querySelector('.modal-backdrop'); if (bd) bd.remove();
    }
  }

  function fetchPayments(patientId) {
    var attempts = [
      API + '/payments/patient/' + patientId + '/?_=' + Date.now(),
      API + '/patient-payments/?patient_id=' + patientId + '&_=' + Date.now(),
      API + '/wallet/transactions/?patient=' + patientId + '&_=' + Date.now()
    ];
    var idx = 0;
    function tryNext() {
      if (idx >= attempts.length) return Promise.resolve([]);
      var url = attempts[idx++];
      return j(url).then(function (data) {
        var list = Array.isArray(data) ? data :
                   (data && data.results) ? data.results :
                   (data && data.items) ? data.items :
                   (data && data.data) ? data.data : [];
        return list.length ? list : tryNext();
      }).catch(function(){ return tryNext(); });
    }
    return tryNext();
  }

  function normalizePaymentRow(x) {
    var t = (x && (x.type || x.kind || x.entry_type) || '').toLowerCase();
    var amount = Number((x && (x.amount != null ? x.amount : (x.total != null ? x.total : x.value))) || 0);
    var status = (x && (x.status || (x.paid ? 'paid' : 'unpaid'))) || '—';
    var serviceName = (x && (x.service_name || (x.service && x.service.name) || x.description)) || '—';
    var dt = x && (x.created_at || x.timestamp || x.date) || null;
    return { type: t, amount: amount, status: status, serviceName: serviceName, dt: dt };
  }

  function openPaymentsModal(patient) {
    ensurePaymentsModal();
    var nameEl = document.getElementById('payPatientName');
    var idEl   = document.getElementById('payPatientId');
    if (nameEl) nameEl.textContent = patient.name || '—';
    if (idEl)   idEl.textContent   = patient.id   || '—';

    var rowsEl = document.getElementById('payRows');
    if (rowsEl) rowsEl.innerHTML = '<tr><td colspan="6" class="text-muted">Yuklanmoqda…</td></tr>';

    fetchPayments(patient.id).then(function(list){
      var billed=0, paid=0;
      rowsEl.innerHTML = '';
      if (!list || !list.length) {
        rowsEl.innerHTML = '<tr><td colspan="6" class="text-muted">To‘lov tarixi topilmadi.</td></tr>';
      } else {
        var i=1;
        for (var k=0;k<list.length;k++){
          var r = normalizePaymentRow(list[k]);
          if (r.type.indexOf('bill')>=0 || r.type.indexOf('charge')>=0 || r.type.indexOf('debit')>=0) billed += Math.max(0,r.amount);
          if (r.type.indexOf('payment')>=0 || r.type.indexOf('credit')>=0 || (r.status && r.status.toLowerCase()==='paid')) paid += Math.max(0,r.amount);
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td>'+(i++)+'</td>'+
            '<td>'+(r.type||'—')+'</td>'+
            '<td>'+r.serviceName+'</td>'+
            '<td>'+fmt(r.amount)+' so’m</td>'+
            '<td>'+(r.status||'—')+'</td>'+
            '<td>'+(r.dt ? new Date(r.dt).toLocaleString() : '—')+'</td>';
          rowsEl.appendChild(tr);
        }
      }
      var tb = document.getElementById('payTotalBilled');
      var tp = document.getElementById('payTotalPaid');
      var bl = document.getElementById('payBalance');
      if (tb) tb.textContent = fmt(billed);
      if (tp) tp.textContent = fmt(paid);
      if (bl) bl.textContent = fmt(Math.max(0, billed - paid));
      showModal(paymentsModalId);
    });
  }

  // ---------- Page list rendering ----------
  var listEl = document.getElementById('room-list');
  var tabsEl = document.getElementById('payment-filter-tabs');
  var currentFilter = 'all';

  // Two caches:
  //  - Active patients from rooms endpoint
  //  - Discharged & fully-paid room patients
  var cacheActiveItems = [];
  var cacheDischargedPaid = [];

  function badge(status) {
    return status === 'paid' ? 'success' : (status === 'prepaid' ? 'warning text-dark' : 'danger');
  }
  function statusUz(status) {
    return status === 'paid' ? 'To‘langan' : (status === 'prepaid' ? 'Avval To‘langan' : 'To‘lanmagan');
  }

  function escAttr(s){ return String(s||'').replace(/"/g,'&quot;'); }

  function cardHTML(item, idx) {
    var hideAdd = !!item.discharged; // hide Add Payment for discharged-paid
    return '' +
      '<div class="card mb-2 shadow-sm">' +
      '  <div class="card-body d-flex justify-content-between align-items-center">' +
      '    <div>' +
      '      <div class="fw-bold">' + (idx) + '. ' + item.patientName + '</div>' +
      '      <div class="text-muted">Xona: ' + item.roomName + '</div>' +
      '    </div>' +
      '    <div class="text-end">' +
      '      <div>Hisob: <strong>' + fmt(item.billed) + '</strong> so’m</div>' +
      '      <div>To‘langan: <strong class="text-success">' + fmt(item.paid) + '</strong> so’m</div>' +
      '      <div>Qoldiq: <strong class="text-danger">' + fmt(item.balance) + '</strong> so’m</div>' +
      '    </div>' +
      '  </div>' +
      '  <div class="card-footer d-flex gap-2 justify-content-between align-items-center flex-wrap">' +
      '    <span class="badge bg-' + badge(item.status) + '">' + statusUz(item.status) + '</span>' +
      '    <div class="ms-auto d-flex gap-2">' +
           (hideAdd ? '' :
      '      <button type="button" class="btn btn-sm btn-outline-secondary" data-action="add-payment" data-patient="' + (item.patient_id || '') + '" data-patient-name="'+ escAttr(item.patientName) +'">➕ To‘lov qo‘shish</button>') +
      '      <button type="button" class="btn btn-sm btn-outline-primary" data-action="open-payments" data-patient="' + (item.patient_id || '') + '">To‘lovlar</button>' +
      '    </div>' +
      '  </div>' +
      '</div>';
  }

  function render() {
    if (!listEl) return;
    var items = [];

    // Requested behavior:
    //  - "Barchasi" => ONLY active items (no discharged-paid)
    //  - "To‘langan" => ONLY discharged-paid room patients
    //  - "To‘lanmagan" / "Avval To‘langan" => subsets of active
    if (currentFilter === 'all') {
      items = cacheActiveItems.slice();
    } else if (currentFilter === 'paid') {
      items = cacheDischargedPaid.slice();
    } else {
      items = cacheActiveItems.filter(function (x) { return x.status === currentFilter; });
    }

    if (!items.length) { listEl.innerHTML = '<div class="alert alert-secondary">Ma’lumot topilmadi.</div>'; return; }

    var html = '';
    for (var i = 0; i < items.length; i++) html += cardHTML(items[i], i + 1);
    listEl.innerHTML = html;
  }

  // ---------- Helpers for mapping ----------
  function firstNum() {
    for (var i = 0; i < arguments.length; i++) {
      var v = arguments[i];
      if (v !== null && v !== undefined) return Number(v);
    }
    return 0;
  }

  function daysInclusiveSince(iso) {
    if (!iso) return 0;
    var start = new Date(iso);
    var now = new Date();
    // Compare by dates (ignore time) — inclusive
    start.setHours(0,0,0,0);
    now.setHours(0,0,0,0);
    var diff = Math.floor((now - start) / 86400000) + 1;
    return diff < 1 ? 1 : diff;
  }

  // Flatten rooms[] -> patient rows (supports amount_due/amount_paid etc.)
  function flattenRoomsPayload(data) {
    var out = [];
    if (!Array.isArray(data)) return out;

    for (var i=0;i<data.length;i++){
      var room = data[i] || {};
      var roomName  = room.name || room.room_name || '—';
      var roomPrice = Number(room.price || room.price_per_day || 0);
      var patients  = Array.isArray(room.patients) ? room.patients : [];

      for (var k=0;k<patients.length;k++){
        var p = patients[k] || {};

        // Prefer server-calculated accrual if present
        var billed = null;
        if (p.amount_due != null) billed = Number(p.amount_due);
        else if (p.expected != null) billed = Number(p.expected);
        else if (p.total_billed != null) billed = Number(p.total_billed);
        else if (p.total != null) billed = Number(p.total);

        // If API provides days, compute days * price_per_day
        var daysField = Number(p.days || p.stay_days || 0);
        if ((billed == null || billed === 0) && (daysField > 0) && roomPrice > 0) {
          billed = daysField * roomPrice;
        }

        // Last fallback: per-day price (will be overridden by patient-balances step)
        if (billed == null) billed = roomPrice;

        var paid   = firstNum(p.total_paid, p.amount_paid, p.paid, 0);

        var balance  = Math.max(0, billed - paid);
        var status   = (p.status || (balance===0 && paid>0 ? 'paid' : (paid>0 ? 'prepaid' : 'unpaid'))).toLowerCase();
        var fullName = p.patient_name || (((p.first_name||'') + ' ' + (p.last_name||'')).trim()) || '—';

        out.push({
          roomName: roomName,
          patientName: fullName,
          billed: billed,
          paid: paid,
          balance: balance,
          status: status,
          patient_id: p.patient_id || p.id,
          discharged: false
        });
      }
    }
    return out;
  }

  // Build list of discharged & fully-paid room patients (no backend changes)
  function buildDischargedPaid(activeItems) {
    var activeMap = Object.create(null);
    activeItems.forEach(function (x){ if (x.patient_id) activeMap[String(x.patient_id)] = true; });

    return j(API + '/patient-balances/data/?limit=500&_=' + Date.now())
      .then(function (payload) {
        var items = (payload && Array.isArray(payload.items)) ? payload.items : [];
        var extra = [];
        for (var i=0;i<items.length;i++){
          var it = items[i] || {};
          var pid = it.id;
          if (!pid || activeMap[String(pid)]) continue;

          var balance = Number(it.balance != null ? it.balance : (it.balance_total || 0));
          var roomCost = 0;
          if (it.room_cost != null) roomCost = Number(it.room_cost);
          else if (it.room_expected != null) roomCost = Number(it.room_expected);
          else if (it.breakdown && it.breakdown.yotoq != null) roomCost = Number(it.breakdown.yotoq);

          if (!(roomCost > 0)) continue;  // only room stays
          if (!(balance <= 0)) continue;  // only fully paid

          var billed = Number(it.expected_due != null ? it.expected_due : (it.billed_total != null ? it.billed_total : (it.total || 0)));
          var paid   = Number(it.paid_total != null ? it.paid_total : (it.paid || 0));

          extra.push({
            roomName: 'Chiqib ketgan (yotoqxona)',
            patientName: it.name || ((it.first_name||'') + ' ' + (it.last_name||'')).trim() || '—',
            billed: billed,
            paid: paid,
            balance: Math.max(0, billed - paid),
            status: 'paid',
            patient_id: pid,
            discharged: true
          });
        }
        return extra;
      })
      .catch(function(){ return []; });
  }

  // Override active items' billed with real room accrual from patient-balances (room_only)
  function augmentActiveWithRoomAccrual(activeItems) {
    if (!activeItems || !activeItems.length) return Promise.resolve(activeItems);
    return j(API + '/patient-balances/data/?limit=500&_=' + Date.now())
      .then(function (payload) {
        var map = Object.create(null);
        var arr = (payload && payload.items) || [];
        for (var i=0;i<arr.length;i++) map[String(arr[i].id)] = arr[i];

        for (var k=0;k<activeItems.length;k++) {
          var row = activeItems[k];
          var src = map[String(row.patient_id)];
          if (!src) continue;

          var roomCost = null;
          if (src.room_cost != null) roomCost = Number(src.room_cost);
          else if (src.room_expected != null) roomCost = Number(src.room_expected);
          else if (src.breakdown && src.breakdown.yotoq != null) roomCost = Number(src.breakdown.yotoq);

          if (roomCost != null && roomCost > 0) {
            row.billed = roomCost; // room-only accrual
            row.balance = Math.max(0, row.billed - row.paid);
            row.status = (row.balance===0 && row.paid>0) ? 'paid' : (row.paid>0 ? 'prepaid' : 'unpaid');
          }
        }
        return activeItems;
      })
      .catch(function(){ return activeItems; });
  }

  function loadData() {
    var listEl = document.getElementById('room-list');
    if (!listEl) return;
    listEl.innerHTML = '<div class="text-muted">Yuklanmoqda…</div>';

    j(API + '/treatment-room-payments/?_=' + Date.now())
      .then(function (data) {
        var items = [];
        // Shape: [{ id, name, price, patients: [...] }]
        if (Array.isArray(data) && data.length && data[0] && data[0].patients) {
          items = flattenRoomsPayload(data);
          return items;
        }

        // Shape: flat array of rows
        if (Array.isArray(data)) {
          items = data.map(function(x){
            var patient = x.patient || {};
            var full = ((patient.first_name||'') + ' ' + (patient.last_name||'')).trim() || (x.patient_name || '—');

            // Try server accrual first
            var billed = null;
            if (x.amount_due != null) billed = Number(x.amount_due);
            else if (x.expected != null) billed = Number(x.expected);
            else if (x.total_billed != null) billed = Number(x.total_billed);
            else if (x.total != null) billed = Number(x.total);

            var roomPrice = Number((x.room && x.room.price_per_day) || x.price || 0);

            // If we have registration dates, compute days * price_per_day
            var days = 0;
            if (x.assigned_at) days = daysInclusiveSince(x.assigned_at);
            else if (x.admitted_at) days = daysInclusiveSince(x.admitted_at);
            else if (x.created_at) days = daysInclusiveSince(x.created_at);
            if ((billed == null || billed === 0) && days > 0 && roomPrice > 0) {
              billed = days * roomPrice;
            }
            if (billed == null) billed = roomPrice;

            var paid   = firstNum(x.total_paid, x.amount_paid, x.paid, 0);
            var balance= Math.max(0, billed - paid);
            var status = (x.status || (balance===0 && paid>0 ? 'paid' : (paid>0 ? 'prepaid' : 'unpaid'))).toLowerCase();

            return {
              roomName: (x.room && x.room.name) || x.room_name || '—',
              patientName: full,
              billed: billed,
              paid: paid,
              balance: balance,
              status: status,
              patient_id: patient.id || x.patient_id || x.id,
              discharged: false
            };
          });
          return items;
        }

        // Fallback legacy: /treatment-registrations/ (we have assigned_at here — compute days)
        return j(API + '/treatment-registrations/?_=' + Date.now()).then(function (regs) {
          regs = Array.isArray(regs) ? regs : (regs && regs.results) || [];
          return regs.map(function (r) {
            var p = r.patient || {};
            var roomPrice = Number((r.room && r.room.price_per_day) || 0);
            var startISO = r.assigned_at || r.admitted_at || r.created_at;
            var days = startISO ? daysInclusiveSince(startISO) : 1;
            var billed = (roomPrice > 0 ? days * roomPrice : roomPrice);
            var paid   = Number(r.total_paid || 0);
            var balance= Math.max(0, billed - paid);
            var status = balance === 0 && paid > 0 ? 'paid' : (paid > 0 ? 'prepaid' : 'unpaid');

            return {
              roomName: (r.room && r.room.name) || '—',
              patientName: ((p.first_name||'') + ' ' + (p.last_name||'')).trim() || '—',
              billed: billed,
              paid: paid,
              balance: balance,
              status: status,
              patient_id: p.id,
              discharged: false
            };
          });
        });
      })
      .then(function (activeItems) {
        // Override billed with real room accrual from patient-balances (room-only)
        return augmentActiveWithRoomAccrual(activeItems || []);
      })
      .then(function (activeWithAccrual) {
        cacheActiveItems = activeWithAccrual || [];
        return buildDischargedPaid(cacheActiveItems);
      })
      .then(function (dischargedPaid) {
        cacheDischargedPaid = dischargedPaid || [];
        render();
      })
      .catch(function (e) {
        console.error('[trp] load error', e);
        listEl.innerHTML = '<div class="alert alert-danger">Ma’lumotni yuklashda xatolik.</div>';
      });
  }

  // --- Filters ---
  if (tabsEl) {
    tabsEl.addEventListener('click', function (ev) {
      var a = ev.target.closest ? ev.target.closest('a[data-filter]') : null;
      if (!a) return;
      ev.preventDefault();
      var tabs = tabsEl.querySelectorAll('a[data-filter]');
      for (var i = 0; i < tabs.length; i++) tabs[i].classList.remove('active');
      a.classList.add('active');
      currentFilter = a.getAttribute('data-filter') || 'all';
      render();
    });
  }

  // --- Helpers for Add Payment + Receipt ---
  function getProcessedBy() {
    return j(API + '/user-profile/').then(function (u) {
      return (u && (u.full_name || u.email)) || 'System';
    }).catch(function(){ return 'System'; });
  }

  function openReceiptPopup(paymentData) {
    var url = new URL('/static/treatment_room_receipt_popup/receipt.html', window.location.origin);
    url.searchParams.set('payment_id', paymentData.id);
    url.searchParams.set('token', encodeURIComponent(localStorage.getItem('token') || ''));
    url.searchParams.set('patient_name', "'" + decodeURIComponent(paymentData.patient_name || 'Unknown') + "'");
    url.searchParams.set('amount', paymentData.amount);
    url.searchParams.set('status', paymentData.status);
    url.searchParams.set('payment_method', paymentData.payment_method);
    url.searchParams.set('notes', paymentData.notes || '');
    url.searchParams.set('date', paymentData.date_str || '');
    url.searchParams.set('processed_by', paymentData.processed_by || 'System');

    var w = window.open(url, '_blank', 'width=420,height=640');
    if (!w) alert('❌ Popup bloklangan. Iltimos, popupga ruxsat bering.');
    else w.focus();
  }

  // --- Click handlers (payments history & add payment) ---
  document.addEventListener('click', function (ev) {
    var btn = ev.target && ev.target.closest ? ev.target.closest('button[data-action]') : null;
    if (!btn) return;
    var action = btn.getAttribute('data-action');

    if (action === 'open-payments') {
      var pid = btn.getAttribute('data-patient');
      if (!pid) return;
      j(API + '/patients/' + pid + '/').then(function (p) {
        openPaymentsModal({ id: pid, name: ((p && p.first_name)||'') + ' ' + ((p && p.last_name)||'') });
      }).catch(function () {
        openPaymentsModal({ id: pid, name: '—' });
      });
    }

    if (action === 'add-payment') {
      var pid2 = btn.getAttribute('data-patient');
      var pname = btn.getAttribute('data-patient-name') || '—';
      var idEl = document.getElementById('apmPatientId');
      var nmEl = document.getElementById('apmPatientName');
      if (idEl) idEl.value = pid2 || '';
      if (nmEl) nmEl.value = pname;
      showModal('addPaymentModal');
    }
  });

  // --- Submit Add Payment form ---
  var apForm = document.getElementById('addPaymentForm');
  if (apForm) {
    apForm.addEventListener('submit', function (e) {
      e.preventDefault();

      var pid = document.getElementById('apmPatientId').value;
      var pname = document.getElementById('apmPatientName').value || 'Unknown';
      var amount = parseFloat(document.getElementById('apmAmount').value);
      var status = document.getElementById('apmStatus').value;
      var method = document.getElementById('apmMethod').value;
      var notes  = document.getElementById('apmNotes').value;

      if (!pid || !(amount > 0)) {
        alert("Iltimos, to‘g‘ri ma'lumot kiriting.");
        return;
      }

      var submitBtn = document.getElementById('apmSubmit');
      if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Saqlanmoqda…'; }

      j(API + '/treatment-room-payments/', {
        method: 'POST',
        headers: hdr(true),
        body: JSON.stringify({
          patient: pid,
          amount: amount,
          status: status,
          payment_method: method,
          notes: notes,
          transaction_type: 'treatment'
        })
      }).then(function (data) {
        var when = new Date(data.date || new Date()).toLocaleString('uz-UZ', {
          timeZone: 'Asia/Tashkent', year: 'numeric', month: '2-digit', day: '2-digit',
          hour: '2-digit', minute: '2-digit'
        });
        return getProcessedBy().then(function (who) {
          hideModal('addPaymentModal');
          openReceiptPopup({
            id: data.id,
            patient_name: pname,
            amount: amount,
            status: status,
            payment_method: method,
            notes: notes,
            date_str: when,
            processed_by: who
          });
          alert('✅ To‘lov muvaffaqiyatli qo‘shildi');
          loadData();
        });
      }).catch(function (err) {
        console.error('❌ To‘lovni saqlashda xatolik', err);
        alert('❌ To‘lovni qo‘shishda xatolik yuz berdi.');
      }).finally(function () {
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '💾 Saqlash'; }
      });
    });
  }

  // --- Init ---
  loadData();
})();
