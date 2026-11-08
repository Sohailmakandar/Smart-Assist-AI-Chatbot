(function () {
  const messagesEl = document.getElementById("chatMessages");
  const inputEl = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const lpBar = document.getElementById("lpBar");
  const lpIntent = document.getElementById("lpIntent");

  const identityBar = document.getElementById("identityBar");
  const identityChip = document.getElementById("identityChip");
  const idName = document.getElementById("idName");
  const idEmail = document.getElementById("idEmail");
  const idSubmit = document.getElementById("idSubmit");
  const idError = document.getElementById("idError");
  const idWhoName = document.getElementById("idWhoName");
  const idSwitch = document.getElementById("idSwitch");

  const historyList = document.getElementById("historyList");
  const faqList = document.getElementById("faqList");
  const faqFilter = document.getElementById("faqFilter");

  let currentUser = SmartAssistSession.get();
  let livePreviewTimer = null;

  // -------------------------------------------------------------------
  // Identity / sign-in
  // -------------------------------------------------------------------
  function applySignedInUI() {
    if (currentUser) {
      identityBar.classList.add("hidden");
      identityChip.classList.add("visible");
      idWhoName.textContent = currentUser.name;
      inputEl.disabled = false;
      sendBtn.disabled = false;
      inputEl.placeholder = "Type your support query…";
    } else {
      identityBar.classList.remove("hidden");
      identityChip.classList.remove("visible");
      inputEl.disabled = true;
      sendBtn.disabled = true;
      inputEl.placeholder = "Sign in above to start chatting…";
    }
  }

  idSubmit.addEventListener("click", async () => {
    const name = idName.value.trim();
    const email = idEmail.value.trim();
    idError.style.display = "none";

    if (!name || !email) {
      idError.textContent = "Please enter both your name and email.";
      idError.style.display = "block";
      return;
    }

    try {
      const res = await fetch("/api/users/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email }),
      });
      const data = await res.json();

      if (data.error) {
        idError.textContent = data.error;
        idError.style.display = "block";
        return;
      }

      currentUser = data.user;
      SmartAssistSession.set(currentUser);
      applySignedInUI();
      loadHistory();
      if (window.SA_onUserSignedIn) window.SA_onUserSignedIn(currentUser);
      if (window.SA_refreshNotifs) window.SA_refreshNotifs();
    } catch (err) {
      idError.textContent = "Couldn't reach the server. Is the Flask app running?";
      idError.style.display = "block";
    }
  });

  idSwitch.addEventListener("click", () => {
    currentUser = null;
    SmartAssistSession.clear();
    idName.value = "";
    idEmail.value = "";
    applySignedInUI();
    if (window.SA_onUserSignedOut) window.SA_onUserSignedOut();
  });

  // -------------------------------------------------------------------
  // Tabs
  // -------------------------------------------------------------------
  document.querySelectorAll(".console-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".console-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.tab).classList.add("active");

      if (tab.dataset.tab === "historyTab") loadHistory();
      if (tab.dataset.tab === "faqTab" && !faqList.dataset.loaded) loadFAQ("All");
    });
  });

  // -------------------------------------------------------------------
  // Chat
  // -------------------------------------------------------------------
  function scrollToBottom() { messagesEl.scrollTop = messagesEl.scrollHeight; }

  function addUserMessage(text) {
    const el = document.createElement("div");
    el.className = "msg user";
    el.innerHTML = `
      <div class="msg-icon">🙂</div>
      <div><div class="bubble">${escapeHTML(text)}</div></div>
    `;
    messagesEl.appendChild(el);
    scrollToBottom();
  }

  function addTypingIndicator() {
    const el = document.createElement("div");
    el.className = "msg bot";
    el.id = "typingMsg";
    el.innerHTML = `
      <div class="msg-icon">🤖</div>
      <div class="bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div>
    `;
    messagesEl.appendChild(el);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    const el = document.getElementById("typingMsg");
    if (el) el.remove();
  }

  function addBotMessage(result) {
    const el = document.createElement("div");
    el.className = "msg bot";
    const uClass = urgencyClass(result.urgency);
    const sClass = sentimentClass(result.sentiment);
    const ticketId = result.ticket_id;

    el.innerHTML = `
      <div class="msg-icon">🤖</div>
      <div>
        <div class="bubble">${escapeHTML(result.response)}</div>
        <div class="meta">
          <span class="badge outline">${escapeHTML(result.intent)}</span>
          <span class="badge ${uClass}"><span class="pulse-dot ${uClass === 'critical' || uClass === 'high' ? '' : 'static'}"></span>${result.urgency}</span>
          <span class="badge ${sClass}">${result.sentiment}</span>
          <span class="conf">conf ${(result.confidence * 100).toFixed(1)}%</span>
        </div>
        ${ticketId ? `
        <div class="feedback-row" data-ticket="${ticketId}">
          <button class="fb-btn" data-rating="1" title="Helpful">👍</button>
          <button class="fb-btn" data-rating="-1" title="Not helpful">👎</button>
        </div>` : ""}
      </div>
    `;
    messagesEl.appendChild(el);
    scrollToBottom();

    if (ticketId) {
      el.querySelectorAll(".fb-btn").forEach((btn) => {
        btn.addEventListener("click", () => sendFeedback(ticketId, parseInt(btn.dataset.rating, 10), el));
      });
    }
  }

  async function sendFeedback(ticketId, rating, container) {
    try {
      await fetch(`/api/chat/${ticketId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      });
      container.querySelectorAll(".fb-btn").forEach((b) => {
        b.disabled = true;
        b.classList.remove("active-up", "active-down");
      });
      const target = container.querySelector(`.fb-btn[data-rating="${rating}"]`);
      if (target) target.classList.add(rating === 1 ? "active-up" : "active-down");
    } catch (err) { /* non-critical */ }
  }

  async function sendMessage(text) {
    if (!text.trim() || !currentUser) return;
    addUserMessage(text);
    inputEl.value = "";
    sendBtn.disabled = true;
    resetLivePreview();
    addTypingIndicator();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          user_name: currentUser.name,
          user_id: currentUser.id,
        }),
      });
      const data = await res.json();
      removeTypingIndicator();

      if (data.error) {
        addBotMessage({ response: "Sorry — " + data.error, intent: "Error", urgency: "Normal", sentiment: "Neutral", confidence: 0 });
      } else {
        addBotMessage(data);
      }
    } catch (err) {
      removeTypingIndicator();
      addBotMessage({
        response: "I couldn't reach the server. Please make sure the Flask app is running.",
        intent: "Error", urgency: "High", sentiment: "Neutral", confidence: 0,
      });
    } finally {
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  function resetLivePreview() {
    lpBar.style.width = "0%";
    lpIntent.textContent = "start typing…";
  }

  async function updateLivePreview(text) {
    if (!text || text.trim().length < 3) { resetLivePreview(); return; }
    try {
      const res = await fetch("/api/live-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (data.intent) {
        lpIntent.textContent = `${data.intent} · ${(data.confidence * 100).toFixed(0)}%`;
        lpBar.style.width = `${Math.max(6, data.confidence * 100)}%`;
      } else {
        resetLivePreview();
      }
    } catch (err) { /* live preview is a nice-to-have */ }
  }

  sendBtn.addEventListener("click", () => sendMessage(inputEl.value));
  inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(inputEl.value); });
  inputEl.addEventListener("input", (e) => {
    clearTimeout(livePreviewTimer);
    const val = e.target.value;
    livePreviewTimer = setTimeout(() => updateLivePreview(val), 280);
  });
  document.querySelectorAll(".chip[data-msg]").forEach((chip) => {
    chip.addEventListener("click", () => sendMessage(chip.dataset.msg));
  });

  // -------------------------------------------------------------------
  // My Tickets (history)
  // -------------------------------------------------------------------
  async function loadHistory() {
    if (!currentUser) {
      historyList.innerHTML = `<div class="empty-state">Sign in to see your past conversations here.</div>`;
      return;
    }
    historyList.innerHTML = `<div class="spinner"></div>`;
    try {
      const res = await fetch(`/api/users/${currentUser.id}/history`);
      const data = await res.json();
      if (!data.tickets || data.tickets.length === 0) {
        historyList.innerHTML = `<div class="empty-state">No conversations yet — say hi in the Chat tab!</div>`;
        return;
      }
      historyList.innerHTML = data.tickets.map((t) => `
        <div class="history-item">
          <div class="h-top">
            <span class="badge outline">${escapeHTML(t.intent)}</span>
            <span class="badge ${urgencyClass(t.urgency_level)}">${t.urgency_level}</span>
            <span class="h-time">${timeAgo(t.created_at)}</span>
          </div>
          <div class="h-msg">🙂 ${escapeHTML(t.query_text)}</div>
          <div class="h-resp">🤖 ${escapeHTML(t.response_text)}</div>
        </div>
      `).join("");
    } catch (err) {
      historyList.innerHTML = `<div class="empty-state">Couldn't load your history right now.</div>`;
    }
  }

  // -------------------------------------------------------------------
  // FAQ
  // -------------------------------------------------------------------
  async function loadFAQ(category) {
    faqList.innerHTML = `<div class="spinner"></div>`;
    try {
      const res = await fetch(`/api/faq?category=${encodeURIComponent(category)}`);
      const data = await res.json();
      faqList.dataset.loaded = "1";

      if (!data.faq || data.faq.length === 0) {
        faqList.innerHTML = `<div class="empty-state">No FAQs in this category yet.</div>`;
        return;
      }

      faqList.innerHTML = data.faq.map((item, idx) => `
        <div class="faq-item" data-idx="${idx}">
          <div class="faq-q">
            <span>${escapeHTML(item.question)}</span>
            <span class="chev">▾</span>
          </div>
          <div class="faq-a"><div class="faq-a-inner">${escapeHTML(item.answer)}</div></div>
        </div>
      `).join("");

      faqList.querySelectorAll(".faq-item").forEach((item) => {
        item.querySelector(".faq-q").addEventListener("click", () => item.classList.toggle("open"));
      });
    } catch (err) {
      faqList.innerHTML = `<div class="empty-state">Couldn't load FAQs right now.</div>`;
    }
  }

  faqFilter.querySelectorAll(".chip[data-cat]").forEach((chip) => {
    chip.addEventListener("click", () => {
      faqFilter.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      loadFAQ(chip.dataset.cat);
    });
  });

  // -------------------------------------------------------------------
  // Init
  // -------------------------------------------------------------------
  applySignedInUI();
  if (currentUser) {
    loadHistory();
    if (window.SA_onUserSignedIn) window.SA_onUserSignedIn(currentUser);
  }
})();
