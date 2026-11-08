(function () {
  const lockedEl = document.getElementById("myspaceLocked");
  const contentEl = document.getElementById("myspaceContent");
  if (!contentEl) return; // not on this page

  const CHART_TEXT = "#9aa4c4";
  let categoryChart, timeChart;
  let currentUser = SmartAssistSession.get();

  const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

  function uid() { return currentUser ? currentUser.id : null; }

  // -------------------------------------------------------------------
  // Lock / unlock
  // -------------------------------------------------------------------
  function applyLockState() {
    if (currentUser) {
      lockedEl.style.display = "none";
      contentEl.style.display = "block";
    } else {
      lockedEl.style.display = "block";
      contentEl.style.display = "none";
    }
  }

  window.SA_onUserSignedIn = function (user) {
    currentUser = user;
    applyLockState();
    loadProfile();
    loadExpenses();
    loadIncidents();
    loadMsNotifications();
  };
  window.SA_onUserSignedOut = function () {
    currentUser = null;
    applyLockState();
  };

  // -------------------------------------------------------------------
  // Page tabs (Profile / Expenses / Incidents / Feedback / Notifications)
  // -------------------------------------------------------------------
  document.querySelectorAll("#myspaceTabs .page-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#myspaceTabs .page-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll("#myspaceContent .page-view").forEach((v) => v.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.view).classList.add("active");
    });
  });

  // Expense sub-tabs
  document.querySelectorAll(".sub-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const parent = tab.closest(".page-view");
      parent.querySelectorAll(".sub-tab").forEach((t) => t.classList.remove("active"));
      parent.querySelectorAll(".sub-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.sub).classList.add("active");
      if (tab.dataset.sub === "subRecycle") loadRecycleBin();
    });
  });

  // -------------------------------------------------------------------
  // Profile
  // -------------------------------------------------------------------
  async function loadProfile() {
    if (!uid()) return;
    const res = await fetch(`/api/users/${uid()}/profile`);
    const data = await res.json();
    if (data.error) return;
    const p = data.profile;

    document.getElementById("profileAvatar").textContent = (p.name || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
    document.getElementById("profileName").textContent = p.name;
    document.getElementById("profileEmail").textContent = p.email;
    document.getElementById("profileNameInput").value = "";
    document.getElementById("profileNameInput").placeholder = `Update name (currently "${p.name}")`;
    document.getElementById("pStatTickets").textContent = p.ticket_count;
    document.getElementById("pStatEscalated").textContent = p.escalated_count;
    document.getElementById("pStatLogins").textContent = p.login_count;
    document.getElementById("pStatExpenses").textContent = p.expense_count;
    document.getElementById("pStatMember").textContent = timeAgo(p.created_at).replace(" ago", "");

    const histRes = await fetch(`/api/users/${uid()}/login-history`);
    const histData = await histRes.json();
    const histList = document.getElementById("loginHistoryList");
    if (!histData.history || histData.history.length === 0) {
      histList.innerHTML = `<div class="empty-state">No login history yet.</div>`;
    } else {
      histList.innerHTML = histData.history.map((h) => `
        <div class="login-history-item">🔐 Signed in ${timeAgo(h.login_at)}</div>
      `).join("");
    }
  }

  document.getElementById("profileNameSave").addEventListener("click", async () => {
    const name = document.getElementById("profileNameInput").value.trim();
    if (!name || !uid()) return;
    await fetch(`/api/users/${uid()}/profile`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    currentUser.name = name;
    SmartAssistSession.set(currentUser);
    loadProfile();
  });

  // -------------------------------------------------------------------
  // Expenses: Track & Analyze
  // -------------------------------------------------------------------
  function buildDoughnut(ctx, labels, data, colors) {
    return new Chart(ctx, {
      type: "doughnut",
      data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }] },
      options: { cutout: "62%", plugins: { legend: { position: "bottom", labels: { boxWidth: 9, padding: 10, font: { size: 10.5 }, color: CHART_TEXT } } } },
    });
  }
  function buildBar(ctx, labels, data, color) {
    return new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ data, backgroundColor: color, borderRadius: 6, maxBarThickness: 32 }] },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: CHART_TEXT, font: { size: 10 } } },
          y: { beginAtZero: true, ticks: { color: CHART_TEXT, precision: 0 } },
        },
      },
    });
  }

  const CAT_PALETTE = ["#7b6ef6","#22d3c4","#5b9bff","#ffb454","#ff5c7a","#34d399","#f472b6","#a78bfa"];

  async function loadExpenses() {
    if (!uid()) return;
    const res = await fetch(`/api/expenses?user_id=${uid()}`);
    const data = await res.json();
    const s = data.summary;

    document.getElementById("expSummaryRow").innerHTML = `
      <div class="mini-stat"><div class="n">₹${s.total_today.toLocaleString()}</div><div class="l">Today</div></div>
      <div class="mini-stat"><div class="n">₹${s.total_week.toLocaleString()}</div><div class="l">This week</div></div>
      <div class="mini-stat"><div class="n">₹${s.total_month.toLocaleString()}</div><div class="l">This month</div></div>
      <div class="mini-stat"><div class="n">${s.entry_count}</div><div class="l">Total entries</div></div>
    `;

    const catLabels = Object.keys(s.category_totals);
    const catData = Object.values(s.category_totals);
    const catColors = catLabels.map((_, i) => CAT_PALETTE[i % CAT_PALETTE.length]);

    const timeLabels = Object.keys(s.time_bucket_totals);
    const timeData = Object.values(s.time_bucket_totals);

    if (categoryChart) categoryChart.destroy();
    if (timeChart) timeChart.destroy();
    categoryChart = catLabels.length
      ? buildDoughnut(document.getElementById("expCategoryChart"), catLabels, catData, catColors)
      : null;
    timeChart = buildBar(document.getElementById("expTimeChart"), timeLabels.map(l => l.split(" ")[0]), timeData, "#22d3c4");

    document.getElementById("expTips").innerHTML = (data.recommendations || []).map((tip) => `
      <div class="tip-card"><span class="tip-icon">💡</span><span>${escapeHTML(tip)}</span></div>
    `).join("");

    const expList = document.getElementById("expList");
    if (!data.expenses || data.expenses.length === 0) {
      expList.innerHTML = `<div class="empty-state">No expenses logged yet.</div>`;
    } else {
      expList.innerHTML = data.expenses.map((e) => `
        <div class="expense-row">
          <div class="e-left">
            <span class="e-cat-dot"></span>
            <div>
              <div>${escapeHTML(e.category)}${e.note ? " · " + escapeHTML(e.note) : ""}</div>
              <div style="font-size:11px; color:var(--text-faint);">${timeAgo(e.spent_at)}</div>
            </div>
          </div>
          <div>
            <span class="e-amount">₹${Number(e.amount).toLocaleString()}</span>
            <button class="e-del" data-id="${e.id}" title="Move to Recycle Bin">🗑</button>
          </div>
        </div>
      `).join("");

      expList.querySelectorAll(".e-del").forEach((btn) => {
        btn.addEventListener("click", async () => {
          await fetch(`/api/expenses/${btn.dataset.id}?user_id=${uid()}`, { method: "DELETE" });
          loadExpenses();
        });
      });
    }
  }

  document.getElementById("expSubmit").addEventListener("click", async () => {
    const category = document.getElementById("expCategory").value;
    const amount = document.getElementById("expAmount").value;
    const note = document.getElementById("expNote").value;
    if (!uid() || !amount || parseFloat(amount) <= 0) return;

    const res = await fetch("/api/expenses", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid(), category, amount: parseFloat(amount), note }),
    });
    const data = await res.json();
    if (data.error) return;

    const banner = document.getElementById("expInsight");
    banner.textContent = "✅ " + data.insight;
    banner.classList.add("visible");
    setTimeout(() => banner.classList.remove("visible"), 6000);

    document.getElementById("expAmount").value = "";
    document.getElementById("expNote").value = "";
    loadExpenses();
    if (window.SA_refreshNotifs) window.SA_refreshNotifs();
  });

  // -------------------------------------------------------------------
  // Expenses: Recycle Bin
  // -------------------------------------------------------------------
  async function loadRecycleBin() {
    if (!uid()) return;
    const list = document.getElementById("recycleList");
    list.innerHTML = `<div class="spinner"></div>`;
    const res = await fetch(`/api/expenses/recycle-bin?user_id=${uid()}`);
    const data = await res.json();

    if (!data.expenses || data.expenses.length === 0) {
      list.innerHTML = `<div class="empty-state">Recycle Bin is empty.</div>`;
      return;
    }

    list.innerHTML = data.expenses.map((e) => `
      <div class="recycle-item">
        <div>
          <div>${escapeHTML(e.category)} · ₹${Number(e.amount).toLocaleString()}${e.note ? " · " + escapeHTML(e.note) : ""}</div>
          <div style="font-size:11px; color:var(--text-faint);">Deleted ${timeAgo(e.deleted_at)}</div>
        </div>
        <button class="r-restore" data-id="${e.id}">↺ Restore</button>
      </div>
    `).join("");

    list.querySelectorAll(".r-restore").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/expenses/${btn.dataset.id}/restore`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: uid() }),
        });
        loadRecycleBin();
        loadExpenses();
      });
    });
  }

  // -------------------------------------------------------------------
  // Expenses: Invoice
  // -------------------------------------------------------------------
  const invMonthSel = document.getElementById("invMonth");
  MONTHS.forEach((m, i) => {
    const opt = document.createElement("option");
    opt.value = i + 1; opt.textContent = m;
    invMonthSel.appendChild(opt);
  });
  const now = new Date();
  invMonthSel.value = now.getMonth() + 1;
  document.getElementById("invYear").value = now.getFullYear();

  document.getElementById("invPeriod").addEventListener("change", (e) => {
    invMonthSel.style.display = e.target.value === "monthly" ? "inline-block" : "none";
  });

  document.getElementById("invGenerate").addEventListener("click", async () => {
    if (!uid()) return;
    const period = document.getElementById("invPeriod").value;
    const year = document.getElementById("invYear").value;
    const month = invMonthSel.value;

    const params = new URLSearchParams({ user_id: uid(), period, year });
    if (period === "monthly") params.set("month", month);

    const res = await fetch(`/api/expenses/invoice?${params.toString()}`);
    const data = await res.json();
    if (data.error) return;
    renderInvoice(data.invoice);
  });

  function renderInvoice(inv) {
    const rowsHTML = inv.line_items.map((li) => `
      <tr>
        <td>${new Date(li.spent_at.replace(" ", "T")).toLocaleString()}</td>
        <td>${escapeHTML(li.category)}</td>
        <td>${escapeHTML(li.note || "—")}</td>
        <td style="text-align:right;">₹${Number(li.amount).toLocaleString()}</td>
      </tr>
    `).join("") || `<tr><td colspan="4" style="text-align:center; color:#8991ac;">No expenses in this period.</td></tr>`;

    document.getElementById("invoiceOutput").innerHTML = `
      <div class="invoice-paper" id="invoicePaper">
        <div class="inv-head">
          <div>
            <div class="inv-brand">SmartAssist AI</div>
            <div style="font-size:12px; color:#565f7e;">Personal Expenditure Statement</div>
          </div>
          <div class="inv-meta">
            <div><strong>${escapeHTML(inv.invoice_number)}</strong></div>
            <div>${escapeHTML(inv.period_label)}</div>
            <div>${escapeHTML(inv.user_name)} · ${escapeHTML(inv.user_email)}</div>
            <div>Generated ${inv.generated_at}</div>
          </div>
        </div>
        <table>
          <thead><tr><th>Date</th><th>Category</th><th>Note</th><th style="text-align:right;">Amount</th></tr></thead>
          <tbody>${rowsHTML}</tbody>
        </table>
        <div class="inv-total-row"><span>Total (${inv.entry_count} entries)</span><span>₹${inv.total.toLocaleString()}</span></div>
      </div>
      <div class="invoice-actions">
        <button class="btn btn-primary" onclick="window.print()">🖨 Print / Save as PDF</button>
      </div>
    `;
  }

  // -------------------------------------------------------------------
  // Incidents
  // -------------------------------------------------------------------
  async function loadIncidents() {
    if (!uid()) return;
    const list = document.getElementById("incidentsList");
    list.innerHTML = `<div class="spinner"></div>`;
    const res = await fetch(`/api/incidents?user_id=${uid()}`);
    const data = await res.json();

    if (!data.incidents || data.incidents.length === 0) {
      list.innerHTML = `<div class="empty-state">No incidents — smooth sailing! 🎉</div>`;
      return;
    }

    list.innerHTML = data.incidents.map((inc) => `
      <div class="incident-card ${inc.urgency_level === 'Critical' ? '' : 'high'}">
        <div class="i-top">
          <span class="badge outline">${escapeHTML(inc.intent)}</span>
          <span class="badge ${urgencyClass(inc.urgency_level)}">${inc.urgency_level}</span>
          <span class="badge outline">${escapeHTML(inc.status)}</span>
          <span style="margin-left:auto; font-size:11px; color:var(--text-faint);">${timeAgo(inc.created_at)}</span>
        </div>
        <div class="i-msg">${escapeHTML(inc.query_text)}</div>
        <div class="incident-updates">
          ${(inc.updates || []).map((u) => `<div class="incident-update-item">💬 ${escapeHTML(u.message)} <span style="color:var(--text-faint);">(${timeAgo(u.created_at)})</span></div>`).join("")}
        </div>
        <div class="incident-update-form">
          <input type="text" placeholder="Add a follow-up note…" data-chat="${inc.id}">
          <button data-chat="${inc.id}">Send</button>
        </div>
      </div>
    `).join("");

    list.querySelectorAll(".incident-update-form button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const input = list.querySelector(`input[data-chat="${btn.dataset.chat}"]`);
        const message = input.value.trim();
        if (!message) return;
        await fetch(`/api/incidents/${btn.dataset.chat}/update`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: uid(), message }),
        });
        loadIncidents();
      });
    });
  }

  // -------------------------------------------------------------------
  // Feedback
  // -------------------------------------------------------------------
  let selectedStars = 0;
  document.querySelectorAll("#starRating span").forEach((star) => {
    star.addEventListener("click", () => {
      selectedStars = parseInt(star.dataset.star, 10);
      document.querySelectorAll("#starRating span").forEach((s) => {
        s.classList.toggle("filled", parseInt(s.dataset.star, 10) <= selectedStars);
      });
    });
  });

  document.getElementById("feedbackSubmit").addEventListener("click", async () => {
    if (!uid() || selectedStars === 0) return;
    const comment = document.getElementById("feedbackComment").value.trim();

    await fetch("/api/feedback", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid(), rating: selectedStars, comment }),
    });

    document.getElementById("feedbackThanks").style.display = "block";
    document.getElementById("feedbackComment").value = "";
    setTimeout(() => { document.getElementById("feedbackThanks").style.display = "none"; }, 4000);
  });

  // -------------------------------------------------------------------
  // Notifications (full list tab)
  // -------------------------------------------------------------------
  async function loadMsNotifications() {
    if (!uid()) return;
    const list = document.getElementById("msNotifList");
    list.innerHTML = `<div class="spinner"></div>`;
    const res = await fetch(`/api/notifications?user_id=${uid()}`);
    const data = await res.json();

    if (!data.notifications || data.notifications.length === 0) {
      list.innerHTML = `<div class="empty-state">No notifications yet.</div>`;
      return;
    }

    const iconFor = { info: "ℹ️", success: "✅", warning: "⚠️", critical: "🚨" };
    list.innerHTML = data.notifications.map((n) => `
      <div class="notif-item ${n.is_read ? "" : "unread"}" data-id="${n.id}" style="border-radius:8px; margin-bottom:6px;">
        <div class="n-title">${iconFor[n.type] || "ℹ️"} ${escapeHTML(n.title)}</div>
        <div class="n-msg">${escapeHTML(n.message)}</div>
        <div class="n-time">${timeAgo(n.created_at)}</div>
      </div>
    `).join("");

    list.querySelectorAll(".notif-item").forEach((el) => {
      el.addEventListener("click", async () => {
        await fetch(`/api/notifications/${el.dataset.id}/read`, { method: "POST" });
        loadMsNotifications();
        if (window.SA_refreshNotifs) window.SA_refreshNotifs();
      });
    });
  }

  document.getElementById("msNotifReadAll").addEventListener("click", async () => {
    if (!uid()) return;
    await fetch("/api/notifications/read-all", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid() }),
    });
    loadMsNotifications();
    if (window.SA_refreshNotifs) window.SA_refreshNotifs();
  });

  // -------------------------------------------------------------------
  // Init (page load with an already-signed-in user)
  // -------------------------------------------------------------------
  applyLockState();
  if (currentUser) {
    loadProfile();
    loadExpenses();
    loadIncidents();
    loadMsNotifications();
  }
})();
