# DEADSHIFT

Local multiplayer social deduction game. Among Us meets the data center.

One person hosts. Everyone else joins on the same WiFi. No accounts, no internet required.

## Setup

### Host (runs the server + plays)
```bash
git clone https://github.com/rpatino-cw/deadshift.git
cd deadshift
npm install
node server.js &
pip install -r requirements.txt
python3 game.py
```

### Players (everyone else)
```bash
git clone https://github.com/rpatino-cw/deadshift.git
cd deadshift
pip install -r requirements.txt
python3 game.py
```
Enter the host's IP and room code when prompted.

## How to Play

- **3-8 players.** One (or two) are secretly the **Impostor**.
- **Crew** completes tasks at stations around the dark data center (cable racks, PSU swaps, cooling checks, badge scans).
- **Impostor** sabotages systems, eliminates crew members, and blends in.
- **Flashlight vision** — you can only see what's near you.
- **Emergency meetings** — discuss and vote to eject the suspected impostor.

### Controls
| Key | Action |
|-----|--------|
| WASD | Move |
| E | Interact (tasks, sabotage, meeting button) |
| Q | Kill (impostor only) |
| SPACE | Call emergency meeting |
| ESC | Cancel task / back to menu |

### Win Conditions
- **Crew wins:** Complete all tasks OR vote out the impostor
- **Impostor wins:** Sabotage 3 critical systems OR outnumber the crew

## Admin/QA Mode

For solo testing:
```bash
python3 game.py --admin
```
Press **F1** in-game to open the admin panel. Spawn bots (F5), switch roles (F2), toggle fog (F3), and more.

## Tech Stack
- **Server:** Node.js + Socket.io (handles rooms, game state, relay)
- **Client:** Python + Pygame + python-socketio

## Requirements
- Node.js 18+
- Python 3.10+
- Same WiFi network for all players
