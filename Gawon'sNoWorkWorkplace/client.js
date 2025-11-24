//  광장 멀티플레이 클라이언트
// ================================

// ---- 탭별 고유 clientId (sessionStorage 사용) ----
var CLIENT_KEY = "plazaClientId";
var clientId = sessionStorage.getItem(CLIENT_KEY);
if (!clientId) {
  clientId = "c_" + Math.random().toString(36).substr(2, 9) + "_" + Date.now().toString(36);
  sessionStorage.setItem(CLIENT_KEY, clientId);
}

// ---- 접속 전에 닉네임 입력 ----
var nickname = prompt("광장에서 사용할 닉네임을 입력하세요.\n(취소 또는 공백이면 랜덤 닉네임 사용)");
if (nickname == null) {
  nickname = "";
} else {
  nickname = nickname.replace(/^\s+|\s+$/g, "");
}

// Socket.IO: 같은 도메인/포트(8067) + polling
var socket = io({
  transports: ["polling"],
  query: {
    clientId: clientId,   // ★ 탭 고유 ID
    nickname: nickname    // ★ 닉네임 후보
  }
});

// 캔버스
var canvas = document.getElementById("gameCanvas");
var ctx = canvas.getContext("2d");

function resizeCanvas() {
  canvas.width = canvas.clientWidth || 1200;
  canvas.height = canvas.clientHeight || 700;
}
resizeCanvas();
window.addEventListener("resize", resizeCanvas);

// 배경 이미지
var bgImage = new Image();
var bgLoaded = false;
bgImage.src = "plaza_bg.png";    // 같은 폴더에 있어야 함
bgImage.onload = function () {
  bgLoaded = true;
};

// 채팅 요소
var chatLog = document.getElementById("chat-log");
var chatInput = document.getElementById("chat-input");

function addChatLine(text) {
  var div = document.createElement("div");
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

// 플레이어 상태
var myId = null;     // = clientId
var players = {};
var moveState = { left: false, right: false, up: false, down: false };

// ------------------------------
// 소켓 이벤트
// ------------------------------
socket.on("connect", function () {
  addChatLine("[시스템] 서버 연결 완료! socket.id = " + socket.id);
  console.log("✔ Socket connected:", socket.id);

  // 접속 직후에도 닉네임 한 번 더 세팅 (안전)
  if (nickname && nickname.length > 0) {
    socket.emit("set_nickname", nickname);
  }
});

socket.on("connect_error", function (err) {
  addChatLine("[에러] 서버 연결 실패: " + err.message);
  console.error("❌ Socket connect error:", err);
});

socket.on("disconnect", function () {
  addChatLine("[시스템] 서버 연결이 끊어졌습니다.");
  console.warn("⚠ Disconnected from server");
});

// 초기 데이터 + 채팅 기록
socket.on("init", function (data) {
  // 서버가 넘겨주는 id = clientId
  myId = data.id;
  players = data.players || {};

  // 과거 채팅 로그 표시
  if (data.chatHistory && data.chatHistory.forEach) {
    chatLog.innerHTML = "";
    data.chatHistory.forEach(function (entry) {
      addChatLine(entry.nickname + ": " + entry.message);
    });
  }

  if (data.me && data.me.nickname) {
    addChatLine("[시스템] 광장에 입장했습니다. 내 닉네임: " + data.me.nickname);
  }

  console.log("INIT data:", data);
});

// 새 플레이어
socket.on("player_joined", function (payload) {
  var id = payload.id;
  var player = payload.player;
  players[id] = player;
  addChatLine("[시스템] " + player.nickname + " 님이 입장했습니다.");
});

// 퇴장
socket.on("player_left", function (payload) {
  var id = payload.id;
  var p = players[id];
  if (p) {
    addChatLine("[시스템] " + p.nickname + " 님이 퇴장했습니다.");
  }
  delete players[id];
});

// 위치 업데이트
socket.on("player_moved", function (payload) {
  var id = payload.id;
  if (!players[id]) return;
  players[id].x = payload.x;
  players[id].y = payload.y;
});

// 채팅 수신
socket.on("chat", function (entry) {
  addChatLine(entry.nickname + ": " + entry.message);
});

// ------------------------------
// 입력 처리
// ------------------------------
window.addEventListener("keydown", function (e) {
  if (e.target === chatInput) return;
  if (e.key === "ArrowLeft") moveState.left = true;
  if (e.key === "ArrowRight") moveState.right = true;
  if (e.key === "ArrowUp") moveState.up = true;
  if (e.key === "ArrowDown") moveState.down = true;
});

window.addEventListener("keyup", function (e) {
  if (e.target === chatInput) return;
  if (e.key === "ArrowLeft") moveState.left = false;
  if (e.key === "ArrowRight") moveState.right = false;
  if (e.key === "ArrowUp") moveState.up = false;
  if (e.key === "ArrowDown") moveState.down = false;
});

// 채팅 입력
chatInput.addEventListener("keydown", function (e) {
  if (e.key === "Enter") {
    var msg = chatInput.value;
    msg = msg.replace(/^\s+|\s+$/g, "");
    if (msg.length > 0) {
      socket.emit("chat", msg);
      chatInput.value = "";
    }
  }
});

// 50ms마다 이동 패킷 전송
setInterval(function () {
  var dx = (moveState.right ? 1 : 0) - (moveState.left ? 1 : 0);
  var dy = (moveState.down ? 1 : 0) - (moveState.up ? 1 : 0);
  if (dx !== 0 || dy !== 0) {
    socket.emit("move", { dx: dx, dy: dy });
  }
}, 50);

// ------------------------------
// 렌더링 루프
// ------------------------------
function draw() {
  // 배경
  if (bgLoaded) {
    ctx.drawImage(bgImage, 0, 0, canvas.width, canvas.height);
  } else {
    ctx.fillStyle = "#020617";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  // 플레이어 렌더링
  Object.keys(players).forEach(function (id) {
    var p = players[id];
    var radius = (id === myId) ? 16 : 14;

    // 몸통
    ctx.beginPath();
    ctx.fillStyle = p.color || "#4ecdc4";
    ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
    ctx.fill();

    // 머리
    ctx.beginPath();
    ctx.fillStyle = "#f9fafb";
    ctx.arc(p.x, p.y - radius - 8, radius * 0.7, 0, Math.PI * 2);
    ctx.fill();

    // 닉네임
    ctx.fillStyle = "#333333";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(p.nickname || "Player", p.x, p.y - radius - 22);
  });

  requestAnimationFrame(draw);
}

draw();
