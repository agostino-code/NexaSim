#!/usr/bin/env bash
# NexaSim Virtual GUI Launcher
# Starts Xvfb virtual display, fluxbox window manager, x11vnc, websockify/novnc,
# opens sumo-gui for traffic visualization, and runs OMNeT++ Qtenv.

set -e

DISPLAY_NUM=99
export DISPLAY=:${DISPLAY_NUM}
RESOLUTION="1600x900x24"

echo "=========================================================="
echo " Starting NexaSim OMNeT++ & SUMO-GUI Virtual Desktop     "
echo "=========================================================="

# 1. Clean up stale X locks
rm -f /tmp/.X${DISPLAY_NUM}-lock /tmp/.X11-unix/X${DISPLAY_NUM}

# 2. Start Xvfb (Virtual X11 Framebuffer)
echo "[1/5] Starting Xvfb on display :${DISPLAY_NUM} (${RESOLUTION})..."
Xvfb :${DISPLAY_NUM} -screen 0 ${RESOLUTION} -ac +extension GLX +render -noreset &
XVFB_PID=$!

sleep 1

# 3. Start lightweight Fluxbox window manager
echo "[2/5] Starting Fluxbox window manager..."
fluxbox &
FLUXBOX_PID=$!

sleep 1

# 4. Start x11vnc server (port 5900)
echo "[3/5] Starting x11vnc server on port 5900..."
x11vnc -display :${DISPLAY_NUM} -forever -shared -nopw -rfbport 5900 -quiet &
X11VNC_PID=$!

# 5. Start NoVNC / websockify bridge (port 6080)
echo "[4/5] Starting NoVNC HTML5 WebSocket gateway on port 6080..."
websockify --web /usr/share/novnc 6080 localhost:5900 &
WEBSOCKIFY_PID=$!

# 6. Launch SUMO-GUI in background on the virtual display
echo "[5/5] Launching SUMO-GUI on virtual desktop..."
sumo-gui -c /artery/scenarios/generated/stelvio/stelvio.sumocfg --start &
SUMO_PID=$!

echo ""
echo "=========================================================="
echo " NexaSim Dual GUI (OMNeT++ Qtenv + SUMO-GUI) is ready!    "
echo " Connect via your browser: http://localhost:6080/vnc.html "
echo "=========================================================="
echo ""

# Run OMNeT++ with Qtenv
if [ $# -eq 0 ]; then
    bash /artery/tools/opp_run.sh -f /artery/scenarios/generated/stelvio/omnetpp.ini -u Qtenv
else
    bash /artery/tools/opp_run.sh "$@" -u Qtenv
fi
