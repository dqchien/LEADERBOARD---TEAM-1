/**
 * app.js
 */

// ─── CONFIG ────────────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";
const WS_URL   = "ws://localhost:8000/ws/leaderboard";

const MY_USER_ID  = "demo_user";
const MY_NAME     = "Bạn";
const TOP_N       = 10;

const SIM_TOTAL       = 2000;
const SIM_BATCH       = 30;
const SIM_DELAY       = 50;
const SIM_USERS       = 200;
const SIM_SCORE_RANGE = [50, 500];    // random 50–500 → điểm lẻ, gần như không trùng

const RENDER_DEBOUNCE = 200;  // ms gom WS message trước khi reorder


// ─── STATE ─────────────────────────────────────────────────────────────────────
let ws = null;
let wsReconnectTimer = null;
let leaderboardData = [];
let renderedOrder   = "";
let renderTimer     = null;

let totalUpdates = 0;
let isSimulating = false;
let simAborted   = false;

let myRank  = null;
let myScore = 0;


// ─── DOM REFS ──────────────────────────────────────────────────────────────────
const lbBody          = document.getElementById("lb-body");
const statTotal       = document.getElementById("stat-total");
const statUpdates     = document.getElementById("stat-updates");
const wsDot           = document.getElementById("ws-dot");
const wsLabel         = document.getElementById("ws-label");
const btnSimulate     = document.getElementById("btn-simulate");
const btnStop         = document.getElementById("btn-stop");
const btnRefresh      = document.getElementById("btn-refresh");
const btnReset        = document.getElementById("btn-reset");
const simProgress     = document.getElementById("sim-progress");
const progressFill    = document.getElementById("progress-fill");
const progressText    = document.getElementById("progress-text");
const pinnedRank      = document.getElementById("pinned-rank");
const pinnedName      = document.getElementById("pinned-name");
const pinnedScore     = document.getElementById("pinned-score");
const toastContainer  = document.getElementById("toast-container");


// ─── INIT ──────────────────────────────────────────────────────────────────────
async function init() {
  await fetchCurrentBackend(); // hiển thị đúng button active ngay khi load
  await fetchLeaderboard();
  connectWebSocket();
}


// ─── WEBSOCKET ─────────────────────────────────────────────────────────────────
function connectWebSocket() {
  clearTimeout(wsReconnectTimer);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setWsStatus("connected");
    showToast("🔗 Kết nối real-time thành công");
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.event === "score_updated") handleScoreUpdate(data);
    } catch (_) {}
  };

  ws.onclose = () => {
    setWsStatus("disconnected");
    wsReconnectTimer = setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => ws.close();
}

function setWsStatus(status) {
  const connected = status === "connected";

  // Dot + label bên phải
  wsDot.className = `ws-dot ${status}`;
  wsLabel.textContent = connected ? "Real-time" : "Đang kết nối lại...";

  // Badge LIVE bên trái — xanh khi kết nối, đỏ + tắt nhấp nháy khi mất
  const liveBadge = document.getElementById("live-badge");
  const liveLabel = document.getElementById("live-label");
  if (liveBadge) liveBadge.classList.toggle("disconnected", !connected);
  if (liveLabel) liveLabel.textContent = connected ? "LIVE" : "OFFLINE";
}


