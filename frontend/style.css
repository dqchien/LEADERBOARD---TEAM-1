/**
 * app.js
 */

// ─── CONFIG ────────────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";
const WS_URL   = "ws://localhost:8000/ws/leaderboard";

const MY_USER_ID  = "demo_user";
const MY_NAME     = "Bạn";
const TOP_N       = 10;
const SHOW_ALL_N  = 200;   // số lượng tối đa khi nhấn "Xem thêm"

const SIM_BATCH       = 30;
const SIM_DELAY       = 50;
const SIM_USERS       = 200;
const SIM_SCORE_RANGE = [50, 500];    // random 50–500 → điểm lẻ, gần như không trùng

const RENDER_DEBOUNCE = 200;  // ms gom WS message trước khi reorder

// ─── NGROK HELPER ──────────────────────────────────────────────────────────────
// Tự động thêm header bỏ qua cảnh báo ngrok cho mọi request
function apiFetch(url, options = {}) {
  return fetch(url, {
    ...options,
    headers: {
      "ngrok-skip-browser-warning": "true",
      ...(options.headers || {}),
    },
  });
}


// ─── PERF STORAGE ──────────────────────────────────────────────────────────────
const PERF_STORAGE_KEY = "lb_perf_v1";

function loadPerfFromStorage() {
  try {
    const saved = JSON.parse(localStorage.getItem(PERF_STORAGE_KEY) || "null");
    if (!saved) return;
    if (saved.redis?.time    != null) { perfRedisTime = saved.redis.time;    perfRedisInfo = saved.redis.info    || ""; }
    if (saved.postgres?.time != null) { perfPgTime    = saved.postgres.time; perfPgInfo    = saved.postgres.info || ""; }
  } catch (_) {}
}

function savePerfToStorage() {
  localStorage.setItem(PERF_STORAGE_KEY, JSON.stringify({
    redis:    { time: perfRedisTime, info: perfRedisInfo },
    postgres: { time: perfPgTime,    info: perfPgInfo    },
  }));
}


// ─── STATE ─────────────────────────────────────────────────────────────────────
let ws = null;
let wsReconnectTimer = null;
let leaderboardData = [];
let renderedOrder   = "";
let renderTimer     = null;

let totalUpdates = { redis: 0, postgres: 0 };   // đếm riêng từng backend
let isSimulating = false;
let simAborted   = false;

let myRank  = null;
let myScore = 0;
let isExpanded    = false;    // đang mở rộng bảng xếp hạng?
let totalPlayers  = 0;        // tổng số người chơi từ API
let isFilterOpen  = false;    // panel lọc đang mở?
let activeGroup   = 10;       // nhóm hạng đang chọn (10, 50, 100, 0=all)
let isFiltering   = false;    // đang có bộ lọc active?
let allData       = [];       // toàn bộ data (fetch khi cần lọc)
let switchingBackend = false;  // đang chuyển backend → bỏ qua WS event cũ

// ── Performance timer ──
let timerStart     = null;     // timestamp bắt đầu
let timerInterval  = null;     // setInterval ID
let perfRedisTime  = null;     // ms — lần chạy Redis gần nhất
let perfRedisInfo  = "";       // "500 updates"
let perfPgTime     = null;     // ms — lần chạy Postgres gần nhất
let perfPgInfo     = "";


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
const simCountInput   = document.getElementById("sim-count");
const lbFooter        = document.getElementById("lb-footer");
const btnShowMore     = document.getElementById("btn-show-more");
const showMoreText    = document.getElementById("show-more-text");
const showMoreIcon    = document.getElementById("show-more-icon");
const filterBody      = document.getElementById("filter-body");
const filterArrow     = document.getElementById("filter-arrow");
const filterBadge     = document.getElementById("filter-badge");
const filterName      = document.getElementById("filter-name");
const filterRank      = document.getElementById("filter-rank");
const filterScoreMin  = document.getElementById("filter-score-min");
const filterScoreMax  = document.getElementById("filter-score-max");
const filterResultCount = document.getElementById("filter-result-count");

