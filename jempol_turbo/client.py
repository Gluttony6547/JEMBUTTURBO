"""Tkinter GUI client for Jempol Turbo."""

from __future__ import annotations

import argparse
import queue
import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from jempol_turbo.protocol import PacketBuffer, ProtocolError, encode_packet
from jempol_turbo.server import DEFAULT_HOST, DEFAULT_PORT
from jempol_turbo.texts import DEFAULT_MODE, GAME_MODES


COLORS = {
    "bg": "#0F172A",
    "surface": "#FFFFFF",
    "surface_alt": "#E0F2FE",
    "ink": "#0F172A",
    "muted": "#64748B",
    "primary": "#2563EB",
    "primary_dark": "#1E40AF",
    "green": "#00B894",
    "blue": "#0984E3",
    "red": "#D63031",
    "amber": "#F59E0B",
    "line": "#CBD5E1",
}


class NetworkClient:
    def __init__(self, host: str, port: int, inbox: queue.Queue[dict[str, Any]]) -> None:
        self.host = host
        self.port = port
        self.inbox = inbox
        self.sock: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.running = False
        self.seq = 0
        self.session_token: str | None = None
        self._send_lock = threading.Lock()

    def connect_hello(self, username: str) -> None:
        self._connect()
        self.send("HELLO", {"username": username}, include_token=False)

    def connect_reconnect(self, session_token: str) -> None:
        self.session_token = session_token
        self._connect()
        self.send("RECONNECT", {"session_token": session_token}, include_token=True)

    def _connect(self) -> None:
        self.close()
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.settimeout(0.5)
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, name="network-reader", daemon=True)
        self.thread.start()

    def send(
        self,
        packet_type: str,
        payload: dict[str, Any] | None = None,
        *,
        include_token: bool = True,
    ) -> None:
        if self.sock is None:
            return
        token = self.session_token if include_token else None
        with self._send_lock:
            raw = encode_packet(
                packet_type,
                seq=self.seq,
                payload=payload or {},
                session_token=token,
            )
            self.seq += 1
            try:
                self.sock.sendall(raw)
            except OSError:
                self.inbox.put({"type": "_DISCONNECTED", "payload": {"message": "send failed"}})

    def _read_loop(self) -> None:
        assert self.sock is not None
        buffer = PacketBuffer()
        while self.running:
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            try:
                packets = buffer.feed(data)
            except ProtocolError as exc:
                self.inbox.put({"type": "ERROR", "payload": {"message": str(exc)}})
                continue
            for packet in packets:
                if packet["type"] == "PING":
                    ping_id = packet.get("payload", {}).get("ping_id")
                    self.send("PONG", {"ping_id": ping_id})
                self.inbox.put(packet)
        self.running = False
        self.inbox.put({"type": "_DISCONNECTED", "payload": {"message": "connection closed"}})

    def close(self) -> None:
        self.running = False
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None