// ─── FETCH LEADERBOARD ─────────────────────────────────────────────────────────
async function fetchLeaderboard() {
  lbBody.innerHTML = `<div class="spinner"></div>`;

  try {
    const res  = await fetch(`${API_BASE}/leaderboard/top?n=${TOP_N}`);
    const data = await res.json();
    leaderboardData = data.leaderboard || [];
    renderLeaderboard(leaderboardData);
    statTotal.textContent = (data.total_users || 0).toLocaleString();
  } catch (_) {
    lbBody.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <div>Không thể kết nối API</div>
        <div style="font-size:12px;margin-top:6px">Kiểm tra server đang chạy chưa</div>
      </div>`;
  }

  await fetchMyRank();
}

async function fetchMyRank() {
  try {
    const res = await fetch(`${API_BASE}/leaderboard/rank/${MY_USER_ID}`);
    if (res.ok) {
      const data = await res.json();
      myRank  = data.rank;
      myScore = data.score;
      updatePinnedBar(myRank, myScore, false);
    }
  } catch (_) {}
}


// ─── RENDER LEADERBOARD (full rebuild – chỉ dùng khi load lần đầu / reset) ────
function renderLeaderboard(entries) {
  renderedOrder = (entries || []).map(e => e.user_id).join(",");

  if (!entries || entries.length === 0) {
    lbBody.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🏆</div>
        <div>Chưa có dữ liệu</div>
        <div style="font-size:12px;margin-top:6px">Nhấn "Giả lập nạp điểm" để bắt đầu</div>
      </div>`;
    return;
  }

  lbBody.innerHTML = entries.map((entry, i) => buildRow(entry, i)).join("");
}

function buildRow(entry, animIndex = 0) {
  const rankClass = entry.rank <= 3 ? `rank-${entry.rank}` : "";
  const rankIcon  = entry.rank === 1 ? "🥇"
                  : entry.rank === 2 ? "🥈"
                  : entry.rank === 3 ? "🥉"
                  : `#${entry.rank}`;

  const initial = (entry.name || entry.user_id || "?")[0].toUpperCase();
  const isMe    = entry.user_id === MY_USER_ID;
  const rowStyle = isMe
    ? `style="background:rgba(108,99,255,0.12);border-left:3px solid var(--accent);"`
    : "";

  return `
    <div class="lb-row" id="row-${entry.user_id}" ${rowStyle}
         style="animation-delay:${animIndex * 40}ms">
      <div class="rank-badge ${rankClass}">${rankIcon}</div>
      <div class="user-info">
        <div class="avatar" style="${avatarGradient(entry.user_id)}">${initial}</div>
        <div>
          <div class="user-name">${escHtml(entry.name || entry.user_id)}${isMe ? " <small style='color:var(--accent)'>← Bạn</small>" : ""}</div>
          <div class="user-id">${escHtml(entry.user_id)}</div>
        </div>
      </div>
      <div class="score-col">
        <div class="score-value" id="score-${entry.user_id}" data-raw="${entry.score}">${Math.round(entry.score).toLocaleString()}</div>
        <div class="score-change" id="change-${entry.user_id}"></div>
      </div>
    </div>`;
}

function avatarGradient(userId) {
  const hash = [...userId].reduce((h, c) => (h * 31 + c.charCodeAt(0)) | 0, 0);
  const h1   = Math.abs(hash) % 360;
  const h2   = (h1 + 60) % 360;
  return `background:linear-gradient(135deg,hsl(${h1},70%,50%),hsl(${h2},70%,40%))`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}


// ─── FLIP ANIMATION REORDER ────────────────────────────────────────────────────
/**
 * Thay thế renderLeaderboard khi chỉ cần đổi thứ tự.
 * Dùng kỹ thuật FLIP: đo vị trí cũ → reorder DOM node (không xóa/tạo lại)
 * → đo vị trí mới → dùng CSS transform animate từ cũ về mới.
 * Kết quả: các hàng trượt lên/xuống mượt mà, không nhấp nháy.
 */