// Performance timer DOM refs
const perfRedisTimeEl  = document.getElementById("perf-redis-time");
const perfPgTimeEl     = document.getElementById("perf-postgres-time");
const perfRedisMetaEl  = document.getElementById("perf-redis-meta");
const perfPgMetaEl     = document.getElementById("perf-postgres-meta");
const perfRedisCard    = document.getElementById("perf-redis-card");
const perfPgCard       = document.getElementById("perf-postgres-card");
const perfLive         = document.getElementById("perf-live");
const perfLiveTimer    = document.getElementById("perf-live-timer");
const perfVerdict      = document.getElementById("perf-verdict");


// ─── HELPER: đọc số lượt giả lập từ ô nhập ────────────────────────────────────
function getSimTotal() {
  const val = parseInt(simCountInput.value, 10);
  if (isNaN(val) || val < 1) {
    simCountInput.value = 500;
    return 500;
  }
  if (val > 50000) {
    simCountInput.value = 50000;
    return 50000;
  }
  return val;
}

// Helper: lấy tên backend đang active từ UI
function getCurrentBackend() {
  return document.getElementById("btn-backend-redis")?.classList.contains("active")
    ? "redis" : "postgres";
}


// ─── INIT ──────────────────────────────────────────────────────────────────────
async function init() {
  await fetchCurrentBackend();
  loadPerfFromStorage();     // khôi phục kết quả đo hiệu năng từ phiên trước
  updatePerfDisplay();
  await fetchLeaderboard();
  connectWebSocket();
}


// ─── WEBSOCKET ─────────────────────────────────────────────────────────────────
function connectWebSocket() {
  clearTimeout(wsReconnectTimer);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setWsStatus("connected");
    showToast("🔗 Connect real-time successful");
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
  wsLabel.textContent = connected ? "Real-time" : "Reconnecting...";

  // Badge LIVE bên trái — xanh khi kết nối, đỏ + tắt nhấp nháy khi mất
  const liveBadge = document.getElementById("live-badge");
  const liveLabel = document.getElementById("live-label");
  if (liveBadge) liveBadge.classList.toggle("disconnected", !connected);
  if (liveLabel) liveLabel.textContent = connected ? "LIVE" : "OFFLINE";
}


// ─── PARSE API RESPONSE ───────────────────────────────────────────────────────
// Tìm mảng leaderboard trong response, bất kể format nào
function parseLeaderboardResponse(data) {
  // Nếu response chính là mảng
  if (Array.isArray(data)) {
    return { entries: data, total: data.length };
  }

  // Tìm mảng trong các key phổ biến
  const keys = ["leaderboard", "top", "data", "results", "users", "items", "rows"];
  for (const key of keys) {
    if (data[key] && Array.isArray(data[key])) {
      return {
        entries: data[key],
        total: data.total_users || data.total || data.count || data[key].length,
      };
    }
  }

  // Fallback: tìm BẤT KỲ mảng nào trong response
  for (const key of Object.keys(data)) {
    if (Array.isArray(data[key]) && data[key].length > 0 && data[key][0].user_id) {
      console.log(`[Leaderboard] Found data in key: "${key}"`);
      return {
        entries: data[key],
        total: data.total_users || data.total || data[key].length,
      };
    }
  }

  console.warn("[Leaderboard] Could not find entries in response:", data);
  return { entries: [], total: 0 };
}


