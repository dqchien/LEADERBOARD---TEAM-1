/**
 * app.js
 * Xử lý:
 *  1. Kết nối WebSocket → nhận real-time updates
 *  2. Fetch leaderboard top 10 qua REST API
 *  3. Nút "Tự động giả lập nạp điểm" → gọi POST /leaderboard/score hàng loạt
 *  4. Cập nhật UI: rank jump, score flash, pinned bar
 */

// ─── CONFIG ────────────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws/leaderboard";

const MY_USER_ID = "demo_user";         // user được ghim ở pinned bar
const MY_NAME = "Bạn";
const TOP_N = 10;

const SIM_TOTAL = 2000;               // số lượt score update khi nhấn simulate
const SIM_BATCH = 30;                 // gửi bao nhiêu request mỗi lần
const SIM_DELAY = 50;                 // ms giữa mỗi batch
const SIM_USERS = 200;               // phạm vi user giả lập (user_1 → user_N)
const SIM_SCORE_RANGE = [10, 100];     // score mỗi lần cộng


// ─── STATE ─────────────────────────────────────────────────────────────────────
let ws = null;
let wsReconnectTimer = null;
let leaderboardData = [];   // mảng top N hiện tại
let totalUpdates = 0;
let isSimulating = false;
let simAborted = false;

let myRank = null;
let myScore = 0;


// ─── DOM REFS ──────────────────────────────────────────────────────────────────
const lbBody = document.getElementById("lb-body");
const statTotal = document.getElementById("stat-total");
const statUpdates = document.getElementById("stat-updates");
const statConnections = document.getElementById("stat-connections");
const wsDot = document.getElementById("ws-dot");
const wsLabel = document.getElementById("ws-label");
const btnSimulate = document.getElementById("btn-simulate");
const btnStop = document.getElementById("btn-stop");
const btnRefresh = document.getElementById("btn-refresh");
const simProgress = document.getElementById("sim-progress");
const progressFill = document.getElementById("progress-fill");
const progressText = document.getElementById("progress-text");
const pinnedRank = document.getElementById("pinned-rank");
const pinnedName = document.getElementById("pinned-name");
const pinnedScore = document.getElementById("pinned-score");
const toastContainer = document.getElementById("toast-container");


// ─── INIT ──────────────────────────────────────────────────────────────────────
async function init() {
    // Đảm bảo demo user tồn tại với score ban đầu
    await ensureDemoUser();

    // Load leaderboard lần đầu
    await fetchLeaderboard();

    // Kết nối WebSocket
    connectWebSocket();
}


// ─── DEMO USER ─────────────────────────────────────────────────────────────────
async function ensureDemoUser() {
    try {
        await postScore(MY_USER_ID, 50, MY_NAME, "demo.png");
    } catch (_) { /* ignore */ }
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
            if (data.event === "score_updated") {
                handleScoreUpdate(data);
            }
        } catch (_) { /* ignore malformed */ }
    };

    ws.onclose = () => {
        setWsStatus("disconnected");
        // Auto reconnect sau 3s
        wsReconnectTimer = setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
        ws.close();
    };
}

function setWsStatus(status) {
    wsDot.className = `ws-dot ${status}`;
    wsLabel.textContent = status === "connected" ? "Real-time" : "Đang kết nối lại...";
}


