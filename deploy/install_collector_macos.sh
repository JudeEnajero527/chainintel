#!/usr/bin/env bash
# Runs the ChainIntel collector in the background on this Mac (starts at login, restarts if it crashes).
#   bash deploy/install_collector_macos.sh            install / update
#   bash deploy/install_collector_macos.sh uninstall  stop and remove
set -euo pipefail

LABEL="com.chainintel.collector"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(command -v python3)"
LOG="$PROJECT/collector.log"

if [[ "${1:-}" == "uninstall" ]]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Collector stopped and removed."
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$PROJECT/collector.py</string>
    <string>--loop</string><string>300</string>
  </array>
  <key>WorkingDirectory</key><string>$PROJECT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>60</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Collector installed and running (every 5 minutes)."
echo "  Log:        tail -f \"$LOG\""
echo "  Uninstall:  bash deploy/install_collector_macos.sh uninstall"