function animateReorder(newEntries) {
  renderedOrder = newEntries.map(e => e.user_id).join(",");

  // ── FIRST: ghi nhớ vị trí hiện tại của từng row ──────────────────────────
  const firstPos = {};
  newEntries.forEach(({ user_id }) => {
    const row = document.getElementById(`row-${user_id}`);
    if (row) firstPos[user_id] = row.getBoundingClientRect().top;
  });

  // ── Fade out + remove các row không còn trong top N ──────────────────────
  const newIds = new Set(newEntries.map(e => e.user_id));
  [...lbBody.children].forEach(child => {
    const uid = child.id?.replace("row-", "");
    if (uid && !newIds.has(uid)) {
      child.style.transition = "opacity 0.25s ease";
      child.style.opacity    = "0";
      setTimeout(() => child.remove(), 260);
    }
  });

  // ── LAST: reorder DOM nodes và cập nhật rank badge ────────────────────────
  // appendChild di chuyển node (không clone) → tự nhiên reorder
  newEntries.forEach((entry) => {
    let row = document.getElementById(`row-${entry.user_id}`);

    if (!row) {
      // User mới lọt vào top N → tạo row rồi fade in
      const tmp = document.createElement("div");
      tmp.innerHTML = buildRow(entry);
      row = tmp.firstElementChild;
      row.style.opacity = "0";
      lbBody.appendChild(row);
      requestAnimationFrame(() => {
        row.style.transition = "opacity 0.3s ease";
        row.style.opacity    = "1";
      });
    } else {
      // Cập nhật rank badge mà không rebuild toàn bộ row
      const badge = row.querySelector(".rank-badge");
      if (badge) {
        badge.className   = `rank-badge ${entry.rank <= 3 ? `rank-${entry.rank}` : ""}`;
        badge.textContent = entry.rank === 1 ? "🥇"
                          : entry.rank === 2 ? "🥈"
                          : entry.rank === 3 ? "🥉"
                          : `#${entry.rank}`;
      }
      lbBody.appendChild(row); // move to new position
    }
  });

  // ── INVERT + PLAY: tính delta, apply transform, rồi animate về 0 ─────────
  newEntries.forEach(({ user_id }) => {
    const row = document.getElementById(`row-${user_id}`);
    if (!row || firstPos[user_id] === undefined) return;

    const lastTop = row.getBoundingClientRect().top;
    const delta   = firstPos[user_id] - lastTop;

    if (Math.abs(delta) < 1) return; // không di chuyển → bỏ qua

    // Đặt về vị trí cũ ngay lập tức (không transition)
    row.style.transition = "none";
    row.style.transform  = `translateY(${delta}px)`;

    // Frame tiếp theo: bỏ transform đi → browser animate về đúng vị trí
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        row.style.transition = "transform 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94)";
        row.style.transform  = "translateY(0)";
      });
    });
  });
}


// ─── HANDLE REAL-TIME UPDATE ──────────────────────────────────────────────────
function handleScoreUpdate(data) {
  const { user_id, new_total_score, rank } = data;

  totalUpdates++;
  statUpdates.textContent = totalUpdates.toLocaleString();

  if (user_id === MY_USER_ID) {
    const oldRank = myRank;
    myRank  = rank;
    myScore = new_total_score;
    updatePinnedBar(rank, new_total_score, oldRank !== null && rank !== oldRank);
  }

  // Cập nhật leaderboardData
  const idx = leaderboardData.findIndex(e => e.user_id === user_id);
  if (idx !== -1) {
    leaderboardData[idx].score = new_total_score;
    flashScoreCell(user_id, new_total_score); // cập nhật điểm ngay
  } else {
    const minScore = leaderboardData.length >= TOP_N
      ? leaderboardData[leaderboardData.length - 1].score
      : -Infinity;
    if (new_total_score > minScore) {
      leaderboardData.push({ user_id, score: new_total_score, name: user_id });
    } else {
      return;
    }
  }

  scheduleRender();
}

// Cập nhật ô điểm + flash animation, không đụng đến thứ tự hàng
function flashScoreCell(user_id, new_total_score) {
  const scoreEl  = document.getElementById(`score-${user_id}`);
  const changeEl = document.getElementById(`change-${user_id}`);
  const rowEl    = document.getElementById(`row-${user_id}`);
  if (!scoreEl) return;

  const oldScore = parseFloat(scoreEl.dataset.raw || "0") || 0;
  const diff     = new_total_score - oldScore;

  scoreEl.dataset.raw = new_total_score;
  scoreEl.textContent = Math.round(new_total_score).toLocaleString();

  if (changeEl && diff > 0) {
    changeEl.textContent = `+${Math.round(diff)}`;
    changeEl.className   = "score-change up show";
    setTimeout(() => changeEl.classList.remove("show"), 1500);
  }

  if (rowEl) {
    rowEl.classList.remove("updated");
    void rowEl.offsetWidth;
    rowEl.classList.add("updated");
  }
}

