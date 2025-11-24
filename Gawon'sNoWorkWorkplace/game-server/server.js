// server.js ─ 광장 멀티플레이 게임 서버 (Node 구버전 호환)

const http = require('http');
const { Server } = require('socket.io');

const PORT = 포트번호;

const httpServer = http.createServer();

const io = new Server(httpServer, {
  cors: {
    origin: "url:port",
    methods: ["GET", "POST"],
  },
});

// ----------------------------------
// 전역 상태
// ----------------------------------

// players: clientId -> { id, x, y, color, nickname, hp, lastSeen }
var players = {};

// socketToClient: socket.id -> clientId
var socketToClient = {};

// 채팅 로그
var chatHistory = [];   // [{ nickname, message, ts }]
var MAX_CHAT_HISTORY = 100;

// ----------------------------------
// 유틸 함수
// ----------------------------------
function randomNickname() {
  var animals = ["Fox", "Cat", "Dog", "Bear", "Rabbit", "Panda", "Tiger"];
  var adj = ["Cute", "Shiny", "Silent", "Happy", "Angry", "Lazy", "Smart"];
  var a = adj[Math.floor(Math.random() * adj.length)];
  var b = animals[Math.floor(Math.random() * animals.length)];
  var num = Math.floor(Math.random() * 900) + 100;
  return a + b + num;
}

function randomColor() {
  var colors = ["#ff6b6b", "#4ecdc4", "#ffe66d", "#1a535c", "#ff9f1c"];
  return colors[Math.floor(Math.random() * colors.length)];
}

function normalizeNickname(raw) {
  if (typeof raw !== "string") raw = "";
  var nickname = raw.replace(/^\s+|\s+$/g, ""); // trim
  if (!nickname) return "";
  var MAX_LEN = 16;
  if (nickname.length > MAX_LEN) {
    nickname = nickname.slice(0, MAX_LEN);
  }
  return nickname;
}

function pushChat(nickname, message) {
  var entry = {
    nickname: nickname,
    message: message,
    ts: Date.now()
  };
  chatHistory.push(entry);
  if (chatHistory.length > MAX_CHAT_HISTORY) {
    chatHistory.splice(0, chatHistory.length - MAX_CHAT_HISTORY);
  }
  io.emit('chat', entry);
}