// ─── FETCH LEADERBOARD ─────────────────────────────────────────────────────────
async function fetchLeaderboard() {
  lbBody.innerHTML = `<div class="spinner"></div>`;

  try {
    const fetchN = isExpanded ? SHOW_ALL_N : TOP_N;
    const res  = await apiFetch(`${API_BASE}/leaderboard/top?n=${fetchN}`);
    const data = await res.json();
    const parsed = parseLeaderboardResponse(data);

    console.log("[Leaderboard] API response:", data);
    console.log("[Leaderboard] Parsed entries:", parsed.entries.length);

    leaderboardData = parsed.entries;
    totalPlayers = parsed.total;
    renderLeaderboard(leaderboardData);
    statTotal.textContent = totalPlayers.toLocaleString();
    updateShowMoreButton();
  } catch (err) {
    console.error("[Leaderboard] Fetch error:", err);
    lbBody.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <div>Cannot connect to API</div>
        <div style="font-size:12px;margin-top:6px">Check if the server is running</div>
      </div>`;
    lbFooter.style.display = "none";
  }

  await fetchMyRank();
}

async function fetchMyRank() {
  try {
    const res = await apiFetch(`${API_BASE}/leaderboard/rank/${MY_USER_ID}`);
    if (res.ok) {
      const data = await res.json();
      myRank  = data.rank;
      myScore = data.score;
      updatePinnedBar(myRank, myScore, false);
    } else {
      // User chưa tồn tại trong backend này → reset pinned bar
      myRank  = null;
      myScore = 0;
      updatePinnedBar(null, 0, false);
    }
  } catch (_) {
    // Lỗi kết nối → reset pinned bar
    myRank  = null;
    myScore = 0;
    updatePinnedBar(null, 0, false);
  }
}


// ─── RENDER LEADERBOARD (full rebuild – chỉ dùng khi load lần đầu / reset) ────
function renderLeaderboard(entries) {
  renderedOrder = (entries || []).map(e => e.user_id).join(",");

  if (!entries || entries.length === 0) {
    lbBody.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🏆</div>
        <div>No data available</div>
        <div style="font-size:12px;margin-top:6px">Click "Start Simulation" to begin</div>
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
          <div class="user-name">${escHtml(entry.name || entry.user_id)}${isMe ? " <small style='color:var(--accent)'>← You</small>" : ""}</div>
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
function animateReorder(newEntries) {
  renderedOrder = newEntries.map(e => e.user_id).join(",");

  const firstPos = {};
  newEntries.forEach(({ user_id }) => {
    const row = document.getElementById(`row-${user_id}`);
    if (row) firstPos[user_id] = row.getBoundingClientRect().top;
  });

  const newIds = new Set(newEntries.map(e => e.user_id));
  [...lbBody.children].forEach(child => {
    // Xoá empty state, spinner, hoặc bất kỳ element nào không phải lb-row
    if (!child.id || !child.id.startsWith("row-")) {
      child.remove();
      return;
    }
    const uid = child.id.replace("row-", "");
    if (!newIds.has(uid)) {
      child.style.transition = "opacity 0.25s ease";
      child.style.opacity    = "0";
      setTimeout(() => child.remove(), 260);
    }
  });

  newEntries.forEach((entry) => {
    let row = document.getElementById(`row-${entry.user_id}`);

    if (!row) {
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
      const badge = row.querySelector(".rank-badge");
      if (badge) {
        badge.className   = `rank-badge ${entry.rank <= 3 ? `rank-${entry.rank}` : ""}`;
        badge.textContent = entry.rank === 1 ? "🥇"
                          : entry.rank === 2 ? "🥈"
                          : entry.rank === 3 ? "🥉"
                          : `#${entry.rank}`;
      }
      lbBody.appendChild(row);
    }
  });

  newEntries.forEach(({ user_id }) => {
    const row = document.getElementById(`row-${user_id}`);
    if (!row || firstPos[user_id] === undefined) return;

    const lastTop = row.getBoundingClientRect().top;
    const delta   = firstPos[user_id] - lastTop;

    if (Math.abs(delta) < 1) return;

    row.style.transition = "none";
    row.style.transform  = `translateY(${delta}px)`;

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
  // Bỏ qua WS event cũ khi đang chuyển backend
  if (switchingBackend) return;

  const { user_id, new_total_score, rank } = data;

  const backend = getCurrentBackend();
  totalUpdates[backend]++;
  statUpdates.textContent = totalUpdates[backend].toLocaleString();

  // Xoá empty state / spinner ngay khi nhận update đầu tiên
  const emptyEl = lbBody.querySelector(".empty-state, .spinner");
  if (emptyEl) emptyEl.remove();

  if (user_id === MY_USER_ID) {
    const oldRank = myRank;
    myRank  = rank;
    myScore = new_total_score;
    updatePinnedBar(rank, new_total_score, oldRank !== null && rank !== oldRank);
  }

  const idx = leaderboardData.findIndex(e => e.user_id === user_id);
  if (idx !== -1) {
    leaderboardData[idx].score = new_total_score;
    flashScoreCell(user_id, new_total_score);
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
      if (!renderedOrder) {
        // Chuyển từ trạng thái trống (cúp) → có data: full rebuild để xoá empty state
        renderLeaderboard(leaderboardData);
      } else {
        // Đã có data → FLIP animate reorder
        animateReorder(leaderboardData);
      }
    }
  }, RENDER_DEBOUNCE);
}


