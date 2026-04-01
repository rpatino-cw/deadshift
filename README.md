<p align="center">
  <img src="assets/banner.svg" alt="DEADSHIFT" width="100%"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/players-3--8-blue?style=flat-square&logo=gamepad" alt="Players"/>
  <img src="https://img.shields.io/badge/platform-macOS%20|%20Linux%20|%20Windows-green?style=flat-square" alt="Platform"/>
  <img src="https://img.shields.io/badge/network-LAN%20%2F%20WiFi-orange?style=flat-square&logo=wifi" alt="Network"/>
  <img src="https://img.shields.io/badge/accounts-none%20required-purple?style=flat-square" alt="No Accounts"/>
  <img src="https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square" alt="License"/>
</p>

<p align="center">
  <b>Among Us meets the data center.</b><br/>
  One person hosts. Everyone joins on the same WiFi. No accounts, no internet required.
</p>

---

## How It Works

<p align="center">
  <img src="assets/gameplay-flow.svg" alt="Gameplay Flow" width="100%"/>
</p>

## The Roles

<p align="center">
  <img src="assets/roles.svg" alt="Crew vs Impostor" width="100%"/>
</p>

**Crew** — Complete tasks at stations around the dark data center. Cable racks, PSU swaps, cooling checks, badge scans. Finish them all to win.

**Impostor** — Blend in. Sabotage critical systems. Eliminate crew in the dark. Win by sabotaging 3 systems or outnumbering the crew.

**Everyone** — Limited flashlight vision. You can only see what's near you. Call emergency meetings to discuss and vote someone out.

---

## Quick Start

<p align="center">
  <img src="assets/setup.svg" alt="Setup Instructions" width="100%"/>
</p>

### Host (runs the server + plays)
```bash
git clone https://github.com/rpatino-cw/deadshift.git
cd deadshift
npm install              # one-time server setup
node server.js &         # start the server
pip install -r requirements.txt   # one-time client setup
python3 game.py          # launch the game
```

### Players (everyone else)
```bash
git clone https://github.com/rpatino-cw/deadshift.git
cd deadshift
pip install -r requirements.txt
python3 game.py
```
> Enter the host's IP (shown in server output) and the 4-letter room code.

---

## Controls

<p align="center">
  <img src="assets/controls.svg" alt="Controls" width="100%"/>
</p>

| Key | Action |
|-----|--------|
| `WASD` | Move around the data center |
| `E` | Interact — do tasks, sabotage, or hit the meeting button |
| `Q` | Kill a nearby crew member *(impostor only)* |
| `SPACE` | Call emergency meeting |
| `1-9` | Vote for a player during meetings |
| `0` | Skip vote |
| `ESC` | Cancel task / back to menu |

---

## Game Features

```
  DARK DATA CENTER          FLASHLIGHT VISION         TASK MINIGAMES
  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
  │ ░░░░████░░░░ │         │    ╭────╮    │         │ ■──────────■ │
  │ ░░░░████░░░░ │         │   ╱      ╲   │         │ ■──────────■ │
  │ ░░██    ██░░ │         │  │  ●  ●  │  │         │ ■──────────■ │
  │ ░░██    ██░░ │         │   ╲      ╱   │         │ ■──────────■ │
  │ ░░░░████░░░░ │         │    ╰────╯    │         │ [CONNECTED]  │
  └──────────────┘         └──────────────┘         └──────────────┘

  SABOTAGE SYSTEM           EMERGENCY MEETINGS        VOTE & EJECT
  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
  │  ╔══════╗    │         │ Red: "Not me" │         │ ● Red    [3] │
  │  ║ !ERR ║    │         │ Blu: "Where?" │         │ ● Blue   [1] │
  │  ║ OVHT ║    │         │ Grn: "Rack B" │         │ ● Green  [0] │
  │  ╚══════╝    │         │ Ylw: "sus"    │         │ ● Skip   [1] │
  │  [CRITICAL]  │         │               │         │ Red ejected! │
  └──────────────┘         └──────────────┘         └──────────────┘
```

### Win Conditions

| Side | Win by... |
|------|-----------|
| **Crew** | Completing all tasks OR voting out the impostor |
| **Impostor** | Sabotaging 3 critical systems OR outnumbering crew |

---

## Admin / QA Mode

Solo testing with full control:

```bash
python3 game.py --admin
```

| Key | Action |
|-----|--------|
| `F1` | Toggle admin panel |
| `F2` | Switch role (crew / impostor) |
| `F3` | Toggle fog of war |
| `F4` | God mode (no proximity limits) |
| `F5` | Spawn 3 bots |
| `F6` | Force emergency meeting |
| `F7` | Skip all tasks (crew win) |
| `F8` | Force crew win |
| `F9` | Force impostor win |
| `F10` | Teleport to center |

---

## Tech Stack

| Component | Tech |
|-----------|------|
| Server | Node.js + Socket.io — rooms, game state, 20 tick/sec sync |
| Client | Python + Pygame + python-socketio |
| Network | WebSocket over LAN — same WiFi, no internet |
| Players | 3-8 per room, 1-2 impostors |

## Requirements

- **Node.js** 18+
- **Python** 3.10+
- **Same WiFi** network for all players

---

<p align="center">
  <sub>Built with Pygame + Socket.io. No accounts. No telemetry. Just betrayal.</sub>
</p>