// Debounce: gom nhiều WS event → 1 lần reorder
function scheduleRender() {
  clearTimeout(renderTimer);
  renderTimer = setTimeout(() => {
    renderTimer = null;

    leaderboardData.sort((a, b) => b.score - a.score);
    leaderboardData = leaderboardData.slice(0, TOP_N);
    leaderboardData.forEach((e, i) => { e.rank = i + 1; });

    const newOrder = leaderboardData.map(e => e.user_id).join(",");
    if (newOrder !== renderedOrder) {
      animateReorder(leaderboardData); // FLIP thay vì rebuild innerHTML
    }
  }, RENDER_DEBOUNCE);
}


// ─── PINNED BAR ────────────────────────────────────────────────────────────────
function updatePinnedBar(rank, score, animate) {
  pinnedScore.textContent = Math.round(score).toLocaleString();
  if (rank !== null) {
    pinnedRank.textContent = `#${rank}`;
    if (animate) {
      pinnedRank.classList.remove("jumped");
      void pinnedRank.offsetWidth;
      pinnedRank.classList.add("jumped");
      setTimeout(() => pinnedRank.classList.remove("jumped"), 500);
    }
  } else {
    pinnedRank.textContent = "--";
  }
}


// ─── SIMULATE ─────────────────────────────────────────────────────────────────
async function startSimulate() {
  if (isSimulating) return;
  isSimulating = true;
  simAborted   = false;
  totalUpdates = 0;

  const rankInterval = setInterval(fetchMyRank, 1000);
  btnSimulate.disabled  = true;
  btnStop.style.display = "inline-flex";
  simProgress.classList.add("visible");
  showToast(`🚀 Bắt đầu giả lập ${SIM_TOTAL.toLocaleString()} lượt nạp điểm...`);

  let sent = 0;
  while (sent < SIM_TOTAL && !simAborted) {
    const batchSize = Math.min(SIM_BATCH, SIM_TOTAL - sent);
    const promises  = [];

    for (let i = 0; i < batchSize; i++) {
      const userId = Math.random() < 1 / (SIM_USERS + 1)
        ? MY_USER_ID
        : `user_${Math.floor(Math.random() * SIM_USERS) + 1}`;
      // Random 50–500, làm lẻ để tránh trùng điểm
      let score = Math.floor(
        Math.random() * (SIM_SCORE_RANGE[1] - SIM_SCORE_RANGE[0]) + SIM_SCORE_RANGE[0]
      );
      if (score % 2 === 0) score += 1;
      promises.push(postScore(userId, score));
    }

    await Promise.allSettled(promises);
    sent += batchSize;

    const pct = (sent / SIM_TOTAL) * 100;
    progressFill.style.width = `${pct}%`;
    progressText.textContent = `${sent.toLocaleString()} / ${SIM_TOTAL.toLocaleString()}`;
    await sleep(SIM_DELAY);
  }

  await fetchLeaderboard();
  showToast(simAborted ? "⏹ Đã dừng giả lập" : "✅ Giả lập hoàn tất!");

  clearInterval(rankInterval);
  await fetchMyRank();

  isSimulating       = false;
  btnSimulate.disabled  = false;
  btnStop.style.display = "none";
  simProgress.classList.remove("visible");
  progressFill.style.width = "0%";
}

function stopSimulate() {
  simAborted = true;
  showToast("⏸ Đang dừng...");
}


