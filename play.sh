#!/bin/bash
# DEADSHIFT — One-command launcher
# Usage: bash play.sh              (join a game)
#        bash play.sh host         (host a game + play)
#        bash play.sh admin        (host + admin/QA mode)
#
# No chmod needed — just: bash play.sh

set -e
cd "$(dirname "$0")"

# Colors
R='\033[0;31m'
G='\033[0;32m'
Y='\033[0;33m'
B='\033[0;34m'
N='\033[0m'

echo -e "${R}"
cat << 'ART'
  ____  _____    _    ____  ____  _   _ ___ _____ _____
 |  _ \| ____|  / \  |  _ \/ ___|| | | |_ _|  ___|_   _|
 | | | |  _|   / _ \ | | | \___ \| |_| || || |_    | |
 | |_| | |___ / ___ \| |_| |___) |  _  || ||  _|   | |
 |____/|_____/_/   \_\____/|____/|_| |_|___|_|     |_|
ART
echo -e "${N}"

# ── Find Python ─────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo -e "${R}  Python 3 is required but not installed.${N}"
    echo ""
    echo "  Install it:"
    echo -e "    macOS:    ${Y}brew install python3${N}"
    echo -e "    Ubuntu:   ${Y}sudo apt install python3 python3-pip${N}"
    echo -e "    Windows:  ${Y}https://python.org/downloads${N}"
    echo ""
    exit 1
fi

echo -e "  Python: ${G}$($PYTHON --version)${N}"

# ── Install Python deps if needed ───────────────────────────────────
if ! $PYTHON -c "import pygame" 2>/dev/null || ! $PYTHON -c "import socketio" 2>/dev/null; then
    echo -e "  ${Y}Installing game dependencies (one-time)...${N}"
    $PYTHON -m pip install -r requirements.txt --quiet --break-system-packages 2>/dev/null \
        || $PYTHON -m pip install -r requirements.txt --quiet --user 2>/dev/null \
        || $PYTHON -m pip install -r requirements.txt --quiet 2>/dev/null
    echo -e "  ${G}Done.${N}"
else
    echo -e "  Dependencies: ${G}OK${N}"
fi

# ── HOST MODE ────────────────────────────────────────────────────────
if [ "$1" = "host" ] || [ "$1" = "admin" ]; then

    # Check Node.js
    if ! command -v node &>/dev/null; then
        echo ""
        echo -e "${R}  Node.js is required to HOST (not to play).${N}"
        echo ""
        echo "  Install it:"
        echo -e "    macOS:    ${Y}brew install node${N}"
        echo -e "    Ubuntu:   ${Y}sudo apt install nodejs npm${N}"
        echo -e "    Windows:  ${Y}https://nodejs.org${N}"
        echo ""
        exit 1
    fi
    echo -e "  Node.js: ${G}$(node --version)${N}"

    # Install node deps if needed
    if [ ! -d "node_modules" ]; then
        echo -e "  ${Y}Installing server dependencies (one-time)...${N}"
        npm install --silent 2>/dev/null
        echo -e "  ${G}Done.${N}"
    fi

    # Kill any existing server on port 3000
    lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

    # Start server
    node server.js &
    SERVER_PID=$!
    sleep 1

    # Get local IP
    IP="localhost"
    if command -v ipconfig &>/dev/null; then
        IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")
    elif command -v hostname &>/dev/null; then
        IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
    fi

    echo ""
    echo -e "${G}  ┌─────────────────────────────────────────────────┐${N}"
    echo -e "${G}  │                                                 │${N}"
    echo -e "${G}  │  ${N}SERVER RUNNING                                ${G}│${N}"
    echo -e "${G}  │                                                 │${N}"
    echo -e "${G}  │  ${Y}Tell your coworkers this address:${N}             ${G}│${N}"
    echo -e "${G}  │                                                 │${N}"
    echo -e "${G}  │     ${R}${IP}:3000${N}                          ${G}│${N}"
    echo -e "${G}  │                                                 │${N}"
    echo -e "${G}  │  ${N}They enter it in the Server field in-game.${N}    ${G}│${N}"
    echo -e "${G}  │                                                 │${N}"
    echo -e "${G}  └─────────────────────────────────────────────────┘${N}"
    echo ""

    # Launch game with server pre-filled
    EXTRA_ARGS="--server ${IP}:3000"
    if [ "$1" = "admin" ]; then
        EXTRA_ARGS="$EXTRA_ARGS --admin"
        echo -e "  ${Y}Admin mode enabled. Press F1 in-game.${N}"
    fi
    $PYTHON game.py $EXTRA_ARGS

    # Cleanup
    kill $SERVER_PID 2>/dev/null || true
    echo -e "${R}  Server stopped.${N}"

# ── PLAYER MODE ──────────────────────────────────────────────────────
else
    echo ""
    echo -e "  ${B}Launching DEADSHIFT...${N}"
    echo -e "  ${Y}Enter the server IP your host gave you.${N}"
    echo ""
    $PYTHON game.py
fi
