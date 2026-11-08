(function () {
  const CHART_TEXT = "#9aa4c4";
  const CHART_GRID = "rgba(154,164,196,0.12)";

  Chart.defaults.color = CHART_TEXT;
  Chart.defaults.font.family = "'Inter', sans-serif";

  const AGENTS = window.SA_AGENTS || ["Unassigned"];
  const INTENTS = window.SA_INTENTS || [];

  let intentChart, urgencyChart, sentimentChart, volumeChart, adminCategoryChart, adminTrendChart;

  const urgencyColors = { Critical: "#ff5c7a", High: "#ffb454", Normal: "#5b9bff", Low: "#34d399" };
  const sentimentColors = { Positive: "#34d399", Neutral: "#9aa4c4", Negative: "#ff5c7a" };
  const intentPalette = ["#7b6ef6", "#22d3c4", "#5b9bff", "#ffb454", "#ff5c7a"];

  // -------------------------------------------------------------------
  // Sidebar navigation
  // -------------------------------------------------------------------
  const loadedViews = new Set(["viewOverview"]);

  document.querySelectorAll(".sidebar-link").forEach((link) => {
    link.addEventListener("click", () => {
      document.querySelectorAll(".sidebar-link").forEach((l) => l.classList.remove("active"));
      document.querySelectorAll(".admin-main .page-view").forEach((v) => v.classList.remove("active"));
      link.classList.add("active");
      document.getElementById(link.dataset.view).classList.add("active");

      const view = link.dataset.view;
      if (!loadedViews.has(view)) {
        loadedViews.add(view);
        if (view === "viewTickets") loadTickets();
        if (view === "viewUsers") loadUsers();
        if (view === "viewExpenses") loadExpenseOverview();
        if (view === "viewFeedback") loadFeedbackOverview();
        if (view === "viewModel") loadCorrections();
      } else {
        if (view === "viewTickets") loadTickets();
        if (view === "viewUsers") loadUsers();
      }
    });
  });

  // -------------------------------------------------------------------
  // Chart builders
  // -------------------------------------------------------------------
  function buildDoughnut(ctx, labels, data, colors) {
    return new Chart(ctx, {
      type: "doughnut",
      data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }] },
      options: { cutout: "68%", plugins: { legend: { position: "bottom", labels: { boxWidth: 10, padding: 14, font: { size: 11.5 } } } } },
    });
  }
  function buildBar(ctx, labels, data, colors) {
    return new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ data, backgroundColor: colors, borderRadius: 6, maxBarThickness: 46 }] },
      options: { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, grid: { color: CHART_GRID }, ticks: { precision: 0 } } } },
    });
  }
  function buildLine(ctx, labels, data, color) {
    return new Chart(ctx, {
      type: "line",
      data: { labels, datasets: [{ data, borderColor: color, backgroundColor: color + "22", fill: true, tension: 0.35, pointRadius: 3, pointBackgroundColor: color }] },
      options: { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, grid: { color: CHART_GRID }, ticks: { precision: 0 } } } },
    });
  }

  // -------------------------------------------------------------------
  // Overview
  // -------------------------------------------------------------------
  async function loadStats() {
    const res = await fetch("/api/stats");
    const s = await res.json();

    document.getElementById("statTotal").textContent = s.total_chats ?? 0;
    document.getElementById("statEscalated").textContent = s.escalated ?? 0;
    document.getElementById("statOpen").textContent = s.open_tickets ?? 0;
    document.getElementById("statConfidence").textContent = s.avg_confidence ? (s.avg_confidence * 100).toFixed(1) + "%" : "0%";
    document.getElementById("statUsers").textContent = s.total_users ?? 0;
    document.getElementById("statBlocked").textContent = s.blocked_users ?? 0;
    document.getElementById("statHelpful").textContent = (s.feedback && s.feedback.helpful) ?? 0;
    document.getElementById("statNotHelpful").textContent = (s.feedback && s.feedback.not_helpful) ?? 0;
    document.getElementById("statCorrections").textContent = s.correction_count ?? 0;

    const intentLabels = Object.keys(s.intent_distribution || {});
    const intentData = Object.values(s.intent_distribution || {});
    const urgencyOrder = ["Critical", "High", "Normal", "Low"];
    const urgencyLabels = urgencyOrder.filter((u) => (s.urgency_distribution || {})[u] !== undefined);
    const urgencyData = urgencyLabels.map((u) => s.urgency_distribution[u]);
    const sentimentLabels = Object.keys(s.sentiment_distribution || {});
    const sentimentData = Object.values(s.sentiment_distribution || {});
    const volumeLabels = Object.keys(s.volume_trend || {});
    const volumeData = Object.values(s.volume_trend || {});

    if (intentChart) intentChart.destroy();
    if (urgencyChart) urgencyChart.destroy();
    if (sentimentChart) sentimentChart.destroy();
    if (volumeChart) volumeChart.destroy();

    intentChart = buildDoughnut(document.getElementById("intentChart"), intentLabels, intentData, intentLabels.map((_, i) => intentPalette[i % intentPalette.length]));
    urgencyChart = buildBar(document.getElementById("urgencyChart"), urgencyLabels, urgencyData, urgencyLabels.map((u) => urgencyColors[u]));
    sentimentChart = buildDoughnut(document.getElementById("sentimentChart"), sentimentLabels, sentimentData, sentimentLabels.map((s2) => sentimentColors[s2] || "#9aa4c4"));
    volumeChart = buildLine(document.getElementById("volumeChart"), volumeLabels, volumeData, "#22d3c4");
  }

  // -------------------------------------------------------------------
  // Tickets
  // -------------------------------------------------------------------
  async function loadTickets() {
    const body = document.getElementById("ticketsBody");
    body.innerHTML = `<tr class="empty-row"><td colspan="12"><div class="spinner"></div></td></tr>`;

    const params = new URLSearchParams({
      status: document.getElementById("filterStatus").value,
      urgency: document.getElementById("filterUrgency").value,
      intent: document.getElementById("filterIntent").value,
      agent: document.getElementById("filterAgent").value,
      search: document.getElementById("searchInput").value,
    });

    const res = await fetch(`/api/tickets?${params.toString()}`);
    const data = await res.json();

    if (!data.tickets || data.tickets.length === 0) {
      body.innerHTML = `<tr class="empty-row"><td colspan="12">No tickets match these filters.</td></tr>`;
      return;
    }

    const agentOptions = AGENTS.map((a) => `<option value="${a}">${a}</option>`).join("");
    const intentOptions = INTENTS.map((i) => `<option value="${i}">${i}</option>`).join("");

    body.innerHTML = data.tickets.map((t) => `
      <tr>
        <td class="mono">#${t.id}</td>
        <td>${escapeHTML(t.user_name)}</td>
        <td class="query-cell" title="${escapeHTML(t.query_text)}">${escapeHTML(t.query_text)}</td>
        <td><span class="badge outline">${escapeHTML(t.intent)}</span></td>
        <td>
          <select class="correct-select" data-action="correct" data-id="${t.id}">
            <option value="">Correct…</option>
            ${intentOptions.replace(`value="${t.intent}"`, `value="${t.intent}" disabled`)}
          </select>
        </td>
        <td class="mono">${(t.confidence * 100).toFixed(1)}%</td>
        <td><span class="badge ${sentimentClass(t.sentiment)}">${t.sentiment}</span></td>
        <td><span class="badge ${urgencyClass(t.urgency_level)}"><span class="pulse-dot ${['Critical','High'].includes(t.urgency_level) ? '' : 'static'}"></span>${t.urgency_level}</span></td>
        <td>
          <select class="status-select" data-action="status" data-id="${t.id}">
            ${["Open", "Pending", "Resolved"].map((opt) => `<option value="${opt}" ${opt === t.status ? "selected" : ""}>${opt}</option>`).join("")}
          </select>
        </td>
        <td>
          <select class="status-select" data-action="agent" data-id="${t.id}">
            ${agentOptions.replace(`value="${t.assigned_agent || 'Unassigned'}"`, `value="${t.assigned_agent || 'Unassigned'}" selected`)}
          </select>
        </td>
        <td><button class="notes-btn ${t.agent_notes ? 'has-notes' : ''}" data-id="${t.id}" data-notes="${escapeHTML(t.agent_notes || '')}">${t.agent_notes ? "📝 View" : "＋ Add"}</button></td>
        <td class="mono" style="color:var(--text-faint); font-size:12px;">${timeAgo(t.created_at)}</td>
      </tr>
    `).join("");

    document.querySelectorAll('.status-select[data-action="status"]').forEach((sel) => {
      sel.addEventListener("change", async (e) => {
        await fetch(`/api/tickets/${e.target.dataset.id}/status`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: e.target.value }) });
        loadStats();
      });
    });
    document.querySelectorAll('.status-select[data-action="agent"]').forEach((sel) => {
      sel.addEventListener("change", async (e) => {
        await fetch(`/api/tickets/${e.target.dataset.id}/assign`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ agent: e.target.value }) });
      });
    });
    document.querySelectorAll('.correct-select[data-action="correct"]').forEach((sel) => {
      sel.addEventListener("change", async (e) => {
        const corrected = e.target.value;
        if (!corrected) return;
        await fetch(`/api/tickets/${e.target.dataset.id}/correct`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ corrected_intent: corrected, corrected_by: "Admin" }),
        });
        loadTickets();
        loadStats();
      });
    });
    document.querySelectorAll(".notes-btn").forEach((btn) => {
      btn.addEventListener("click", () => openNotesModal(btn.dataset.id, btn.dataset.notes));
    });
  }

  // -------------------------------------------------------------------
  // Notes modal
  // -------------------------------------------------------------------
  const notesModal = document.getElementById("notesModal");
  const notesTextarea = document.getElementById("notesTextarea");
  const notesModalTicket = document.getElementById("notesModalTicket");
  let activeNotesTicketId = null;

  function openNotesModal(id, existingNotes) {
    activeNotesTicketId = id;
    notesModalTicket.textContent = `Ticket #${id}`;
    notesTextarea.value = existingNotes || "";
    notesModal.classList.add("visible");
  }
  function closeNotesModal() { notesModal.classList.remove("visible"); }
  document.getElementById("notesModalClose").addEventListener("click", closeNotesModal);
  document.getElementById("notesCancel").addEventListener("click", closeNotesModal);
  document.getElementById("notesSave").addEventListener("click", async () => {
    if (!activeNotesTicketId) return;
    await fetch(`/api/tickets/${activeNotesTicketId}/notes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ notes: notesTextarea.value }) });
    closeNotesModal();
    loadTickets();
  });
  notesModal.addEventListener("click", (e) => { if (e.target === notesModal) closeNotesModal(); });

  // -------------------------------------------------------------------
  // Users
  // -------------------------------------------------------------------
  function initials(name) { return (name || "?").trim().split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase(); }

  async function loadUsers() {
    const body = document.getElementById("usersBody");
    body.innerHTML = `<tr class="empty-row"><td colspan="9"><div class="spinner"></div></td></tr>`;

    const search = document.getElementById("userSearchInput").value;
    const params = new URLSearchParams(search ? { search } : {});
    const res = await fetch(`/api/admin/users?${params.toString()}`);
    const data = await res.json();

    if (!data.users || data.users.length === 0) {
      body.innerHTML = `<tr class="empty-row"><td colspan="9">No users found.</td></tr>`;
      return;
    }

    body.innerHTML = data.users.map((u) => `
      <tr>
        <td><div class="user-name-cell"><div class="user-avatar">${initials(u.name)}</div>${escapeHTML(u.name)}</div></td>
        <td class="mono" style="font-size:12.5px;">${escapeHTML(u.email)}</td>
        <td>${u.ticket_count || 0}</td>
        <td>${u.escalated_count || 0}</td>
        <td>${u.open_count || 0}</td>
        <td style="color:var(--text-faint); font-size:12px;">${timeAgo(u.last_active)}</td>
        <td>${u.is_blocked ? '<span class="badge critical">Blocked</span>' : '<span class="badge low">Active</span>'}</td>
        <td><button class="view-btn" data-id="${u.id}">View</button></td>
        <td><button class="block-btn ${u.is_blocked ? 'is-blocked' : ''}" data-id="${u.id}" data-blocked="${u.is_blocked ? '1' : '0'}">${u.is_blocked ? 'Unblock' : 'Block'}</button></td>
      </tr>
    `).join("");

    document.querySelectorAll(".view-btn").forEach((btn) => btn.addEventListener("click", () => openUserModal(btn.dataset.id)));
    document.querySelectorAll(".block-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const blocked = btn.dataset.blocked === "1";
        await fetch(`/api/admin/users/${btn.dataset.id}/block`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ blocked: !blocked }) });
        loadUsers();
      });
    });
  }

  const userModal = document.getElementById("userModal");
  async function openUserModal(id) {
    document.getElementById("userModalName").textContent = "Loading…";
    document.getElementById("userModalEmail").textContent = "";
    document.getElementById("userModalTickets").innerHTML = `<div class="spinner"></div>`;
    userModal.classList.add("visible");

    const res = await fetch(`/api/admin/users/${id}`);
    const data = await res.json();
    if (data.error) { document.getElementById("userModalName").textContent = "User not found"; return; }
    const u = data.user;
    document.getElementById("userModalName").textContent = u.name;
    document.getElementById("userModalEmail").textContent = `${u.email} · joined ${timeAgo(u.created_at)}`;

    document.getElementById("userModalTickets").innerHTML = (u.tickets || []).map((t) => `
      <div class="history-item">
        <div class="h-top"><span class="badge outline">${escapeHTML(t.intent)}</span><span class="badge ${urgencyClass(t.urgency_level)}">${t.urgency_level}</span><span class="h-time">${timeAgo(t.created_at)}</span></div>
        <div class="h-msg">${escapeHTML(t.query_text)}</div>
      </div>
    `).join("") || `<div class="empty-state">No tickets from this user yet.</div>`;
  }
  document.getElementById("userModalClose").addEventListener("click", () => userModal.classList.remove("visible"));
  userModal.addEventListener("click", (e) => { if (e.target === userModal) userModal.classList.remove("visible"); });

  // -------------------------------------------------------------------
  // Expenses overview (admin)
  // -------------------------------------------------------------------
  const CAT_PALETTE = ["#7b6ef6","#22d3c4","#5b9bff","#ffb454","#ff5c7a","#34d399","#f472b6","#a78bfa"];

  async function loadExpenseOverview() {
    const res = await fetch("/api/admin/expenses/overview");
    const data = await res.json();

    document.getElementById("expTotalSpent").textContent = `₹${data.total_spent.toLocaleString()}`;
    document.getElementById("expEntryCount").textContent = data.total_entries;

    const catEntries = Object.entries(data.category_totals || {});
    document.getElementById("expTopCategory").textContent = catEntries.length ? catEntries[0][0] : "—";
    document.getElementById("expTopSpender").textContent = (data.top_spenders && data.top_spenders[0]) ? data.top_spenders[0].name : "—";

    const catLabels = catEntries.map((e) => e[0]);
    const catData = catEntries.map((e) => e[1]);
    if (adminCategoryChart) adminCategoryChart.destroy();
    adminCategoryChart = buildDoughnut(document.getElementById("adminCategoryChart"), catLabels, catData, catLabels.map((_, i) => CAT_PALETTE[i % CAT_PALETTE.length]));

    const trendLabels = Object.keys(data.trend_14d || {});
    const trendData = Object.values(data.trend_14d || {});
    if (adminTrendChart) adminTrendChart.destroy();
    adminTrendChart = buildLine(document.getElementById("adminTrendChart"), trendLabels, trendData, "#7b6ef6");

    const spendersList = document.getElementById("topSpendersList");
    spendersList.innerHTML = (data.top_spenders || []).map((s, i) => `
      <div class="expense-row"><div class="e-left"><span class="e-cat-dot" style="background:${CAT_PALETTE[i % CAT_PALETTE.length]};"></span>${escapeHTML(s.name)}</div><span class="e-amount">₹${s.total.toLocaleString()}</span></div>
    `).join("") || `<div class="empty-state">No spending data yet.</div>`;
  }

  // -------------------------------------------------------------------
  // Feedback overview (admin)
  // -------------------------------------------------------------------
  async function loadFeedbackOverview() {
    const res = await fetch("/api/admin/feedback");
    const data = await res.json();
    const stats = data.stats;

    document.getElementById("fbAverage").textContent = stats.average ? stats.average.toFixed(1) : "—";
    document.getElementById("fbCount").textContent = stats.count;
    const five = (stats.distribution && stats.distribution["5"]) || 0;
    document.getElementById("fbFiveStarShare").textContent = stats.count ? `${Math.round((five / stats.count) * 100)}%` : "—";

    const list = document.getElementById("feedbackListAdmin");
    if (!data.feedback || data.feedback.length === 0) {
      list.innerHTML = `<div class="empty-state">No feedback submitted yet.</div>`;
      return;
    }
    list.innerHTML = data.feedback.map((f) => `
      <div class="feedback-list-item">
        <div class="f-top">
          <div><strong>${escapeHTML(f.user_name || "Anonymous")}</strong> <span style="color:var(--text-faint); font-size:11.5px;">${escapeHTML(f.user_email || "")}</span></div>
          <div class="f-stars">${"★".repeat(f.rating)}${"☆".repeat(5 - f.rating)}</div>
        </div>
        ${f.comment ? `<div class="f-comment">${escapeHTML(f.comment)}</div>` : ""}
        <div style="font-size:11px; color:var(--text-faint); margin-top:4px;">${timeAgo(f.created_at)}</div>
      </div>
    `).join("");
  }

  // -------------------------------------------------------------------
  // Model & Corrections
  // -------------------------------------------------------------------
  async function loadCorrections() {
    const res = await fetch("/api/admin/corrections");
    const data = await res.json();
    const list = document.getElementById("correctionsList");

    if (!data.corrections || data.corrections.length === 0) {
      list.innerHTML = `<div class="empty-state">No corrections yet — use the "Correct?" dropdown on a ticket to relabel a misclassified intent.</div>`;
      return;
    }
    list.innerHTML = data.corrections.map((c) => `
      <div class="correction-item">
        <span class="mono" style="color:var(--text-faint);">#${c.chat_id}</span>
        <span class="query-cell" style="max-width:220px;" title="${escapeHTML(c.query_text)}">${escapeHTML(c.query_text)}</span>
        <span class="badge outline">${escapeHTML(c.original_intent)}</span>
        <span class="correction-arrow">→</span>
        <span class="badge low">${escapeHTML(c.corrected_intent)}</span>
        <span style="margin-left:auto; font-size:11.5px; color:var(--text-faint);">${timeAgo(c.created_at)}</span>
      </div>
    `).join("");
  }

  document.getElementById("retrainBtn").addEventListener("click", async () => {
    const btn = document.getElementById("retrainBtn");
    btn.disabled = true;
    btn.textContent = "Retraining…";
    const res = await fetch("/api/admin/retrain", { method: "POST" });
    const data = await res.json();
    btn.disabled = false;
    btn.textContent = "🔁 Retrain model";

    const resultEl = document.getElementById("retrainResult");
    if (data.success) {
      resultEl.textContent = `✅ Retrained on ${data.report.total_samples} samples (${data.report.correction_samples_used} from corrections).`;
      resultEl.style.display = "block";
    }
  });

  // -------------------------------------------------------------------
  // Wiring
  // -------------------------------------------------------------------
  function refreshAll() { loadStats(); }
  document.getElementById("refreshBtn").addEventListener("click", () => { loadStats(); loadTickets(); });
  document.getElementById("searchInput").addEventListener("input", debounce(loadTickets, 300));
  ["filterIntent", "filterUrgency", "filterStatus", "filterAgent"].forEach((id) => {
    document.getElementById(id).addEventListener("change", loadTickets);
  });
  document.getElementById("userSearchInput").addEventListener("input", debounce(loadUsers, 300));

  function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  refreshAll();
  setInterval(loadStats, 15000);
})();
