(function () {
  "use strict";

  var root = document.querySelector("[data-realtime-chat]");
  if (!root || !window.WebSocket) {
    return;
  }

  var kind = root.dataset.chatKind;
  var roomId = root.dataset.roomId;
  var currentUserId = root.dataset.currentUserId;
  var reportUrlTemplate = root.dataset.reportUrlTemplate || "";
  var messageList = root.querySelector("[data-message-list]");
  var form = root.querySelector("[data-chat-form]");
  var input = root.querySelector("[data-chat-input]");
  var statusEl = root.querySelector("[data-chat-status]");
  var knownMessageIds = new Set();
  var socket = createSocketClient();

  Array.prototype.forEach.call(root.querySelectorAll("[data-message-id]"), function (messageEl) {
    knownMessageIds.add(String(messageEl.dataset.messageId));
  });

  socket.on("joined", function () {
    setStatus("실시간 연결됨");
  });

  socket.on("product_message", function (message) {
    if (kind !== "product" || String(message.room_id) !== String(roomId)) {
      return;
    }
    appendMessage(message, true);
  });

  socket.on("plaza_message", function (message) {
    if (kind !== "plaza") {
      return;
    }
    appendMessage(message, false);
  });

  socket.on("chat_error", function (payload) {
    setStatus(payload && payload.message ? payload.message : "전송 실패");
  });

  socket.connect(function () {
    if (kind === "product") {
      socket.emit("join_product_room", { room_id: Number(roomId) });
    } else if (kind === "plaza") {
      socket.emit("join_plaza", {});
    }
  });

  if (form && input) {
    form.addEventListener("submit", function (event) {
      if (!socket.isReady()) {
        return;
      }

      var content = input.value.trim();
      if (!content) {
        event.preventDefault();
        return;
      }
      if (content.length > 500) {
        event.preventDefault();
        setStatus("메시지가 너무 깁니다");
        return;
      }

      event.preventDefault();
      if (kind === "product") {
        socket.emit("send_product_message", { room_id: Number(roomId), content: content });
      } else if (kind === "plaza") {
        socket.emit("send_plaza_message", { content: content });
      }
      input.value = "";
      input.focus();
    });
  }

  function appendMessage(message, canReport) {
    if (!message || !message.id || knownMessageIds.has(String(message.id))) {
      return;
    }
    knownMessageIds.add(String(message.id));

    var emptyState = messageList.querySelector(".empty-inline");
    if (emptyState) {
      emptyState.remove();
    }

    var isMine = String(message.sender_id) === String(currentUserId);
    var article = document.createElement("article");
    article.className = isMine ? "message mine" : "message";
    article.dataset.messageId = String(message.id);

    var meta = document.createElement("p");
    meta.className = "message-meta";
    meta.textContent = String(message.sender || "unknown") + " · " + formatMessageTime(message.created_at);
    article.appendChild(meta);

    var body = document.createElement("p");
    body.textContent = String(message.content || "");
    article.appendChild(body);

    if (canReport && !isMine && reportUrlTemplate) {
      var reportLink = document.createElement("a");
      reportLink.className = "report-link";
      reportLink.href = reportUrlTemplate.replace("__MESSAGE_ID__", encodeURIComponent(message.id));
      reportLink.textContent = "신고";
      article.appendChild(reportLink);
    }

    messageList.appendChild(article);
    messageList.scrollTop = messageList.scrollHeight;
  }

  function formatMessageTime(value) {
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    return (
      pad(date.getMonth() + 1) +
      "/" +
      pad(date.getDate()) +
      " " +
      pad(date.getHours()) +
      ":" +
      pad(date.getMinutes())
    );
  }

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function setStatus(message) {
    if (statusEl) {
      statusEl.textContent = message;
    }
  }

  function createSocketClient() {
    var handlers = {};
    var ws = null;
    var ready = false;
    var connectCallback = null;
    var reconnectTimer = null;

    return {
      connect: connect,
      emit: emit,
      isReady: function () {
        return ready && ws && ws.readyState === WebSocket.OPEN;
      },
      on: function (name, handler) {
        handlers[name] = handlers[name] || [];
        handlers[name].push(handler);
      },
    };

    function connect(onConnect) {
      connectCallback = onConnect;
      open();
    }

    function open() {
      clearTimeout(reconnectTimer);
      ready = false;
      setStatus("연결 중");

      var protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(protocol + "//" + window.location.host + "/socket.io/?EIO=4&transport=websocket");

      ws.onmessage = function (event) {
        handlePacket(String(event.data || ""));
      };
      ws.onclose = function () {
        ready = false;
        setStatus("재연결 중");
        reconnectTimer = setTimeout(open, 1500);
      };
      ws.onerror = function () {
        ready = false;
        setStatus("연결 오류");
      };
    }

    function emit(name, payload) {
      if (!ready || !ws || ws.readyState !== WebSocket.OPEN) {
        return;
      }
      ws.send("42" + JSON.stringify([name, payload || {}]));
    }

    function handlePacket(packet) {
      if (!packet) {
        return;
      }
      if (packet === "2") {
        ws.send("3");
        return;
      }
      if (packet.charAt(0) === "0") {
        ws.send("40");
        return;
      }
      if (packet.indexOf("40") === 0) {
        ready = true;
        if (connectCallback) {
          connectCallback();
        }
        return;
      }
      if (packet.indexOf("42") === 0) {
        dispatchEvent(packet.slice(2));
      }
    }

    function dispatchEvent(rawPayload) {
      var payload;
      try {
        payload = JSON.parse(rawPayload);
      } catch (error) {
        return;
      }
      if (!Array.isArray(payload) || payload.length < 1) {
        return;
      }
      (handlers[payload[0]] || []).forEach(function (handler) {
        handler(payload[1] || {});
      });
    }
  }
})();