// ----------------------------------
// 소켓 연결
// ----------------------------------
io.on('connection', function (socket) {
  console.log("=== [connect] socket:", socket.id,
              "query:", socket.handshake && socket.handshake.query, "===");

  // 1) clientId 가져오기 (없으면 socket.id 사용)
  var clientId = null;
  if (socket.handshake &&
      socket.handshake.query &&
      socket.handshake.query.clientId) {
    clientId = socket.handshake.query.clientId;
  }
  if (!clientId) {
    clientId = socket.id;
  }
  socketToClient[socket.id] = clientId;

  // 2) 닉네임 후보
  var nicknameRaw = "";
  if (socket.handshake &&
      socket.handshake.query &&
      socket.handshake.query.nickname) {
    nicknameRaw = socket.handshake.query.nickname;
  }
  var nicknameFromQuery = normalizeNickname(nicknameRaw);

  // 3) 기존 플레이어 재사용 여부
  var player = players[clientId];

  if (player && player.hp > 0) {
    // 살아있는 기존 캐릭터 재사용 (같은 탭 새로고침)
    console.log("[reuse player]", clientId, "nick:", player.nickname);
    player.lastSeen = Date.now();
  } else {
    // 새 플레이어 생성 (처음 접속, 또는 죽은 후 재접속)
    var nicknameFinal = nicknameFromQuery || (player && player.nickname) || randomNickname();

    player = {
      id: clientId,
      x: 600 + (Math.random() * 80 - 40),
      y: 350 + (Math.random() * 80 - 40),
      color: randomColor(),
      nickname: nicknameFinal,
      hp: 3,            // ★ 하트 3개
      lastSeen: Date.now()
    };
    players[clientId] = player;

    // 다른 사람에게 "새 플레이어" 알림
    socket.broadcast.emit('player_joined', {
      id: clientId,
      player: player
    });

    pushChat("SYSTEM", nicknameFinal + " 님이 입장했습니다.");
  }

  // 본인에게 전체 상태 + 채팅 기록 전달
  socket.emit('init', {
    id: clientId,
    me: player,
    players: players,
    chatHistory: chatHistory
  });

  // --------------------------------
  // 닉네임 변경 (선택 기능)
  // --------------------------------
  socket.on('set_nickname', function (rawNick) {
    var cid = socketToClient[socket.id];
    if (!cid) return;
    var p = players[cid];
    if (!p) return;

    var nn = normalizeNickname(rawNick);
    if (!nn) return;

    var old = p.nickname;
    p.nickname = nn;
    p.lastSeen = Date.now();

    pushChat("SYSTEM", old + " 님이 닉네임을 " + nn + "(으)로 변경했습니다.");
  });

  // --------------------------------
  // 이동
  // --------------------------------
  socket.on('move', function (data) {
    var cid = socketToClient[socket.id];
    if (!cid) return;
    var p = players[cid];
    if (!p || p.hp <= 0) return;  // 죽은 플레이어는 무시

    var speed = 3;
    var dx = data && data.dx ? data.dx : 0;
    var dy = data && data.dy ? data.dy : 0;

    p.x += dx * speed;
    p.y += dy * speed;

    // 방 범위 제한
    if (p.x < 80) p.x = 80;
    if (p.x > 1120) p.x = 1120;
    if (p.y < 80) p.y = 80;
    if (p.y > 620) p.y = 620;

    p.lastSeen = Date.now();

    io.emit('player_moved', {
      id: cid,
      x: p.x,
      y: p.y
    });
  });

  // --------------------------------
  // 공격 (Space)
// --------------------------------
  socket.on('attack', function () {
    var cid = socketToClient[socket.id];
    console.log("[attack] from socket:", socket.id, "clientId:", cid);
    if (!cid) return;
    var attacker = players[cid];
    if (!attacker || attacker.hp <= 0) {
      console.log("  -> attacker not found or dead");
      return;
    }

    attacker.lastSeen = Date.now();

    var RANGE = 80;             // 공격 범위 (픽셀)
    var range2 = RANGE * RANGE;
    var closestId = null;
    var closestDist2 = range2;

    // 가장 가까운 타겟 찾기
    Object.keys(players).forEach(function (oid) {
      if (oid === cid) return;
      var t = players[oid];
      if (!t || t.hp <= 0) return;

      var dx = attacker.x - t.x;
      var dy = attacker.y - t.y;
      var d2 = dx * dx + dy * dy;
      if (d2 <= closestDist2) {
        closestDist2 = d2;
        closestId = oid;
      }
    });

    if (!closestId) {
      console.log("  -> no target in range");
      // 공격 범위 내 대상 없음 → 공격자에게만 알림
      socket.emit('attack_result', {
        success: false,
        reason: 'no_target'
      });
      return;
    }

    var target = players[closestId];
    if (!target) {
      console.log("  -> target vanished");
      return;
    }

    target.hp -= 1;
    if (target.hp < 0) target.hp = 0;
    target.lastSeen = Date.now();

    console.log("  -> hit", target.nickname, "new hp:", target.hp);

    // HP 변경 브로드캐스트
    io.emit('hp_update', {
      id: closestId,
      hp: target.hp
    });

    // 공격 결과 (공격자에게는 success true 보냄)
    socket.emit('attack_result', {
      success: true,
      targetId: closestId,
      hp: target.hp,
      targetNickname: target.nickname
    });

    pushChat("SYSTEM",
      attacker.nickname + " 님이 " + target.nickname +
      " 님을 공격했습니다! (남은 하트: " + target.hp + ")"
    );

    // 죽음 처리
    if (target.hp <= 0) {
      console.log("  ->", target.nickname, "died");
      // 모든 클라에게 죽음 알림
      io.emit('player_dead', {
        id: closestId,
        nickname: target.nickname
      });

      // 채팅창에 "{닉네임}님이 죽었습니다."
      pushChat("SYSTEM", target.nickname + "님이 죽었습니다.");

      // 서버에서 캐릭터 제거
      delete players[closestId];
    }
  });

  // --------------------------------
  // 채팅
  // --------------------------------
  socket.on('chat', function (msg) {
    var cid = socketToClient[socket.id];
    if (!cid) return;
    var p = players[cid];
    if (!p || p.hp <= 0) return; // 죽은 플레이어는 채팅 금지 (원하면 풀어도 됨)

    var text = String(msg || "");
    text = text.replace(/^\s+|\s+$/g, "");
    if (!text) return;

    pushChat(p.nickname, text);
  });

  // --------------------------------
  // 연결 종료
  // --------------------------------
  socket.on('disconnect', function () {
    var cid = socketToClient[socket.id];
    console.log("[disconnect] socket:", socket.id, "clientId:", cid);

    delete socketToClient[socket.id];
    // 여기서는 players[cid] 삭제 안 함
    // → 같은 탭 새로고침하면 기존 캐릭터 유지
  });
});

// ----------------------------------
// 유령 플레이어 정리 (오랫동안 아무 행동 없는 캐릭터 제거)
// ----------------------------------
setInterval(function () {
  var now = Date.now();
  var TIMEOUT = 60000; // 60초 동안 이벤트 없으면 제거

  Object.keys(players).forEach(function (cid) {
    var p = players[cid];
    if (!p) return;
    if (now - p.lastSeen > TIMEOUT) {
      console.log("[cleanup stale player]", cid, p.nickname);
      delete players[cid];
      io.emit('player_left', { id: cid });
    }
  });
}, 10000); // 10초마다 검사

httpServer.listen(PORT, function () {
  console.log("Game server listening on port " + PORT);
});
