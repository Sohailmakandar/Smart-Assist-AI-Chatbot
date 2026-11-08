// Shared helpers used across pages.

function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function urgencyClass(level) {
  return { Critical: "critical", High: "high", Normal: "normal", Low: "low" }[level] || "normal";
}

function sentimentClass(label) {
  return { Positive: "positive", Neutral: "neutral", Negative: "negative" }[label] || "neutral";
}

function timeAgo(isoString) {
  if (!isoString) return "";
  const then = new Date(isoString.replace(" ", "T") + "Z");
  const diffMs = Date.now() - then.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ---------------------------------------------------------------------------
// Theme toggle (persisted in localStorage, applied via [data-theme] on <html>)
// ---------------------------------------------------------------------------
(function initTheme() {
  const root = document.documentElement;
  const saved = localStorage.getItem("sa_theme") || "dark";
  root.setAttribute("data-theme", saved);

  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("themeToggle");
    if (!btn) return;
    btn.textContent = saved === "light" ? "☀️" : "🌙";
    btn.addEventListener("click", () => {
      const current = root.getAttribute("data-theme");
      const next = current === "light" ? "dark" : "light";
      root.setAttribute("data-theme", next);
      localStorage.setItem("sa_theme", next);
      btn.textContent = next === "light" ? "☀️" : "🌙";
    });
  });
})();

// ---------------------------------------------------------------------------
// Lightweight local "session" for the signed-in chat user
// ---------------------------------------------------------------------------
const SmartAssistSession = {
  KEY: "sa_user",
  get() {
    try { return JSON.parse(localStorage.getItem(this.KEY) || "null"); }
    catch (e) { return null; }
  },
  set(user) { localStorage.setItem(this.KEY, JSON.stringify(user)); },
  clear() { localStorage.removeItem(this.KEY); },
};

// ---------------------------------------------------------------------------
// Notification bell (nav) — polling based, only present on the chat page
// ---------------------------------------------------------------------------
(function initNotifBell() {
  document.addEventListener("DOMContentLoaded", () => {
    const bell = document.getElementById("notifBell");
    if (!bell) return; // not on this page

    const dropdown = document.getElementById("notifDropdown");
    const list = document.getElementById("notifList");
    const badge = document.getElementById("notifBadge");
    const readAllBtn = document.getElementById("notifReadAll");

    function currentUserId() {
      const u = SmartAssistSession.get();
      return u ? u.id : null;
    }

    async function refreshNotifs() {
      const uid = currentUserId();
      if (!uid) {
        list.innerHTML = `<div class="notif-empty">Sign in to see notifications.</div>`;
        badge.style.display = "none";
        return;
      }
      try {
        const res = await fetch(`/api/notifications?user_id=${uid}`);
        const data = await res.json();
        const items = data.notifications || [];

        if (data.unread_count > 0) {
          badge.textContent = data.unread_count > 9 ? "9+" : data.unread_count;
          badge.style.display = "flex";
        } else {
          badge.style.display = "none";
        }

        if (items.length === 0) {
          list.innerHTML = `<div class="notif-empty">No notifications yet.</div>`;
          return;
        }

        const iconFor = { info: "ℹ️", success: "✅", warning: "⚠️", critical: "🚨" };
        list.innerHTML = items.map((n) => `
          <div class="notif-item ${n.is_read ? "" : "unread"}" data-id="${n.id}">
            <div class="n-title">${iconFor[n.type] || "ℹ️"} ${escapeHTML(n.title)}</div>
            <div class="n-msg">${escapeHTML(n.message)}</div>
            <div class="n-time">${timeAgo(n.created_at)}</div>
          </div>
        `).join("");

        list.querySelectorAll(".notif-item").forEach((el) => {
          el.addEventListener("click", async () => {
            await fetch(`/api/notifications/${el.dataset.id}/read`, { method: "POST" });
            el.classList.remove("unread");
            refreshNotifs();
          });
        });
      } catch (err) { /* silent */ }
    }

    bell.addEventListener("click", (e) => {
      e.stopPropagation();
      dropdown.classList.toggle("visible");
      if (dropdown.classList.contains("visible")) refreshNotifs();
    });
    document.addEventListener("click", (e) => {
      if (!dropdown.contains(e.target) && e.target !== bell) dropdown.classList.remove("visible");
    });
    readAllBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const uid = currentUserId();
      if (!uid) return;
      await fetch("/api/notifications/read-all", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid }),
      });
      refreshNotifs();
    });

    refreshNotifs();
    setInterval(refreshNotifs, 20000);
    window.SA_refreshNotifs = refreshNotifs;
  });
})();