// ─── FETCH LEADERBOARD ─────────────────────────────────────────────────────────
async function fetchLeaderboard() {
    lbBody.innerHTML = `<div class="spinner"></div>`;

    try {
        const res = await fetch(`${API_BASE}/leaderboard/top?n=${TOP_N}`);
        const data = await res.json();

        leaderboardData = data.leaderboard || [];
        renderLeaderboard(leaderboardData);

        statTotal.textContent = (data.total_users || 0).toLocaleString();
    } catch (e) {
        lbBody.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <div>Không thể kết nối API</div>
        <div style="font-size:12px;margin-top:6px">Kiểm tra server đang chạy chưa</div>
      </div>`;
    }

    // Lấy rank của demo user
    await fetchMyRank();
}


async function fetchMyRank() {
    try {
        const res = await fetch(`${API_BASE}/leaderboard/rank/${MY_USER_ID}`);
        if (res.ok) {
            const data = await res.json();
            myRank = data.rank;
            myScore = data.score;
            updatePinnedBar(myRank, myScore, false);
        }
    } catch (_) { /* ignore */ }
}


// ─── RENDER LEADERBOARD ────────────────────────────────────────────────────────
function renderLeaderboard(entries) {
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


function buildRow(entry, animIndex) {
    const rankClass = entry.rank <= 3 ? `rank-${entry.rank}` : "";
    const rankIcon = entry.rank === 1 ? "🥇"
        : entry.rank === 2 ? "🥈"
            : entry.rank === 3 ? "🥉"
                : `#${entry.rank}`;

    const initial = (entry.name || entry.user_id || "?")[0].toUpperCase();
    const isMe = entry.user_id === MY_USER_ID;
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
        <div class="score-value" id="score-${entry.user_id}">${Math.round(entry.score).toLocaleString()}</div>
        <div class="score-change" id="change-${entry.user_id}"></div>
      </div>
    </div>`;
}


function avatarGradient(userId) {
    // Tạo màu gradient nhất quán theo user_id
    const hash = [...userId].reduce((h, c) => (h * 31 + c.charCodeAt(0)) | 0, 0);
    const h1 = Math.abs(hash) % 360;
    const h2 = (h1 + 60) % 360;
    return `background:linear-gradient(135deg,hsl(${h1},70%,50%),hsl(${h2},70%,40%))`;
}


function escHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}


// ─── HANDLE REAL-TIME UPDATE (từ WebSocket) ────────────────────────────────────
function handleScoreUpdate(data) {
    const { user_id, new_total_score, rank } = data;

    totalUpdates++;
    statUpdates.textContent = totalUpdates.toLocaleString();

    // Cập nhật demo user nếu là mình
    if (user_id === MY_USER_ID) {
        const oldRank = myRank;
        myRank = rank;
        myScore = new_total_score;
        updatePinnedBar(rank, new_total_score, oldRank !== null && rank !== oldRank);
    }

    // Cập nhật score cell nếu user đang hiển thị trong top N
    const scoreEl = document.getElementById(`score-${user_id}`);
    const changeEl = document.getElementById(`change-${user_id}`);
    const rowEl = document.getElementById(`row-${user_id}`);

    if (scoreEl) {
        const oldScore = parseFloat(scoreEl.dataset.raw || scoreEl.textContent.replace(/,/g, "")) || 0;
        const diff = new_total_score - oldScore;

        scoreEl.dataset.raw = new_total_score;
        scoreEl.textContent = Math.round(new_total_score).toLocaleString();

        if (changeEl && diff > 0) {
            changeEl.textContent = `+${Math.round(diff)}`;
            changeEl.className = "score-change up show";
            setTimeout(() => changeEl.classList.remove("show"), 1500);
        }

        if (rowEl) {
            rowEl.classList.remove("updated");
            // Force reflow để animation chạy lại
            void rowEl.offsetWidth;
            rowEl.classList.add("updated");
        }
    } else {
        // User không có trong danh sách hiển thị → re-fetch nếu có thể vào top
        // Debounce: chỉ fetch nếu chưa fetch gần đây
        scheduleFetch();
    }
}

// Debounced fetch để tránh flood request
let fetchTimer = null;
function scheduleFetch() {
    clearTimeout(fetchTimer);
    fetchTimer = setTimeout(fetchLeaderboard, 800);
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
    simAborted = false;
    totalUpdates = 0;

    btnSimulate.disabled = true;
    btnStop.style.display = "inline-flex";
    simProgress.classList.add("visible");

    showToast(`🚀 Bắt đầu giả lập ${SIM_TOTAL.toLocaleString()} lượt nạp điểm...`);

    let sent = 0;

    while (sent < SIM_TOTAL && !simAborted) {
        const batchSize = Math.min(SIM_BATCH, SIM_TOTAL - sent);
        const promises = [];

        for (let i = 0; i < batchSize; i++) {
            const userId = `user_${Math.floor(Math.random() * SIM_USERS) + 1}`;
            const score = Math.floor(
                Math.random() * (SIM_SCORE_RANGE[1] - SIM_SCORE_RANGE[0]) + SIM_SCORE_RANGE[0]
            );
            promises.push(postScore(userId, score));
        }

        await Promise.allSettled(promises);
        sent += batchSize;

        // Cập nhật progress bar
        const pct = (sent / SIM_TOTAL) * 100;
        progressFill.style.width = `${pct}%`;
        progressText.textContent = `${sent.toLocaleString()} / ${SIM_TOTAL.toLocaleString()}`;

        await sleep(SIM_DELAY);
    }

    // Giả lập xong → refresh leaderboard 1 lần cuối
    await fetchLeaderboard();
    showToast(simAborted ? "⏹ Đã dừng giả lập" : "✅ Giả lập hoàn tất!");

    isSimulating = false;
    btnSimulate.disabled = false;
    btnStop.style.display = "none";
    simProgress.classList.remove("visible");
    progressFill.style.width = "0%";
}

function stopSimulate() {
    simAborted = true;
    showToast("⏸ Đang dừng...");
}


// ─── API CALLS ─────────────────────────────────────────────────────────────────
async function postScore(userId, score, name, avatar) {
    const body = { user_id: userId, score };
    if (name) body.name = name;
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


// ─── BOOT ──────────────────────────────────────────────────────────────────────
init();