class JempolTurboApp:
    def __init__(self, root: tk.Tk, host: str, port: int) -> None:
        self.root = root
        self.root.title("Jempol Turbo")
        self.root.geometry("980x720")
        self.root.minsize(860, 640)
        self.root.configure(bg=COLORS["bg"])

        self.inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self.network = NetworkClient(host, port, self.inbox)
        self.username = ""
        self.session_token = ""
        self.target_text = ""
        self.current_room_id = ""
        self.current_mode = DEFAULT_MODE
        self.current_mode_label = GAME_MODES[DEFAULT_MODE]["label"]
        self.match_running = False
        self.last_input_send_at = 0.0
        self.latest_players: list[dict[str, Any]] = []

        self._configure_style()
        self._build_shell()
        self._build_login()
        self.root.after(50, self._poll_network)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"])
        style.configure("Soft.TFrame", background=COLORS["surface_alt"])
        style.configure("TProgressbar", troughcolor="#E2E8F0", background=COLORS["primary"], bordercolor="#E2E8F0")
        style.configure("Green.Horizontal.TProgressbar", troughcolor="#D1FAE5", background=COLORS["green"])
        style.configure("Red.Horizontal.TProgressbar", troughcolor="#FEE2E2", background=COLORS["red"])

    def _build_shell(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.container = ttk.Frame(self.root, padding=22, style="App.TFrame")
        self.container.grid(row=0, column=0, sticky="nsew")
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(1, weight=1)

        header = tk.Frame(self.container, bg=COLORS["primary_dark"], padx=22, pady=18)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="Jempol Turbo",
            bg=COLORS["primary_dark"],
            fg="white",
            font=("Segoe UI", 28, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="Real-time Typing Battle | TCP Socket | Matchmaking | Reconnect",
            bg=COLORS["primary_dark"],
            fg="#BFDBFE",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.status_var = tk.StringVar(value="Connect to the server to start.")
        tk.Label(
            header,
            textvariable=self.status_var,
            bg=COLORS["primary_dark"],
            fg="#FEF3C7",
            font=("Segoe UI", 10),
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        self.content = ttk.Frame(self.container, style="App.TFrame")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _card(self, parent: tk.Widget, *, bg: str = "surface") -> tk.Frame:
        return tk.Frame(parent, bg=COLORS[bg], padx=22, pady=20, highlightthickness=1, highlightbackground=COLORS["line"])

    def _label(
        self,
        parent: tk.Widget,
        text: str = "",
        *,
        textvariable: tk.StringVar | None = None,
        size: int = 10,
        weight: str = "normal",
        fg: str = "ink",
        bg: str = "surface",
        wraplength: int = 0,
    ) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            textvariable=textvariable,
            bg=COLORS[bg],
            fg=COLORS[fg] if fg in COLORS else fg,
            font=("Segoe UI", size, weight),
            wraplength=wraplength,
            justify="left",
        )

    def _button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        *,
        bg: str = "primary",
        fg: str = "white",
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=COLORS[bg],
            activebackground=COLORS[bg],
            fg=COLORS[fg] if fg in COLORS else fg,
            activeforeground=COLORS[fg] if fg in COLORS else fg,
            relief="flat",
            padx=16,
            pady=9,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        )

    def _entry(self, parent: tk.Widget, variable: tk.Variable, *, show: str = "") -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=variable,
            show=show,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["primary"],
            font=("Segoe UI", 10),
        )

    def _build_login(self) -> None:
        self._clear_content()
        card = self._card(self.content)
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)

        self._label(card, "Masuk ke Arena", size=20, weight="bold").grid(row=0, column=0, columnspan=2, sticky="w")
        self._label(
            card,
            "Gunakan dua client dengan username berbeda. Simpan session token untuk demo reconnect.",
            fg="muted",
            wraplength=720,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 18))

        self._label(card, "Server host").grid(row=2, column=0, sticky="w", pady=7)
        self.host_var = tk.StringVar(value=self.network.host)
        self._entry(card, self.host_var).grid(row=2, column=1, sticky="ew", pady=7)

        self._label(card, "Server port").grid(row=3, column=0, sticky="w", pady=7)
        self.port_var = tk.IntVar(value=self.network.port)
        self._entry(card, self.port_var).grid(row=3, column=1, sticky="ew", pady=7)

        self._label(card, "Username").grid(row=4, column=0, sticky="w", pady=7)
        self.username_var = tk.StringVar(value=self.username)
        self._entry(card, self.username_var).grid(row=4, column=1, sticky="ew", pady=7)

        self._label(card, "Session token").grid(row=5, column=0, sticky="w", pady=7)
        self.token_var = tk.StringVar(value=self.session_token)
        self._entry(card, self.token_var).grid(row=5, column=1, sticky="ew", pady=7)

        buttons = tk.Frame(card, bg=COLORS["surface"])
        buttons.grid(row=6, column=0, columnspan=2, sticky="w", pady=(18, 0))
        self._button(buttons, "Connect", self._connect, bg="green").grid(row=0, column=0, padx=(0, 10))
        self._button(buttons, "Reconnect", self._reconnect, bg="amber").grid(row=0, column=1)

    def _build_matchmaking(self) -> None:
        self._clear_content()
        wrapper = tk.Frame(self.content, bg=COLORS["bg"])
        wrapper.grid(row=0, column=0, sticky="nsew")
        wrapper.columnconfigure(0, weight=1)

        card = self._card(wrapper)
        card.grid(row=0, column=0, sticky="ew")
        card.columnconfigure(0, weight=1)

        self._label(card, f"Logged in as {self.username}", size=16, weight="bold").grid(row=0, column=0, sticky="w")
        self._label(card, f"Session token: {self.session_token}", fg="muted").grid(row=1, column=0, sticky="w", pady=(4, 16))

        self.mode_var = tk.StringVar(value=self.current_mode)
        mode_frame = tk.Frame(card, bg=COLORS["surface"])
        mode_frame.grid(row=2, column=0, sticky="ew")
        mode_frame.columnconfigure((0, 1, 2), weight=1)
        for index, (mode_id, mode_data) in enumerate(GAME_MODES.items()):
            accent = mode_data["accent"]
            option = tk.Frame(mode_frame, bg="#F8FAFC", padx=12, pady=10, highlightthickness=2, highlightbackground=accent)
            option.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            tk.Radiobutton(
                option,
                text=mode_data["label"],
                variable=self.mode_var,
                value=mode_id,
                bg="#F8FAFC",
                fg=COLORS["ink"],
                activebackground="#F8FAFC",
                selectcolor="#DBEAFE",
                font=("Segoe UI", 11, "bold"),
            ).grid(row=0, column=0, sticky="w")
            tk.Label(
                option,
                text=mode_data["description"],
                bg="#F8FAFC",
                fg=COLORS["muted"],
                font=("Segoe UI", 9),
            ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        actions = tk.Frame(card, bg=COLORS["surface"])
        actions.grid(row=3, column=0, sticky="w", pady=(18, 0))
        self._button(actions, "Join Matchmaking", self._join_matchmaking, bg="primary").grid(row=0, column=0, padx=(0, 10))
        self._button(actions, "Back to Login", self._build_login, bg="muted").grid(row=0, column=1)

    def _build_arena(self) -> None:
        self._clear_content()
        wrapper = tk.Frame(self.content, bg=COLORS["bg"])
        wrapper.grid(row=0, column=0, sticky="nsew")
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(2, weight=1)

        top = self._card(wrapper, bg="surface_alt")
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        self.countdown_var = tk.StringVar(value="Waiting for countdown...")
        self._label(top, textvariable=self.countdown_var, size=20, weight="bold", fg="primary", bg="surface_alt").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.latency_var = tk.StringVar(value="Latency: - ms")
        self.mode_badge_var = tk.StringVar(value=f"{self.current_mode_label} | {self._target_word_count()} kata")
        self._label(top, textvariable=self.mode_badge_var, fg="muted", bg="surface_alt").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._label(top, textvariable=self.latency_var, fg="primary", bg="surface_alt", weight="bold").grid(row=0, column=1, sticky="e")

        target_card = self._card(wrapper)
        target_card.grid(row=1, column=0, sticky="ew", pady=(14, 14))
        target_card.columnconfigure(0, weight=1)
        self.target_var = tk.StringVar(value=self.target_text)
        self._label(target_card, "Target Text", weight="bold", fg="red").grid(row=0, column=0, sticky="w")
        self._label(target_card, textvariable=self.target_var, size=13, wraplength=850).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        main = tk.Frame(wrapper, bg=COLORS["bg"])
        main.grid(row=2, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)

        players_card = self._card(main)
        players_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        players_card.columnconfigure(0, weight=1)
        players_card.columnconfigure(1, weight=1)
        self.finish_banner_var = tk.StringVar(value="Belum ada yang finish. Gas duluan.")
        self._label(players_card, textvariable=self.finish_banner_var, weight="bold", fg="amber").grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 8),
        )
        self.player_a_var = tk.StringVar(value="Player A")
        self.player_b_var = tk.StringVar(value="Player B")
        self._label(players_card, textvariable=self.player_a_var, weight="bold").grid(row=1, column=0, sticky="w")
        self._label(players_card, textvariable=self.player_b_var, weight="bold").grid(row=1, column=1, sticky="w")
        self.player_a_progress = ttk.Progressbar(players_card, maximum=100, style="Green.Horizontal.TProgressbar")
        self.player_b_progress = ttk.Progressbar(players_card, maximum=100, style="Red.Horizontal.TProgressbar")
        self.player_a_progress.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(6, 0))
        self.player_b_progress.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))

        input_card = self._card(main)
        input_card.grid(row=1, column=0, columnspan=2, sticky="nsew")
        input_card.columnconfigure(0, weight=1)
        input_card.rowconfigure(1, weight=1)
        self._label(input_card, "Type here", weight="bold").grid(row=0, column=0, sticky="w")
        self.input_text = tk.Text(
            input_card,
            height=8,
            wrap="word",
            font=("Consolas", 14),
            bg="#F8FAFC",
            fg=COLORS["ink"],
            insertbackground=COLORS["red"],
            relief="flat",
            padx=12,
            pady=10,
        )
        self.input_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.input_text.configure(state="disabled")
        self.input_text.bind("<KeyRelease>", self._on_typing)

    def _build_results(self, rankings: list[dict[str, Any]], reason: str, winner: str) -> None:
        self.match_running = False
        self._clear_content()
        card = self._card(self.content)
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)

        my_rank = next((item.get("rank") for item in rankings if item.get("username") == self.username), None)
        headline = "KAMU MENANG!" if my_rank == 1 else f"Pemenang: {winner or '-'}"
        headline_color = "green" if my_rank == 1 else "red"
        self._label(card, headline, size=24, weight="bold", fg=headline_color).grid(row=0, column=0, sticky="w")
        self._label(
            card,
            f"{self.current_mode_label} selesai. Reason: {reason}",
            fg="muted",
        ).grid(row=1, column=0, sticky="w", pady=(4, 16))

        columns = ("rank", "username", "wpm", "accuracy", "score", "finish")
        table = ttk.Treeview(card, columns=columns, show="headings", height=5)
        for column in columns:
            table.heading(column, text=column.title())
            table.column(column, width=120, anchor="center")
        table.grid(row=2, column=0, sticky="ew")

        for item in rankings:
            table.insert(
                "",
                "end",
                values=(
                    item.get("rank"),
                    item.get("username"),
                    item.get("wpm"),
                    item.get("accuracy"),
                    item.get("score"),
                    item.get("finish_time") or "-",
                ),
            )

        actions = tk.Frame(card, bg=COLORS["surface"])
        actions.grid(row=3, column=0, sticky="w", pady=(18, 0))
        self._button(actions, "Rematch", self._request_rematch, bg="red").grid(row=0, column=0, padx=(0, 10))
        self._button(actions, "Cari Lawan Baru", self._join_matchmaking, bg="primary").grid(row=0, column=1, padx=(0, 10))
        self._button(actions, "Back to Login", self._build_login, bg="muted").grid(row=0, column=2)

    def _target_word_count(self) -> int:
        return len([word for word in self.target_text.replace(".", " ").split() if word])

    def _connect(self) -> None:
        username = self.username_var.get().strip()
        if not username:
            messagebox.showerror("Missing username", "Username is required.")
            return
        try:
            self.network.host = self.host_var.get().strip() or DEFAULT_HOST
            self.network.port = int(self.port_var.get())
            self.network.connect_hello(username)
        except Exception as exc:
            messagebox.showerror("Connection failed", str(exc))
            return
        self.username = username
        self.status_var.set("Connected. Waiting for server welcome...")

    def _reconnect(self) -> None:
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("Missing token", "Session token is required for reconnect.")
            return
        try:
            self.network.host = self.host_var.get().strip() or DEFAULT_HOST
            self.network.port = int(self.port_var.get())
            self.network.connect_reconnect(token)
        except Exception as exc:
            messagebox.showerror("Reconnect failed", str(exc))
            return
        self.status_var.set("Reconnect request sent...")

    def _join_matchmaking(self) -> None:
        mode = self.mode_var.get() if hasattr(self, "mode_var") else self.current_mode
        self.current_mode = mode
        self.current_mode_label = GAME_MODES[mode]["label"]
        self.network.send("JOIN_MATCHMAKING", {"mode": mode})
        self.status_var.set(f"Joining {self.current_mode_label} queue...")

    def _request_rematch(self) -> None:
        self.network.send("REMATCH_REQUEST", {})
        self.status_var.set("Rematch requested. Waiting for opponent...")

    def _on_typing(self, _event: tk.Event) -> None:
        if not self.match_running:
            return
        now = time.monotonic()
        if now - self.last_input_send_at < 0.08:
            return
        self.last_input_send_at = now
        typed_text = self.input_text.get("1.0", "end-1c")
        self.network.send("INPUT_UPDATE", {"typed_text": typed_text})

    def _poll_network(self) -> None:
        while True:
            try:
                packet = self.inbox.get_nowait()
            except queue.Empty:
                break
            self._handle_server_packet(packet)
        self.root.after(50, self._poll_network)

    def _handle_server_packet(self, packet: dict[str, Any]) -> None:
        packet_type = packet.get("type")
        payload = packet.get("payload", {})

        if packet_type == "_DISCONNECTED":
            self.match_running = False
            self.status_var.set("Disconnected. Use the saved session token to reconnect.")
            return
        if packet_type == "ERROR":
            self.status_var.set(f"Server error: {payload.get('message', 'unknown error')}")
            return
        if packet_type == "WELCOME":
            self.username = payload.get("username", self.username)
            self.session_token = payload.get("session_token", self.session_token)
            self.network.session_token = self.session_token
            self.status_var.set("Connected. Ready for matchmaking.")
            self._build_matchmaking()
            return
        if packet_type == "QUEUED":
            self.current_mode = payload.get("mode", self.current_mode)
            self.current_mode_label = payload.get("mode_label", self.current_mode_label)
            self.status_var.set(f"Queued in {self.current_mode_label}. Queue size: {payload.get('queue_size', '-')}")
            return
        if packet_type == "MATCH_FOUND":
            self._apply_match_payload(payload)
            self.match_running = False
            self._build_arena()
            self.status_var.set(f"Match found. Room: {self.current_room_id}")
            self._update_players(payload.get("players", []), state="COUNTDOWN", first_finished=None)
            return
        if packet_type == "COUNTDOWN":
            self.countdown_var.set(f"Countdown: {payload.get('remaining', 0)}s")
            return
        if packet_type == "MATCH_START":
            self._apply_match_payload(payload)
            self.match_running = True
            self.countdown_var.set("GO! Jangan kasih kendor.")
            self.status_var.set("Match running.")
            self._enable_typing()
            return
        if packet_type == "PLAYER_FINISHED":
            username = payload.get("username", "-")
            if username == self.username:
                self.finish_banner_var.set("Kamu finish duluan. Tunggu lawan selesai.")
            else:
                self.finish_banner_var.set(f"{username} finish duluan. Kejar akurasi dan skor!")
            return
        if packet_type == "STATE_UPDATE":
            self._apply_match_payload(payload)
            self._update_players(
                payload.get("players", []),
                state=payload.get("state", ""),
                first_finished=payload.get("first_finished"),
            )
            return
        if packet_type == "MATCH_FINISH":
            self._apply_match_payload(payload)
            self.status_var.set("Match finished.")
            self._build_results(
                payload.get("rankings", []),
                payload.get("reason", "-"),
                payload.get("winner", ""),
            )
            return
        if packet_type == "REMATCH_WAITING":
            waiting_for = ", ".join(payload.get("waiting_for", [])) or "server"
            self.status_var.set(
                f"Rematch {payload.get('ready_count')}/{payload.get('needed_count')} ready. Waiting for {waiting_for}."
            )
            return

    def _apply_match_payload(self, payload: dict[str, Any]) -> None:
        self.current_room_id = payload.get("room_id", self.current_room_id)
        self.current_mode = payload.get("mode", self.current_mode)
        self.current_mode_label = payload.get("mode_label", self.current_mode_label)
        self.target_text = payload.get("target_text", self.target_text)
        if hasattr(self, "target_var"):
            self.target_var.set(self.target_text)
        if hasattr(self, "mode_badge_var"):
            word_count = payload.get("word_count", self._target_word_count())
            self.mode_badge_var.set(f"{self.current_mode_label} | {word_count} kata")

    def _enable_typing(self) -> None:
        if hasattr(self, "input_text"):
            self.input_text.configure(state="normal")
            self.input_text.delete("1.0", "end")
            self.input_text.focus_set()

    def _disable_typing(self) -> None:
        if hasattr(self, "input_text"):
            self.input_text.configure(state="disabled")

    def _update_players(self, players: list[dict[str, Any]], *, state: str, first_finished: str | None) -> None:
        self.latest_players = players
        if not players:
            return

        if state == "RUNNING" and not self.match_running:
            self.match_running = True
            self.countdown_var.set("Reconnected. Match running.")
            self._enable_typing()

        labels = []
        for player in players:
            name = player.get("username", "-")
            connected = "online" if player.get("connected") else "offline"
            finished = "FINISH" if player.get("finished") else "typing"
            label = (
                f"{name} | {connected} | {finished} | "
                f"{player.get('wpm', 0)} WPM | "
                f"{player.get('accuracy', 0)}% | "
                f"{player.get('score', 0)} pts"
            )
            labels.append(label)
            if name == self.username and player.get("latency_ms") is not None:
                self.latency_var.set(f"Latency: {player.get('latency_ms')} ms")
            if name == self.username and player.get("finished"):
                self.match_running = False
                self._disable_typing()
                if hasattr(self, "finish_banner_var"):
                    self.finish_banner_var.set("Kamu sudah finish. Menunggu lawan atau hasil akhir.")

        if first_finished and hasattr(self, "finish_banner_var"):
            if first_finished == self.username:
                self.finish_banner_var.set("Kamu finish duluan. Pertahankan posisi!")
            else:
                self.finish_banner_var.set(f"{first_finished} finish duluan. Masih bisa unggul dari skor.")

        if hasattr(self, "player_a_var") and labels:
            self.player_a_var.set(labels[0])
            self.player_a_progress["value"] = float(players[0].get("progress", 0.0)) * 100
        if hasattr(self, "player_b_var") and len(labels) > 1:
            self.player_b_var.set(labels[1])
            self.player_b_progress["value"] = float(players[1].get("progress", 0.0)) * 100

    def _on_close(self) -> None:
        self.network.close()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Jempol Turbo tkinter client.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    root = tk.Tk()
    JempolTurboApp(root, args.host, args.port)
    root.mainloop()


if __name__ == "__main__":
    main()
