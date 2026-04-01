#!/usr/bin/env python3
"""DEADSHIFT — Local multiplayer social deduction game."""

import sys
import math
import time
import threading
import socketio
import pygame

ADMIN_MODE = "--admin" in sys.argv or "-a" in sys.argv

# Parse --server flag: python3 game.py --server 192.168.1.51:3000
_SERVER_OVERRIDE = None
for i, arg in enumerate(sys.argv):
    if arg == "--server" and i + 1 < len(sys.argv):
        _SERVER_OVERRIDE = sys.argv[i + 1]
        break

# ── Config ──────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1024, 768
MAP_W, MAP_H = 1600, 1200
FPS = 60
PLAYER_RADIUS = 16
FLASHLIGHT_RADIUS = 180
INTERACT_RADIUS = 80
MOVE_SPEED = 4
FONT_SIZE = 18
CHAT_MAX = 12

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (60, 60, 60)
DARK_GRAY = (30, 30, 30)
RED = (231, 76, 60)
GREEN = (46, 204, 113)
BLUE = (52, 152, 219)
YELLOW = (243, 156, 18)
AMBER = (255, 191, 0)
DIM_WHITE = (120, 120, 120)
PANEL_BG = (20, 20, 30, 200)

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ── Game State ──────────────────────────────────────────────────────
class GameState:
    def __init__(self):
        self.phase = "menu"  # menu | lobby | playing | meeting | voting | gameover | task
        self.my_id = None
        self.my_role = None
        self.my_tasks = []
        self.room = None
        self.players = {}
        self.positions = {}
        self.task_stations = []
        self.sabotage_stations = []
        self.meeting_button = None
        self.map_size = (MAP_W, MAP_H)
        self.completed_tasks = 0
        self.total_crew_tasks = 0
        self.sabotages_done = 0
        self.sabotages_needed = 3
        self.active_sabotages = []
        self.dead_players = []
        self.chat_log = []
        self.chat_input = ""
        self.vote_players = []
        self.vote_cast = False
        self.vote_result = None
        self.winner = None
        self.effects = []  # visual effects: [{type, x, y, t}]
        self.notification = None
        self.notification_time = 0
        self.name_input = ""
        self.code_input = ""
        self.server_input = _SERVER_OVERRIDE or "localhost:3000"
        self.menu_cursor = 0  # 0=name, 1=code, 2=server, 3=create, 4=join
        self.active_task = None  # current minigame
        self.kill_cooldown = 0
        self.meeting_end_time = 0
        self.vote_end_time = 0
        self.error_msg = ""
        self.my_x = MAP_W / 2
        self.my_y = MAP_H / 2
        self.admin_enabled = False
        self.admin_panel_open = False
        self.god_mode = False
        self.no_fog = False

    def notify(self, msg, duration=3):
        self.notification = msg
        self.notification_time = time.time() + duration

    def load_game_state(self, data):
        self.my_role = data.get("myRole")
        self.my_tasks = data.get("myTasks", [])
        self.task_stations = data.get("taskStations", [])
        self.sabotage_stations = data.get("sabotageStations", [])
        self.meeting_button = data.get("meetingButton")
        self.map_size = (data["mapSize"]["w"], data["mapSize"]["h"])
        self.completed_tasks = data.get("completedTasks", 0)
        self.total_crew_tasks = data.get("totalCrewTasks", 0)
        self.sabotages_done = data.get("sabotagesDone", 0)
        self.sabotages_needed = data.get("sabotagesNeeded", 3)
        self.active_sabotages = data.get("activeSabotages", [])
        self.dead_players = data.get("deadPlayers", [])
        self.winner = data.get("winner")
        if data.get("players"):
            for p in data["players"]:
                self.positions[p["id"]] = p


gs = GameState()