// ─── SHOW MORE / COLLAPSE ──────────────────────────────────────────────────────
function updateShowMoreButton() {
  if (totalPlayers > TOP_N) {
    lbFooter.style.display = "flex";
    if (isExpanded) {
      showMoreText.textContent = "Collapse";
      showMoreIcon.textContent = "▲";
    } else {
      const remaining = totalPlayers - TOP_N;
      showMoreText.textContent = `View more (${remaining.toLocaleString()} players)`;
      showMoreIcon.textContent = "▼";
    }
  } else {
    lbFooter.style.display = "none";
  }
}

async function toggleShowAll() {
  isExpanded = !isExpanded;
  await fetchLeaderboard();

  // Nếu thu gọn, cuộn lên đầu bảng
  if (!isExpanded) {
    document.querySelector(".lb-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}


// ─── SEARCH & FILTER ──────────────────────────────────────────────────────────
function toggleFilterPanel() {
  isFilterOpen = !isFilterOpen;
  filterBody.style.display = isFilterOpen ? "block" : "none";
  filterArrow.textContent  = isFilterOpen ? "▲" : "▼";
}

function setGroupFilter(n) {
  activeGroup = n;
  document.querySelectorAll(".filter-tag").forEach(btn => {
    btn.classList.toggle("active", parseInt(btn.dataset.group) === n);
  });
}

function countActiveFilters() {
  let count = 0;
  if (filterName.value.trim()) count++;
  if (filterRank.value.trim()) count++;
  if (filterScoreMin.value.trim() || filterScoreMax.value.trim()) count++;
  if (activeGroup !== 10) count++;  // 10 là mặc định
  return count;
}

function updateFilterBadge() {
  const count = countActiveFilters();
  if (count > 0 && isFiltering) {
    filterBadge.textContent     = count;
    filterBadge.style.display   = "inline-flex";
  } else {
    filterBadge.style.display   = "none";
  }
}

async function applyFilters() {
  const nameQuery = filterName.value.trim().toLowerCase();
  const rankQuery = parseInt(filterRank.value, 10);
  const scoreMin  = parseFloat(filterScoreMin.value);
  const scoreMax  = parseFloat(filterScoreMax.value);
  const groupN    = activeGroup || SHOW_ALL_N;

  // Nếu không có bộ lọc nào → về mặc định
  if (!nameQuery && isNaN(rankQuery) && isNaN(scoreMin) && isNaN(scoreMax) && activeGroup === 10) {
    clearFilters();
    return;
  }

  isFiltering = true;
  updateFilterBadge();
  lbBody.innerHTML = `<div class="spinner"></div>`;

  try {
    // Fetch đủ data để lọc
    const fetchN = Math.max(groupN, SHOW_ALL_N);
    const res  = await apiFetch(`${API_BASE}/leaderboard/top?n=${fetchN}`);
    const data = await res.json();
    const parsed = parseLeaderboardResponse(data);

    allData = parsed.entries;
    totalPlayers = parsed.total;
    statTotal.textContent = totalPlayers.toLocaleString();

    // Giới hạn theo nhóm hạng trước
    let filtered = groupN > 0 ? allData.slice(0, groupN) : [...allData];

    // Tìm theo rank cụ thể → nhảy đến rank đó
    if (!isNaN(rankQuery) && rankQuery >= 1) {
      const found = allData.find(e => e.rank === rankQuery);
      if (found) {
        // Hiển thị vùng xung quanh rank (±5)
        const idx = allData.indexOf(found);
        const start = Math.max(0, idx - 5);
        const end   = Math.min(allData.length, idx + 6);
        filtered = allData.slice(start, end);
        // Cập nhật rank cho đúng
        filtered.forEach((e, i) => { e._highlight = e.rank === rankQuery; });
      } else {
        filtered = [];
      }
    }

    // Lọc theo tên / user_id
    if (nameQuery) {
      filtered = filtered.filter(e =>
        (e.name || "").toLowerCase().includes(nameQuery) ||
        (e.user_id || "").toLowerCase().includes(nameQuery)
      );
    }

    // Lọc theo khoảng điểm
    if (!isNaN(scoreMin)) {
      filtered = filtered.filter(e => e.score >= scoreMin);
    }
    if (!isNaN(scoreMax)) {
      filtered = filtered.filter(e => e.score <= scoreMax);
    }

    // Render kết quả
    renderFilteredLeaderboard(filtered, rankQuery);

    // Cập nhật số kết quả
    filterResultCount.textContent = `${filtered.length.toLocaleString()} kết quả`;

    // Ẩn nút "Xem thêm" khi đang filter
    lbFooter.style.display = "none";

    showToast(`🔍 Found ${filtered.length} results`);

  } catch (_) {
    lbBody.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <div>Cannot load data</div>
      </div>`;
  }
}

function renderFilteredLeaderboard(entries, highlightRank) {
  if (!entries || entries.length === 0) {
    lbBody.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <div>No results found</div>
        <div style="font-size:12px;margin-top:6px">Try changing the filters</div>
      </div>`;
    return;
  }

  lbBody.innerHTML = entries.map((entry, i) => {
    const html = buildRow(entry, i);
    // Highlight row nếu match rank search
    if (entry._highlight || entry.rank === highlightRank) {
      return html.replace(
        'class="lb-row"',
        'class="lb-row filter-highlight"'
      );
    }
    return html;
  }).join("");
}

async function clearFilters() {
  // Reset tất cả input
  filterName.value     = "";
  filterRank.value     = "";
  filterScoreMin.value = "";
  filterScoreMax.value = "";
  setGroupFilter(10);

  isFiltering = false;
  filterResultCount.textContent = "";
  updateFilterBadge();

  // Về lại hiển thị mặc định
  isExpanded = false;
  await fetchLeaderboard();
  showToast("✕ Đã xoá bộ lọc");
}

// Cho phép nhấn Enter trong các ô filter để apply
[filterName, filterRank, filterScoreMin, filterScoreMax].forEach(el => {
  if (el) el.addEventListener("keydown", (e) => {
    if (e.key === "Enter") applyFilters();
  });
});


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


// ─── PERFORMANCE TIMER ────────────────────────────────────────────────────────
function formatTime(ms) {
  if (ms === null || ms === undefined) return "--";
  const totalSec = ms / 1000;
  const min = Math.floor(totalSec / 60);
  const sec = Math.floor(totalSec % 60);
  const millis = Math.floor(ms % 1000);
  return `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}.${String(millis).padStart(3, "0")}`;
}

function startTimer() {
  timerStart = performance.now();
  perfLive.style.display = "flex";
  timerInterval = setInterval(() => {
    const elapsed = performance.now() - timerStart;
    perfLiveTimer.textContent = formatTime(elapsed);
  }, 47); // ~21fps — đủ mượt, tiết kiệm CPU
}

function stopTimer(simTotal) {
  clearInterval(timerInterval);
  timerInterval = null;
  const elapsed = performance.now() - timerStart;
  perfLive.style.display = "none";

  // Lưu kết quả theo backend đang dùng
  const info = `${simTotal.toLocaleString()} updates`;
  const backend = getCurrentBackend();

  if (backend === "redis") {
    perfRedisTime = elapsed;
    perfRedisInfo = info;
  } else {
    perfPgTime = elapsed;
    perfPgInfo = info;
  }

  savePerfToStorage();   // lưu ngay để F5 không mất kết quả
  updatePerfDisplay();
}

function updatePerfDisplay() {
  // Redis card
  if (perfRedisTime !== null) {
    perfRedisTimeEl.textContent = formatTime(perfRedisTime);
    perfRedisMetaEl.textContent = perfRedisInfo;
    perfRedisCard.classList.add("has-data");
  } else {
    perfRedisTimeEl.textContent = "--";
    perfRedisMetaEl.textContent = "Not run yet";
  }

  // Postgres card
  if (perfPgTime !== null) {
    perfPgTimeEl.textContent = formatTime(perfPgTime);
    perfPgMetaEl.textContent = perfPgInfo;
    perfPgCard.classList.add("has-data");
  } else {
    perfPgTimeEl.textContent = "--";
    perfPgMetaEl.textContent = "Not run yet";
  }

  // Xoá winner/loser cũ
  perfRedisCard.classList.remove("winner", "loser");
  perfPgCard.classList.remove("winner", "loser");
  perfVerdict.textContent = "";

  // So sánh nếu cả 2 đều có data
  if (perfRedisTime !== null && perfPgTime !== null) {
    const diff = Math.abs(perfRedisTime - perfPgTime);
    const diffSec = (diff / 1000).toFixed(2);
    const ratio = Math.max(perfRedisTime, perfPgTime) / Math.min(perfRedisTime, perfPgTime);

    if (perfRedisTime < perfPgTime) {
      perfRedisCard.classList.add("winner");
      perfPgCard.classList.add("loser");
      perfVerdict.innerHTML = `⚡ Redis is faster <strong>${ratio.toFixed(1)}x</strong> (faster by ${diffSec}s)`;
    } else if (perfPgTime < perfRedisTime) {
      perfPgCard.classList.add("winner");
      perfRedisCard.classList.add("loser");
      perfVerdict.innerHTML = `🐘 PostgreSQL is faster <strong>${ratio.toFixed(1)}x</strong> (faster by ${diffSec}s)`;
    } else {
      perfVerdict.textContent = "🤝 Tie!";
    }
  }
}


// ─── SIMULATE ─────────────────────────────────────────────────────────────────
async function startSimulate() {
  if (isSimulating) return;

  // Xoá empty state ngay lập tức — không đợi WS event mới xoá
  const emptyEl = lbBody.querySelector(".empty-state");
  if (emptyEl) {
    lbBody.innerHTML = "";
    renderedOrder = "";   // đảm bảo lần render đầu tiên dùng full rebuild
  }

  const simTotal = getSimTotal();

  isSimulating = true;
  simAborted   = false;
  totalUpdates[getCurrentBackend()] = 0;
  statUpdates.textContent = "0";

  const rankInterval = setInterval(fetchMyRank, 1000);
  btnSimulate.disabled  = true;
  simCountInput.disabled = true;   // khoá ô nhập khi đang chạy
  btnStop.style.display = "inline-flex";
  simProgress.classList.add("visible");
  progressText.textContent = `0 / ${simTotal.toLocaleString()}`;
  showToast(`🚀 Start simulating ${simTotal.toLocaleString()} updates...`);

  // Bắt đầu đồng hồ đo hiệu năng
  startTimer();

  let sent = 0;
  while (sent < simTotal && !simAborted) {
    const batchSize = Math.min(SIM_BATCH, simTotal - sent);
    const promises  = [];

    for (let i = 0; i < batchSize; i++) {
      const userId = Math.random() < 1 / (SIM_USERS + 1)
        ? MY_USER_ID
        : `user_${Math.floor(Math.random() * SIM_USERS) + 1}`;
      let score = Math.floor(
        Math.random() * (SIM_SCORE_RANGE[1] - SIM_SCORE_RANGE[0]) + SIM_SCORE_RANGE[0]
      );
      if (score % 2 === 0) score += 1;
      promises.push(postScore(userId, score));
    }

    await Promise.allSettled(promises);
    sent += batchSize;

    const pct = (sent / simTotal) * 100;
    progressFill.style.width = `${pct}%`;
    progressText.textContent = `${sent.toLocaleString()} / ${simTotal.toLocaleString()}`;
    await sleep(SIM_DELAY);
  }

  // Dừng đồng hồ đo hiệu năng
  stopTimer(sent);

  // Chờ backend xử lý xong batch cuối
  await sleep(300);

  // Tắt bộ lọc nếu đang active (để hiển thị đầy đủ kết quả)
  if (isFiltering) {
    isFiltering = false;
    updateFilterBadge();
    filterResultCount.textContent = "";
  }

  await fetchLeaderboard();
  showToast(simAborted ? "⏹ Đã dừng giả lập" : "✅ Giả lập hoàn tất!");

  clearInterval(rankInterval);
  await fetchMyRank();

  isSimulating          = false;
  btnSimulate.disabled  = false;
  simCountInput.disabled = false;  // mở khoá ô nhập
  btnStop.style.display = "none";
  simProgress.classList.remove("visible");
  progressFill.style.width = "0%";
}

function stopSimulate() {
  simAborted = true;
  showToast("⏸ Stopping simulation...");
}


// ─── BACKEND SWITCHER ──────────────────────────────────────────────────────────
async function switchBackend(target) {
  if (isSimulating) {
    showToast("⚠️ Stop simulation before switching to the backend.");
    return;
  }

  try {
    const res = await apiFetch(`${API_BASE}/leaderboard/switch-backend?target=${target}`, {
      method: "POST",
    });
    if (res.ok) {
      // Chặn WS event cũ trong khi đang chuyển
      switchingBackend = true;

      updateBackendUI(target);

      // ── Reset toàn bộ UI state cho backend mới ──────────────────────────
      // 1. Số phiên riêng của backend mới
      statUpdates.textContent = (totalUpdates[target] || 0).toLocaleString();

      // 2. Reset pinned bar (demo_user có thể không tồn tại ở backend mới)
      myRank  = null;
      myScore = 0;
      updatePinnedBar(null, 0, false);

      // 3. Reset leaderboard data cũ
      leaderboardData = [];
      renderedOrder   = "";

      // 4. Reset filter state
      isExpanded  = false;
      isFiltering = false;
      updateFilterBadge();
      filterResultCount.textContent = "";

      // 5. Fetch data mới từ backend mới (bao gồm fetchMyRank)
      showToast(target === "redis" ? "⚡ Switched to Redis + Postgres" : "🐘 Switched to PostgreSQL");
      await fetchLeaderboard();

      // Ngắt WS cũ để flush toàn bộ message của backend trước còn trong queue,
      // sau đó kết nối lại — connectWebSocket tự xử lý reconnect timer
      clearTimeout(wsReconnectTimer);
      if (ws) { ws.onclose = null; ws.onerror = null; ws.close(); ws = null; }
      switchingBackend = false;
      connectWebSocket();
    } else {
      const err = await res.json();
      showToast("❌ " + (err.detail || "Failed to switch backend"));
    }
  } catch (_) {
    showToast("❌ Cannot connect to server");
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

  if (slider && btnRedis && btnPostgres) {
    const activeBtn = isRedis ? btnRedis : btnPostgres;
    slider.style.width     = `${activeBtn.offsetWidth}px`;
    slider.style.transform = isRedis
      ? "translateX(0)"
      : `translateX(${btnRedis.offsetWidth}px)`;
  }

  if (statDisplay) {
    statDisplay.textContent = isRedis ? "⚡ Redis + Postgres" : "🐘 Postgres";
    statDisplay.style.color = isRedis ? "var(--accent)" : "#336791";
  }
}

async function fetchCurrentBackend() {
  try {
    const res  = await apiFetch(`${API_BASE}/leaderboard/current-backend`);
    const data = await res.json();
    updateBackendUI(data.current_backend);
  } catch (_) {}
}


// ─── RESET ────────────────────────────────────────────────────────────────────
async function resetLeaderboard() {
  if (isSimulating) { showToast("⚠️ Stop simulation before resetting"); return; }
  if (!confirm("Delete all leaderboard data?")) return;

  try {
    const res = await apiFetch(`${API_BASE}/leaderboard/reset`, { method: "DELETE" });
    if (res.ok) {
      leaderboardData = [];
      renderedOrder   = "";
      myRank = null; myScore = 0; totalUpdates[getCurrentBackend()] = 0;
      isExpanded = false; totalPlayers = 0;
      isFiltering = false; allData = [];
      filterName.value = ""; filterRank.value = "";
      filterScoreMin.value = ""; filterScoreMax.value = "";
      setGroupFilter(10);
      filterResultCount.textContent = "";
      updateFilterBadge();
      statUpdates.textContent = "0";
      statTotal.textContent   = "0";
      lbFooter.style.display  = "none";
      updatePinnedBar(null, 0, false);
      renderLeaderboard([]);

      // Xoá kết quả đo hiệu năng
      perfRedisTime = null; perfRedisInfo = "";
      perfPgTime    = null; perfPgInfo    = "";
      totalUpdates  = { redis: 0, postgres: 0 };
      localStorage.removeItem(PERF_STORAGE_KEY);
      updatePerfDisplay();

      showToast("🗑 Deleted all data");
    } else {
      showToast("❌ Reset failed: " + res.status);
    }
  } catch (_) {
    showToast("❌ Cannot connect to server");
  }
}


// ─── API CALLS ─────────────────────────────────────────────────────────────────
async function postScore(userId, score, name, avatar) {
  const body = { user_id: userId, score };
  if (name)   body.name   = name;
  if (avatar) body.avatar = avatar;
  const res = await apiFetch(`${API_BASE}/leaderboard/score`, {
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

// Cho phép nhấn Enter trong ô nhập để bắt đầu giả lập
simCountInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !isSimulating) startSimulate();
});


// ─── BOOT ──────────────────────────────────────────────────────────────────────
init();