// ─── BACKEND SWITCHER ──────────────────────────────────────────────────────────
async function switchBackend(target) {
  try {
    const res = await fetch(`${API_BASE}/leaderboard/switch-backend?target=${target}`, {
      method: "POST",
    });
    if (res.ok) {
      updateBackendUI(target);
      showToast(target === "redis" ? "⚡ Đã chuyển sang Redis" : "🐘 Đã chuyển sang PostgreSQL");
      await fetchLeaderboard(); // reload data từ backend mới
    } else {
      const err = await res.json();
      showToast("❌ " + (err.detail || "Chuyển backend thất bại"));
    }
  } catch (_) {
    showToast("❌ Không thể kết nối server");
  }
}

function updateBackendUI(backend) {
  const btnRedis    = document.getElementById("btn-backend-redis");
  const btnPostgres = document.getElementById("btn-backend-postgres");
  const slider      = document.getElementById("backend-slider");
  const switcher    = slider?.parentElement;
  const statDisplay = document.getElementById("stat-backend-display");

  const isRedis = backend === "redis";

  btnRedis?.classList.toggle("active", isRedis);
  btnPostgres?.classList.toggle("active", !isRedis);
  switcher?.classList.toggle("postgres", !isRedis);

  // Di chuyển slider đến đúng nút active
  if (slider && btnRedis && btnPostgres) {
    const activeBtn = isRedis ? btnRedis : btnPostgres;
    slider.style.width     = `${activeBtn.offsetWidth}px`;
    slider.style.transform = isRedis
      ? "translateX(0)"
      : `translateX(${btnRedis.offsetWidth}px)`;
  }

  // Cập nhật stat card
  if (statDisplay) {
    statDisplay.textContent = isRedis ? "⚡ Redis" : "🐘 Postgres";
    statDisplay.style.color = isRedis ? "var(--accent)" : "#336791";
  }
}

async function fetchCurrentBackend() {
  try {
    const res  = await fetch(`${API_BASE}/leaderboard/current-backend`);
    const data = await res.json();
    updateBackendUI(data.current_backend);
  } catch (_) {}
}


// ─── RESET ────────────────────────────────────────────────────────────────────
async function resetLeaderboard() {
  if (isSimulating) { showToast("⚠️ Dừng giả lập trước khi reset"); return; }
  if (!confirm("Xoá toàn bộ dữ liệu leaderboard?")) return;

  try {
    const res = await fetch(`${API_BASE}/leaderboard/reset`, { method: "DELETE" });
    if (res.ok) {
      leaderboardData = [];
      renderedOrder   = "";
      myRank = null; myScore = 0; totalUpdates = 0;
      statUpdates.textContent = "0";
      statTotal.textContent   = "0";
      updatePinnedBar(null, 0, false);
      renderLeaderboard([]);
      showToast("🗑 Đã xoá toàn bộ dữ liệu");
    } else {
      showToast("❌ Reset thất bại: " + res.status);
    }
  } catch (_) {
    showToast("❌ Không thể kết nối server");
  }
}


// ─── API CALLS ─────────────────────────────────────────────────────────────────
async function postScore(userId, score, name, avatar) {
  const body = { user_id: userId, score };
  if (name)   body.name   = name;
  if (avatar) body.avatar = avatar;
  const res = await fetch(`${API_BASE}/leaderboard/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}


// ─── TOAST ─────────────────────────────────────────────────────────────────────
function showToast(message, duration = 3300) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  toastContainer.appendChild(el);
  setTimeout(() => el.remove(), duration);
}


// ─── UTILS ─────────────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }


// ─── EVENT LISTENERS ───────────────────────────────────────────────────────────
btnSimulate.addEventListener("click", startSimulate);
btnStop.addEventListener("click", stopSimulate);
btnRefresh.addEventListener("click", fetchLeaderboard);
if (btnReset) btnReset.addEventListener("click", resetLeaderboard);


// ─── BOOT ──────────────────────────────────────────────────────────────────────
init();