# ── Minigame State ──────────────────────────────────────────────────
class MiniGame:
    """Simple task minigames."""
    def __init__(self, task_type, station_id):
        self.task_type = task_type
        self.station_id = station_id
        self.done = False
        self.progress = 0
        self.target = 100
        self.data = {}

        if task_type == "cable":
            # Connect 4 color pairs by clicking them in order
            colors = [(231,76,60), (52,152,219), (46,204,113), (243,156,18)]
            self.data["pairs"] = colors
            self.data["connected"] = 0
            self.data["total"] = 4
            self.target = 4
        elif task_type == "psu":
            # Hold click on a bar to fill it
            self.data["fill"] = 0
            self.target = 100
        elif task_type == "temp":
            # Click on hot servers (red) to cool them, avoid green ones
            import random
            servers = []
            for i in range(8):
                servers.append({"hot": random.random() > 0.5, "cooled": False})
            self.data["servers"] = servers
            self.data["cooled"] = 0
            self.data["total"] = sum(1 for s in servers if s["hot"])
            if self.data["total"] == 0:
                self.data["servers"][0]["hot"] = True
                self.data["total"] = 1
            self.target = self.data["total"]
        elif task_type == "badge":
            # Type a 4-digit code
            import random
            self.data["code"] = "".join(str(random.randint(0,9)) for _ in range(4))
            self.data["input"] = ""
            self.target = 4

    def update(self, events, mouse_pos, mouse_held):
        if self.done:
            return True

        cx, cy = WIDTH // 2, HEIGHT // 2
        panel_x, panel_y = cx - 200, cy - 150
        local_mx = mouse_pos[0] - panel_x
        local_my = mouse_pos[1] - panel_y

        if self.task_type == "cable":
            for ev in events:
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    # Click zones: 4 ports on left, 4 on right
                    idx = self.data["connected"]
                    if idx < self.data["total"]:
                        # Click anywhere to connect next pair
                        self.data["connected"] += 1
                        self.progress = self.data["connected"]
                        if self.data["connected"] >= self.data["total"]:
                            self.done = True

        elif self.task_type == "psu":
            if mouse_held:
                # Check if mouse is on the fill bar area
                if 50 < local_mx < 350 and 100 < local_my < 200:
                    self.data["fill"] = min(100, self.data["fill"] + 1.5)
                    self.progress = self.data["fill"]
                    if self.data["fill"] >= 100:
                        self.done = True

        elif self.task_type == "temp":
            for ev in events:
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    # 8 server boxes in a 4x2 grid
                    for i, srv in enumerate(self.data["servers"]):
                        sx = 40 + (i % 4) * 90
                        sy = 80 + (i // 4) * 100
                        if sx < local_mx < sx + 70 and sy < local_my < sy + 70:
                            if srv["hot"] and not srv["cooled"]:
                                srv["cooled"] = True
                                self.data["cooled"] += 1
                                self.progress = self.data["cooled"]
                                if self.data["cooled"] >= self.data["total"]:
                                    self.done = True

        elif self.task_type == "badge":
            for ev in events:
                if ev.type == pygame.KEYDOWN:
                    if ev.unicode and ev.unicode.isdigit() and len(self.data["input"]) < 4:
                        self.data["input"] += ev.unicode
                        self.progress = len(self.data["input"])
                        if self.data["input"] == self.data["code"]:
                            self.done = True
                        elif len(self.data["input"]) >= 4:
                            # Wrong code — reset
                            self.data["input"] = ""
                            self.progress = 0
                    elif ev.key == pygame.K_BACKSPACE:
                        self.data["input"] = self.data["input"][:-1]
                        self.progress = len(self.data["input"])

        return self.done

    def draw(self, screen, font):
        cx, cy = WIDTH // 2, HEIGHT // 2
        panel = pygame.Rect(cx - 200, cy - 150, 400, 300)
        pygame.draw.rect(screen, DARK_GRAY, panel)
        pygame.draw.rect(screen, WHITE, panel, 2)

        title_map = {"cable": "CONNECT CABLES", "psu": "INSTALL PSU", "temp": "COOL SERVERS", "badge": "SCAN BADGE"}
        title = font.render(title_map.get(self.task_type, "TASK"), True, AMBER)
        screen.blit(title, (cx - title.get_width() // 2, cy - 135))

        px, py = panel.x, panel.y

        if self.task_type == "cable":
            for i in range(self.data["total"]):
                color = self.data["pairs"][i]
                done = i < self.data["connected"]
                lx, ly = px + 40, py + 70 + i * 50
                rx, ry = px + 360, py + 70 + i * 50
                pygame.draw.circle(screen, color, (lx, ly), 12)
                pygame.draw.circle(screen, color, (rx, ry), 12)
                if done:
                    pygame.draw.line(screen, color, (lx, ly), (rx, ry), 3)
                else:
                    pygame.draw.line(screen, GRAY, (lx, ly), (rx, ry), 1)
            hint = font.render("Click to connect next pair", True, DIM_WHITE)
            screen.blit(hint, (cx - hint.get_width() // 2, cy + 120))

        elif self.task_type == "psu":
            bar_rect = pygame.Rect(px + 50, py + 100, 300, 80)
            pygame.draw.rect(screen, GRAY, bar_rect)
            fill_w = int(self.data["fill"] / 100 * 300)
            pygame.draw.rect(screen, GREEN, (px + 50, py + 100, fill_w, 80))
            pygame.draw.rect(screen, WHITE, bar_rect, 2)
            hint = font.render("HOLD CLICK on bar to install", True, DIM_WHITE)
            screen.blit(hint, (cx - hint.get_width() // 2, cy + 120))

        elif self.task_type == "temp":
            for i, srv in enumerate(self.data["servers"]):
                sx = px + 40 + (i % 4) * 90
                sy = py + 80 + (i // 4) * 100
                color = RED if srv["hot"] and not srv["cooled"] else GREEN if srv["cooled"] else (60, 60, 80)
                pygame.draw.rect(screen, color, (sx, sy, 70, 70))
                pygame.draw.rect(screen, WHITE, (sx, sy, 70, 70), 1)
                lbl = font.render(f"S{i+1}", True, WHITE)
                screen.blit(lbl, (sx + 25, sy + 25))
            hint = font.render("Click RED servers to cool them", True, DIM_WHITE)
            screen.blit(hint, (cx - hint.get_width() // 2, cy + 120))

        elif self.task_type == "badge":
            code_display = font.render(f"Code: {self.data['code']}", True, AMBER)
            screen.blit(code_display, (cx - code_display.get_width() // 2, cy - 60))
            input_display = font.render(f"Enter: {self.data['input']}_", True, WHITE)
            screen.blit(input_display, (cx - input_display.get_width() // 2, cy + 10))
            hint = font.render("Type the code shown above", True, DIM_WHITE)
            screen.blit(hint, (cx - hint.get_width() // 2, cy + 120))

        # ESC hint
        esc = font.render("[ESC] cancel", True, DIM_WHITE)
        screen.blit(esc, (cx - esc.get_width() // 2, cy + 140))


# ── Networking ──────────────────────────────────────────────────────
sio = socketio.Client(reconnection=True)

@sio.on("player:joined")
def on_player_joined(data):
    gs.room = data.get("room")
    gs.notify("Player joined!")

@sio.on("player:updated")
def on_player_updated(data):
    gs.room = data.get("room")

@sio.on("player:left")
def on_player_left(data):
    gs.room = data.get("room")
    gs.notify("Player left")

@sio.on("game:start")
def on_game_start(data):
    gs.load_game_state(data)
    gs.phase = "playing"
    gs.kill_cooldown = 0
    # Find my position
    for p in data.get("players", []):
        if p["id"] == gs.my_id:
            gs.my_x = p["x"]
            gs.my_y = p["y"]
            break
    role_text = "IMPOSTOR" if gs.my_role == "impostor" else "CREW"
    gs.notify(f"You are {role_text}!", 5)

@sio.on("game:resume")
def on_game_resume(data):
    gs.load_game_state(data)
    gs.phase = "playing"
    gs.active_task = None

@sio.on("positions")
def on_positions(data):
    gs.positions = data

@sio.on("sabotage:effect")
def on_sabotage_effect(data):
    gs.effects.append({
        "type": data["type"], "x": data["x"], "y": data["y"],
        "t": time.time(), "duration": 3
    })
    if data["type"] == "blackout":
        gs.notify("POWER OUTAGE!", 3)
    elif data["type"] == "alarm":
        gs.notify("OVERHEAT ALARM!", 3)
    else:
        gs.notify("SPARKS DETECTED!", 3)

@sio.on("killed")
def on_killed(data):
    gs.notify("YOU WERE ELIMINATED!", 5)

@sio.on("body:found")
def on_body_found(data):
    gs.effects.append({
        "type": "body", "x": data["x"], "y": data["y"],
        "t": time.time(), "duration": 60, "name": data["name"], "color": data["color"]
    })

@sio.on("meeting:started")
def on_meeting_started(data):
    gs.phase = "meeting"
    gs.room = data.get("room")
    gs.chat_log = []
    gs.chat_input = ""
    gs.vote_cast = False
    gs.vote_result = None
    gs.active_task = None
    caller = data.get("caller", {})
    gs.meeting_end_time = time.time() + data.get("duration", 45000) / 1000
    gs.notify(f"EMERGENCY MEETING by {caller.get('name', '???')}!", 5)

@sio.on("voting:started")
def on_voting_started(data):
    gs.phase = "voting"
    gs.vote_players = data.get("players", [])
    gs.vote_cast = False
    gs.vote_end_time = time.time() + data.get("duration", 15000) / 1000

@sio.on("chat:message")
def on_chat_message(data):
    gs.chat_log.append(data)
    if len(gs.chat_log) > 50:
        gs.chat_log = gs.chat_log[-50:]

@sio.on("vote:cast")
def on_vote_cast(data):
    pass  # could show a checkmark

@sio.on("vote:result")
def on_vote_result(data):
    gs.vote_result = data
    ejected = data.get("ejected")
    if ejected:
        gs.notify(f"{ejected['name']} was ejected! ({ejected['role'].upper()})", 5)
    else:
        gs.notify("No one was ejected (tie/skip)", 4)

@sio.on("game:over")
def on_game_over(data):
    gs.phase = "gameover"
    gs.winner = data.get("winner")
    impostors = data.get("impostors", [])
    names = ", ".join(i["name"] for i in impostors)
    gs.notify(f"{'CREW' if gs.winner == 'crew' else 'IMPOSTOR'} WINS! Impostor: {names}", 10)

@sio.on("kicked")
def on_kicked():
    gs.phase = "menu"
    gs.notify("You were kicked from the room", 4)


def connect_and_create(server, name):
    try:
        sio.connect(f"http://{server}", transports=["websocket"])
        gs.my_id = sio.sid
        resp = sio.call("create", {"name": name, "maxPlayers": 8})
        if resp and resp.get("ok"):
            gs.room = resp["room"]
            gs.phase = "lobby"
            gs.code_input = resp["room"]["code"]
            if ADMIN_MODE:
                admin_resp = sio.call("admin:enable", {})
                gs.admin_enabled = admin_resp and admin_resp.get("ok")
        else:
            gs.error_msg = resp.get("error", "Failed to create")
    except Exception as e:
        gs.error_msg = str(e)[:60]

def connect_and_join(server, name, code):
    try:
        if not sio.connected:
            sio.connect(f"http://{server}", transports=["websocket"])
            gs.my_id = sio.sid
        resp = sio.call("join", {"name": name, "code": code})
        if resp and resp.get("ok"):
            gs.room = resp["room"]
            gs.phase = "lobby"
        else:
            gs.error_msg = resp.get("error", "Failed to join")
    except Exception as e:
        gs.error_msg = str(e)[:60]


# ── Drawing ─────────────────────────────────────────────────────────
def draw_menu(screen, font, big_font):
    screen.fill((10, 10, 20))

    # Title
    title = big_font.render("DEADSHIFT", True, RED)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 60))
    sub = font.render("Local Multiplayer Social Deduction", True, DIM_WHITE)
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 110))

    cx = WIDTH // 2
    y = 180

    fields = [
        ("Name", gs.name_input, 0),
        ("Room Code", gs.code_input, 1),
        ("Server", gs.server_input, 2),
    ]

    for label, value, idx in fields:
        color = AMBER if gs.menu_cursor == idx else WHITE
        lbl = font.render(f"{label}:", True, color)
        screen.blit(lbl, (cx - 160, y))
        box = pygame.Rect(cx - 10, y - 4, 200, 28)
        pygame.draw.rect(screen, DARK_GRAY, box)
        border_color = AMBER if gs.menu_cursor == idx else GRAY
        pygame.draw.rect(screen, border_color, box, 1)
        val = font.render(value + ("_" if gs.menu_cursor == idx else ""), True, WHITE)
        screen.blit(val, (cx - 5, y))
        y += 50

    # Buttons
    for i, (label, idx) in enumerate([("[ CREATE ROOM ]", 3), ("[ JOIN ROOM ]", 4)]):
        color = AMBER if gs.menu_cursor == idx else WHITE
        btn = font.render(label, True, color)
        screen.blit(btn, (cx - btn.get_width() // 2, y + i * 45))

    # Error
    if gs.error_msg:
        err = font.render(gs.error_msg, True, RED)
        screen.blit(err, (cx - err.get_width() // 2, y + 120))

    # Instructions
    inst = font.render("TAB=next field  ENTER=select  Type to fill", True, DIM_WHITE)
    screen.blit(inst, (cx - inst.get_width() // 2, HEIGHT - 40))


def draw_lobby(screen, font, big_font):
    screen.fill((10, 10, 20))

    if not gs.room:
        return

    title = big_font.render(f"ROOM: {gs.room['code']}", True, AMBER)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))

    sub = font.render("Share this code with your coworkers!", True, DIM_WHITE)
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 90))

    y = 140
    for p in gs.room.get("players", []):
        color = hex_to_rgb(p.get("color", "#ffffff"))
        dot = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.circle(dot, color, (10, 10), 10)
        screen.blit(dot, (WIDTH // 2 - 120, y))

        name_text = p.get("name", "???")
        if p["id"] == gs.room.get("host"):
            name_text += " (HOST)"
        ready_text = " READY" if p.get("ready") else ""
        label = font.render(f"{name_text}{ready_text}", True, GREEN if p.get("ready") else WHITE)
        screen.blit(label, (WIDTH // 2 - 90, y))
        y += 35

    y += 20
    if gs.room.get("host") == gs.my_id:
        start_btn = font.render("[ PRESS ENTER TO START ]", True, AMBER)
        screen.blit(start_btn, (WIDTH // 2 - start_btn.get_width() // 2, y))
    else:
        ready_btn = font.render("[ PRESS R TO TOGGLE READY ]", True, AMBER)
        screen.blit(ready_btn, (WIDTH // 2 - ready_btn.get_width() // 2, y))

    info = font.render(f"Players: {len(gs.room.get('players', []))}/8  |  Need 3+ to start", True, DIM_WHITE)
    screen.blit(info, (WIDTH // 2 - info.get_width() // 2, HEIGHT - 40))


def draw_game(screen, font):
    screen.fill(BLACK)

    # Camera offset — center on player
    cam_x = gs.my_x - WIDTH // 2
    cam_y = gs.my_y - HEIGHT // 2

    # Draw map background (dark with grid)
    for gx in range(0, MAP_W, 100):
        sx = gx - cam_x
        pygame.draw.line(screen, (15, 15, 25), (sx, -cam_y), (sx, MAP_H - cam_y), 1)
    for gy in range(0, MAP_H, 100):
        sy = gy - cam_y
        pygame.draw.line(screen, (15, 15, 25), (-cam_x, sy), (MAP_W - cam_x, sy), 1)

    # Map border
    border = pygame.Rect(-cam_x, -cam_y, MAP_W, MAP_H)
    pygame.draw.rect(screen, (40, 40, 60), border, 2)

    # Draw task stations
    for station in gs.task_stations:
        sx = station["x"] - cam_x
        sy = station["y"] - cam_y
        # Check if this station has a task for me
        has_task = any(t["stationId"] == station["id"] and not t.get("done") for t in gs.my_tasks)
        color = YELLOW if has_task else (40, 40, 50)
        rect = pygame.Rect(sx - 30, sy - 30, 60, 60)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, WHITE, rect, 1)
        lbl = font.render(station.get("label", "")[:10], True, WHITE)
        screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 50))

    # Draw sabotage stations (only for impostor)
    if gs.my_role == "impostor":
        for station in gs.sabotage_stations:
            sx = station["x"] - cam_x
            sy = station["y"] - cam_y
            done = station["id"] in gs.active_sabotages
            color = (100, 20, 20) if not done else (40, 40, 40)
            rect = pygame.Rect(sx - 25, sy - 25, 50, 50)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, RED, rect, 1)
            icon = font.render("SAB" if not done else "X", True, RED)
            screen.blit(icon, (sx - icon.get_width() // 2, sy - icon.get_height() // 2))

    # Draw meeting button
    if gs.meeting_button:
        bx = gs.meeting_button["x"] - cam_x
        by = gs.meeting_button["y"] - cam_y
        pygame.draw.circle(screen, (150, 30, 30), (int(bx), int(by)), 30)
        pygame.draw.circle(screen, RED, (int(bx), int(by)), 30, 2)
        icon = font.render("!", True, WHITE)
        screen.blit(icon, (bx - icon.get_width() // 2, by - icon.get_height() // 2))

    # Draw effects (bodies, sabotage)
    now = time.time()
    gs.effects = [e for e in gs.effects if now - e["t"] < e["duration"]]
    for eff in gs.effects:
        ex = eff["x"] - cam_x
        ey = eff["y"] - cam_y
        if eff["type"] == "body":
            pygame.draw.circle(screen, hex_to_rgb(eff.get("color", "#ff0000")), (int(ex), int(ey)), 12)
            pygame.draw.line(screen, RED, (int(ex) - 8, int(ey) - 8), (int(ex) + 8, int(ey) + 8), 2)
            pygame.draw.line(screen, RED, (int(ex) + 8, int(ey) - 8), (int(ex) - 8, int(ey) + 8), 2)
        elif eff["type"] == "blackout":
            alpha = max(0, 1 - (now - eff["t"]) / eff["duration"])
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(200 * alpha)))
            screen.blit(overlay, (0, 0))

    # Draw other players
    am_alive = gs.my_id not in gs.dead_players
    for pid, p in gs.positions.items():
        if pid == gs.my_id:
            continue
        px = p["x"] - cam_x
        py = p["y"] - cam_y
        if not p.get("alive", True):
            continue

        dist = math.hypot(p["x"] - gs.my_x, p["y"] - gs.my_y)
        # Only show within flashlight radius (or always if dead/ghost)
        if am_alive and not gs.no_fog and dist > FLASHLIGHT_RADIUS * 1.5:
            continue

        color = hex_to_rgb(p.get("color", "#ffffff"))
        pygame.draw.circle(screen, color, (int(px), int(py)), PLAYER_RADIUS)
        name = font.render(p.get("name", ""), True, WHITE)
        screen.blit(name, (px - name.get_width() // 2, py - PLAYER_RADIUS - 18))

    # Draw me
    if gs.my_id in gs.positions:
        my_p = gs.positions[gs.my_id]
        my_color = hex_to_rgb(my_p.get("color", "#ffffff"))
    else:
        my_color = WHITE
    mx = WIDTH // 2
    my = HEIGHT // 2
    pygame.draw.circle(screen, my_color, (mx, my), PLAYER_RADIUS)
    pygame.draw.circle(screen, WHITE, (mx, my), PLAYER_RADIUS, 2)

    # Flashlight effect — darken everything outside radius
    if am_alive and not gs.no_fog:
        fog = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        fog.fill((0, 0, 0, 180))
        # Cut out a circle around player
        pygame.draw.circle(fog, (0, 0, 0, 0), (mx, my), FLASHLIGHT_RADIUS)
        # Gradient edge
        for r in range(FLASHLIGHT_RADIUS, FLASHLIGHT_RADIUS + 40):
            alpha = int(180 * (r - FLASHLIGHT_RADIUS) / 40)
            pygame.draw.circle(fog, (0, 0, 0, alpha), (mx, my), r, 1)
        screen.blit(fog, (0, 0))

    # ── HUD ───────────────────────────────────────────────────────
    # Role badge
    role_color = RED if gs.my_role == "impostor" else GREEN
    role_text = "IMPOSTOR" if gs.my_role == "impostor" else "CREW"
    badge = font.render(role_text, True, role_color)
    screen.blit(badge, (10, 10))

    # Task progress (crew)
    if gs.my_role == "crew":
        my_done = sum(1 for t in gs.my_tasks if t.get("done"))
        my_total = len(gs.my_tasks)
        task_text = font.render(f"Tasks: {my_done}/{my_total}", True, WHITE)
        screen.blit(task_text, (10, 35))

        # Team progress bar
        if gs.total_crew_tasks > 0:
            bar_w = 150
            bar_h = 12
            fill = int(gs.completed_tasks / gs.total_crew_tasks * bar_w)
            pygame.draw.rect(screen, GRAY, (10, 58, bar_w, bar_h))
            pygame.draw.rect(screen, GREEN, (10, 58, fill, bar_h))
            pygame.draw.rect(screen, WHITE, (10, 58, bar_w, bar_h), 1)
            pct = font.render(f"Team: {gs.completed_tasks}/{gs.total_crew_tasks}", True, DIM_WHITE)
            screen.blit(pct, (10, 73))

    # Sabotage count (impostor)
    if gs.my_role == "impostor":
        sab_text = font.render(f"Sabotaged: {gs.sabotages_done}/{gs.sabotages_needed}", True, RED)
        screen.blit(sab_text, (10, 35))
        hint = font.render("[Q] Kill nearby  |  Go to SAB stations", True, DIM_WHITE)
        screen.blit(hint, (10, 58))

    # Controls hint
    controls = font.render("WASD=move  E=interact  SPACE=meeting  ESC=menu", True, DIM_WHITE)
    screen.blit(controls, (WIDTH // 2 - controls.get_width() // 2, HEIGHT - 25))

    # Interact prompt
    nearby = get_nearby_interactable()
    if nearby:
        prompt = font.render(f"[E] {nearby['label']}", True, AMBER)
        screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + 50))

    # Kill prompt (impostor)
    if gs.my_role == "impostor" and gs.kill_cooldown <= 0:
        target = get_nearby_kill_target()
        if target:
            prompt = font.render(f"[Q] Kill {target['name']}", True, RED)
            screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + 75))


def draw_meeting(screen, font, big_font):
    screen.fill((10, 10, 20))

    title = big_font.render("EMERGENCY MEETING", True, RED)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 20))

    remaining = max(0, gs.meeting_end_time - time.time())
    timer = font.render(f"Discussion: {int(remaining)}s", True, AMBER)
    screen.blit(timer, (WIDTH // 2 - timer.get_width() // 2, 60))

    # Chat log
    y = 90
    visible = gs.chat_log[-CHAT_MAX:]
    for msg in visible:
        color = hex_to_rgb(msg.get("color", "#ffffff"))
        name_surf = font.render(f"{msg['name']}: ", True, color)
        msg_surf = font.render(msg.get("message", ""), True, WHITE)
        screen.blit(name_surf, (20, y))
        screen.blit(msg_surf, (20 + name_surf.get_width(), y))
        y += 22

    # Chat input
    input_y = HEIGHT - 50
    pygame.draw.rect(screen, DARK_GRAY, (10, input_y, WIDTH - 20, 30))
    pygame.draw.rect(screen, AMBER, (10, input_y, WIDTH - 20, 30), 1)
    input_text = font.render(f"> {gs.chat_input}_", True, WHITE)
    screen.blit(input_text, (15, input_y + 5))

    hint = font.render("Type message + ENTER to send", True, DIM_WHITE)
    screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 20))


def draw_voting(screen, font, big_font):
    screen.fill((10, 10, 20))

    title = big_font.render("VOTE", True, RED)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 20))

    remaining = max(0, gs.vote_end_time - time.time())
    timer = font.render(f"Time: {int(remaining)}s", True, AMBER)
    screen.blit(timer, (WIDTH // 2 - timer.get_width() // 2, 55))

    if gs.vote_cast:
        cast_msg = font.render("Vote cast! Waiting for others...", True, GREEN)
        screen.blit(cast_msg, (WIDTH // 2 - cast_msg.get_width() // 2, 80))

    y = 110
    for i, p in enumerate(gs.vote_players):
        color = hex_to_rgb(p.get("color", "#ffffff"))
        rect = pygame.Rect(WIDTH // 2 - 150, y, 300, 35)
        pygame.draw.rect(screen, DARK_GRAY, rect)
        pygame.draw.rect(screen, color, rect, 2)
        pygame.draw.circle(screen, color, (rect.x + 18, rect.y + 18), 10)
        label = font.render(p.get("name", "???"), True, WHITE)
        screen.blit(label, (rect.x + 38, rect.y + 7))
        key_hint = font.render(str(i + 1), True, AMBER)
        screen.blit(key_hint, (rect.x + rect.width - 25, rect.y + 7))
        y += 42

    # Skip vote
    skip_rect = pygame.Rect(WIDTH // 2 - 100, y + 10, 200, 35)
    pygame.draw.rect(screen, DARK_GRAY, skip_rect)
    pygame.draw.rect(screen, DIM_WHITE, skip_rect, 2)
    skip_label = font.render("[0] SKIP VOTE", True, DIM_WHITE)
    screen.blit(skip_label, (WIDTH // 2 - skip_label.get_width() // 2, y + 17))

    # Vote result
    if gs.vote_result:
        ejected = gs.vote_result.get("ejected")
        vy = HEIGHT - 80
        if ejected:
            result_text = f"{ejected['name']} was ejected. Role: {ejected['role'].upper()}"
            result_color = RED
        else:
            result_text = "No one was ejected."
            result_color = DIM_WHITE
        result = font.render(result_text, True, result_color)
        screen.blit(result, (WIDTH // 2 - result.get_width() // 2, vy))


def draw_gameover(screen, font, big_font):
    screen.fill((10, 10, 20))

    winner_text = "CREW WINS!" if gs.winner == "crew" else "IMPOSTOR WINS!"
    color = GREEN if gs.winner == "crew" else RED
    title = big_font.render(winner_text, True, color)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 60))

    hint = font.render("Press ENTER to return to lobby", True, DIM_WHITE)
    screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT // 2 + 20))


def draw_admin_panel(screen, font):
    """Admin/QA overlay panel."""
    if not gs.admin_enabled or not gs.admin_panel_open:
        # Just show the toggle hint
        if gs.admin_enabled:
            hint = font.render("[F1] Admin Panel", True, (255, 100, 255))
            screen.blit(hint, (WIDTH - hint.get_width() - 10, 10))
        return

    panel_w, panel_h = 300, 340
    panel = pygame.Rect(WIDTH - panel_w - 10, 40, panel_w, panel_h)
    overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    overlay.fill((10, 0, 20, 220))
    screen.blit(overlay, panel.topleft)
    pygame.draw.rect(screen, (255, 100, 255), panel, 2)

    x, y = panel.x + 10, panel.y + 8
    purple = (255, 100, 255)
    title = font.render("ADMIN PANEL", True, purple)
    screen.blit(title, (x, y)); y += 24

    cmds = [
        (f"[F2] Role: {gs.my_role or '?'}", "Switch role"),
        (f"[F3] Fog: {'OFF' if gs.no_fog else 'ON'}", "Toggle fog"),
        (f"[F4] God: {'ON' if gs.god_mode else 'OFF'}", "No proximity"),
        ("[F5] Spawn 3 bots", "Add bots"),
        ("[F6] Force meeting", ""),
        ("[F7] Skip all tasks", "Crew win"),
        ("[F8] Force win: crew", ""),
        ("[F9] Force win: impostor", ""),
        ("[F10] TP to center", ""),
    ]
    for label, desc in cmds:
        line = font.render(label, True, WHITE)
        screen.blit(line, (x, y))
        if desc:
            d = font.render(desc, True, DIM_WHITE)
            screen.blit(d, (x + 180, y))
        y += 24

    phase_text = font.render(f"Phase: {gs.phase} | Pos: {int(gs.my_x)},{int(gs.my_y)}", True, DIM_WHITE)
    screen.blit(phase_text, (x, y)); y += 20
    players_alive = sum(1 for p in gs.positions.values() if p.get("alive"))
    total = len(gs.positions)
    stats = font.render(f"Alive: {players_alive}/{total} | Tasks: {gs.completed_tasks}/{gs.total_crew_tasks}", True, DIM_WHITE)
    screen.blit(stats, (x, y))


def handle_admin_keys(ev):
    """Handle admin hotkeys. Returns True if event was consumed."""
    if not gs.admin_enabled:
        return False
    if ev.type != pygame.KEYDOWN:
        return False

    if ev.key == pygame.K_F1:
        gs.admin_panel_open = not gs.admin_panel_open
        return True
    if ev.key == pygame.K_F2:
        new_role = "crew" if gs.my_role == "impostor" else "impostor"
        resp = sio.call("admin:role", {"role": new_role})
        if resp and resp.get("ok"):
            gs.my_role = resp["role"]
            gs.notify(f"Role → {gs.my_role.upper()}", 2)
        return True
    if ev.key == pygame.K_F3:
        gs.no_fog = not gs.no_fog
        gs.notify(f"Fog {'OFF' if gs.no_fog else 'ON'}", 2)
        return True
    if ev.key == pygame.K_F4:
        resp = sio.call("admin:god", {})
        if resp and resp.get("ok"):
            gs.god_mode = resp["godMode"]
            gs.notify(f"God mode {'ON' if gs.god_mode else 'OFF'}", 2)
        return True
    if ev.key == pygame.K_F5:
        resp = sio.call("admin:bots", {"count": 3})
        if resp and resp.get("ok"):
            gs.room = resp["room"]
            gs.notify("Spawned 3 bots", 2)
        return True
    if ev.key == pygame.K_F6:
        sio.call("admin:meeting", {})
        return True
    if ev.key == pygame.K_F7:
        sio.call("admin:skip_tasks", {})
        gs.notify("Tasks skipped!", 2)
        return True
    if ev.key == pygame.K_F8:
        sio.call("admin:win", {"side": "crew"})
        return True
    if ev.key == pygame.K_F9:
        sio.call("admin:win", {"side": "impostor"})
        return True
    if ev.key == pygame.K_F10:
        gs.my_x, gs.my_y = MAP_W / 2, MAP_H / 2
        sio.call("admin:tp", {"x": gs.my_x, "y": gs.my_y})
        gs.notify("TP → center", 1)
        return True

    return False


def draw_notification(screen, font):
    if gs.notification and time.time() < gs.notification_time:
        text = font.render(gs.notification, True, AMBER)
        bg = pygame.Rect(WIDTH // 2 - text.get_width() // 2 - 10, 10,
                         text.get_width() + 20, 30)
        pygame.draw.rect(screen, (20, 20, 30), bg)
        pygame.draw.rect(screen, AMBER, bg, 1)
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, 15))


# ── Interaction Helpers ─────────────────────────────────────────────
def get_nearby_interactable():
    """Find the nearest interactable thing."""
    best = None
    best_dist = INTERACT_RADIUS

    # Task stations (crew)
    if gs.my_role == "crew":
        for station in gs.task_stations:
            has_task = any(t["stationId"] == station["id"] and not t.get("done") for t in gs.my_tasks)
            if not has_task:
                continue
            dist = math.hypot(gs.my_x - station["x"], gs.my_y - station["y"])
            if dist < best_dist:
                best_dist = dist
                best = {"type": "task", "station": station, "label": station.get("label", "Task")}

    # Sabotage stations (impostor)
    if gs.my_role == "impostor":
        for station in gs.sabotage_stations:
            if station["id"] in gs.active_sabotages:
                continue
            dist = math.hypot(gs.my_x - station["x"], gs.my_y - station["y"])
            if dist < best_dist:
                best_dist = dist
                best = {"type": "sabotage", "station": station, "label": f"Sabotage: {station.get('label', '')}"}

    # Meeting button
    if gs.meeting_button:
        dist = math.hypot(gs.my_x - gs.meeting_button["x"], gs.my_y - gs.meeting_button["y"])
        if dist < best_dist:
            best = {"type": "meeting", "label": "Emergency Meeting"}

    return best


def get_nearby_kill_target():
    """Find nearest alive crew member for impostor kill."""
    if gs.my_role != "impostor":
        return None
    best = None
    best_dist = INTERACT_RADIUS
    for pid, p in gs.positions.items():
        if pid == gs.my_id or not p.get("alive", True):
            continue
        dist = math.hypot(gs.my_x - p["x"], gs.my_y - p["y"])
        if dist < best_dist:
            best_dist = dist
            best = {"id": pid, "name": p.get("name", "???"), "dist": dist}
    return best


# ── Main Loop ───────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("DEADSHIFT")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", FONT_SIZE)
    big_font = pygame.font.SysFont("monospace", 42, bold=True)

    running = True
    last_move_send = 0

    while running:
        dt = clock.tick(FPS) / 1000
        events = pygame.event.get()
        mouse_pos = pygame.mouse.get_pos()
        mouse_held = pygame.mouse.get_pressed()[0]
        keys = pygame.key.get_pressed()

        for ev in events:
            if ev.type == pygame.QUIT:
                running = False
            # Admin keys consume event if handled
            if ADMIN_MODE:
                handle_admin_keys(ev)

        # ── MENU ──────────────────────────────────────────────────
        if gs.phase == "menu":
            for ev in events:
                if ev.type == pygame.KEYDOWN:
                    gs.error_msg = ""
                    if ev.key == pygame.K_TAB:
                        gs.menu_cursor = (gs.menu_cursor + 1) % 5
                    elif ev.key == pygame.K_RETURN:
                        if gs.menu_cursor == 3:  # Create
                            threading.Thread(target=connect_and_create,
                                             args=(gs.server_input, gs.name_input or "Player"),
                                             daemon=True).start()
                        elif gs.menu_cursor == 4:  # Join
                            threading.Thread(target=connect_and_join,
                                             args=(gs.server_input, gs.name_input or "Player", gs.code_input),
                                             daemon=True).start()
                    elif ev.key == pygame.K_BACKSPACE:
                        if gs.menu_cursor == 0:
                            gs.name_input = gs.name_input[:-1]
                        elif gs.menu_cursor == 1:
                            gs.code_input = gs.code_input[:-1]
                        elif gs.menu_cursor == 2:
                            gs.server_input = gs.server_input[:-1]
                    elif ev.unicode and ev.unicode.isprintable():
                        if gs.menu_cursor == 0 and len(gs.name_input) < 16:
                            gs.name_input += ev.unicode
                        elif gs.menu_cursor == 1 and len(gs.code_input) < 6:
                            gs.code_input += ev.unicode.upper()
                        elif gs.menu_cursor == 2 and len(gs.server_input) < 30:
                            gs.server_input += ev.unicode

            draw_menu(screen, font, big_font)

        # ── LOBBY ─────────────────────────────────────────────────
        elif gs.phase == "lobby":
            for ev in events:
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_RETURN and gs.room and gs.room.get("host") == gs.my_id:
                        resp = sio.call("start", {})
                        if resp and not resp.get("ok"):
                            gs.error_msg = resp.get("error", "")
                            gs.notify(gs.error_msg, 3)
                    elif ev.key == pygame.K_r:
                        sio.call("ready", {})
                    elif ev.key == pygame.K_ESCAPE:
                        sio.emit("leave")
                        gs.phase = "menu"
            draw_lobby(screen, font, big_font)

        # ── PLAYING ───────────────────────────────────────────────
        elif gs.phase == "playing":
            am_alive = gs.my_id not in gs.dead_players

            # Active minigame
            if gs.active_task:
                completed = gs.active_task.update(events, mouse_pos, mouse_held)
                if completed:
                    sio.call("task:complete", {"stationId": gs.active_task.station_id})
                    gs.notify("Task complete!", 2)
                    gs.active_task = None
                for ev in events:
                    if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                        gs.active_task = None

                draw_game(screen, font)
                if gs.active_task:
                    gs.active_task.draw(screen, font)
            else:
                # Movement
                if am_alive:
                    dx, dy = 0, 0
                    if keys[pygame.K_w] or keys[pygame.K_UP]: dy -= MOVE_SPEED
                    if keys[pygame.K_s] or keys[pygame.K_DOWN]: dy += MOVE_SPEED
                    if keys[pygame.K_a] or keys[pygame.K_LEFT]: dx -= MOVE_SPEED
                    if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += MOVE_SPEED

                    if dx and dy:
                        dx *= 0.707
                        dy *= 0.707

                    gs.my_x = max(20, min(MAP_W - 20, gs.my_x + dx))
                    gs.my_y = max(20, min(MAP_H - 20, gs.my_y + dy))

                    # Send position to server at tick rate
                    now = time.time()
                    if now - last_move_send > 1 / 20:
                        sio.emit("move", {"x": gs.my_x, "y": gs.my_y})
                        last_move_send = now

                # Kill cooldown
                if gs.kill_cooldown > 0:
                    gs.kill_cooldown -= dt

                # Key events
                for ev in events:
                    if ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_e and am_alive:
                            nearby = get_nearby_interactable()
                            if nearby:
                                if nearby["type"] == "task":
                                    station = nearby["station"]
                                    task = next((t for t in gs.my_tasks if t["stationId"] == station["id"] and not t.get("done")), None)
                                    if task:
                                        gs.active_task = MiniGame(task["type"], station["id"])
                                elif nearby["type"] == "sabotage":
                                    sio.call("sabotage", {"stationId": nearby["station"]["id"]})
                                    gs.notify("SABOTAGED!", 2)
                                elif nearby["type"] == "meeting":
                                    sio.call("meeting:call", {})
                        elif ev.key == pygame.K_SPACE and am_alive:
                            sio.call("meeting:call", {})
                        elif ev.key == pygame.K_q and gs.my_role == "impostor" and am_alive and gs.kill_cooldown <= 0:
                            target = get_nearby_kill_target()
                            if target:
                                resp = sio.call("kill", {"targetId": target["id"]})
                                if resp and resp.get("ok"):
                                    gs.kill_cooldown = 25  # 25 sec cooldown
                                    gs.notify(f"Eliminated {target['name']}!", 2)

                draw_game(screen, font)

        # ── MEETING ───────────────────────────────────────────────
        elif gs.phase == "meeting":
            for ev in events:
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_RETURN:
                        if gs.chat_input.strip():
                            sio.emit("chat", {"message": gs.chat_input.strip()})
                            gs.chat_input = ""
                    elif ev.key == pygame.K_BACKSPACE:
                        gs.chat_input = gs.chat_input[:-1]
                    elif ev.unicode and ev.unicode.isprintable() and len(gs.chat_input) < 150:
                        gs.chat_input += ev.unicode
            draw_meeting(screen, font, big_font)

        # ── VOTING ────────────────────────────────────────────────
        elif gs.phase == "voting":
            for ev in events:
                if ev.type == pygame.KEYDOWN and not gs.vote_cast:
                    if ev.key == pygame.K_0:
                        sio.call("vote", {"targetId": "skip"})
                        gs.vote_cast = True
                    elif ev.unicode and ev.unicode.isdigit():
                        idx = int(ev.unicode) - 1
                        if 0 <= idx < len(gs.vote_players):
                            sio.call("vote", {"targetId": gs.vote_players[idx]["id"]})
                            gs.vote_cast = True
            draw_voting(screen, font, big_font)

        # ── GAME OVER ─────────────────────────────────────────────
        elif gs.phase == "gameover":
            for ev in events:
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                    gs.phase = "menu"
                    if sio.connected:
                        sio.emit("leave")
            draw_gameover(screen, font, big_font)

        # Admin + Notification overlays
        draw_admin_panel(screen, font)
        draw_notification(screen, font)
        pygame.display.flip()

    pygame.quit()
    if sio.connected:
        sio.disconnect()
    sys.exit()


if __name__ == "__main__":
    main()
