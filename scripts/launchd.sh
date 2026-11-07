#!/bin/bash

set -e # Exit immediately if a command exits with a non-zero status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_PATH="$(dirname "$SCRIPT_DIR")"

show_help() {
    echo "Usage: $0 <install|uninstall|status|run|restart> [OPTIONS]"
    echo "Manage the macOS launchd agents for dongseon"
    echo
    echo "Jobs:"
    echo "  serve         the built app on 127.0.0.1:8100, always on (restarted if it exits)"
    echo "  daily         'dongseon daily' every day (default 06:00): live prices, then AI scouting"
    echo
    echo "Options:"
    echo "  --job NAME      serve | daily (default: serve)"
    echo "  --hour H        daily only: hour of day (0-23, default 6)"
    echo "  --minute M      daily only: minute (0-59, default 0)"
    echo "  -h, --help      Show this help message"
    echo
    echo "Examples:"
    echo "  $0 install --job serve              # builds the frontend first"
    echo "  $0 status --job serve"
    echo "  $0 restart --job serve              # after pulling new code (rebuilds the frontend)"
    echo "  $0 uninstall --job serve"
}

COMMAND="${1:-}"
shift || true
JOB="serve"
HOUR=6
MINUTE=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --job)
            JOB="$2"
            shift 2
            ;;
        --hour)
            HOUR="$2"
            shift 2
            ;;
        --minute)
            MINUTE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

LOG_DIR="$WORKSPACE_PATH/data/logs"
DONGSEON_BIN="$WORKSPACE_PATH/.venv/bin/dongseon"

case "$JOB" in
    serve)
        LABEL="com.dongseon.serve"
        PROGRAM="<string>$DONGSEON_BIN</string><string>serve</string><string>--no-reload</string><string>--host</string><string>127.0.0.1</string><string>--port</string><string>8100</string>"
        WHEN="always (127.0.0.1:8100)"
        LOG="$LOG_DIR/serve.log"
        ;;
    daily)
        LABEL="com.dongseon.daily"
        PROGRAM="<string>$DONGSEON_BIN</string><string>daily</string>"
        WHEN="$(printf 'every day at %02d:%02d' "$HOUR" "$MINUTE")"
        LOG="$LOG_DIR/launchd-daily.log"
        ;;
    *)
        echo "Unknown job: $JOB"
        show_help
        exit 1
        ;;
esac
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ "$JOB" == "daily" ]]; then
    # Scheduled job: a Mac asleep at that time runs it on wake; a Mac powered off skips that day
    TRIGGER="<key>StartCalendarInterval</key><dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MINUTE</integer></dict>"
else
    # Long-running service: start at login, restart if it exits (throttled to once per 10 s)
    TRIGGER="<key>RunAtLoad</key><true/><key>KeepAlive</key><true/><key>ThrottleInterval</key><integer>10</integer>"
fi

build_frontend() {
    echo "Building the frontend..."
    pnpm --dir "$WORKSPACE_PATH/frontend" build >/dev/null
}

case "$COMMAND" in
    install)
        if [[ "$JOB" == "serve" || "$JOB" == "daily" ]]; then
            if [[ ! -x "$DONGSEON_BIN" ]]; then
                echo "Error: $DONGSEON_BIN not found. Run 'make install' first."
                exit 1
            fi
        fi
        if [[ "$JOB" == "serve" ]]; then
            build_frontend
        fi
        mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
        cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>$PROGRAM</array>
    <key>WorkingDirectory</key>
    <string>$WORKSPACE_PATH</string>
    $TRIGGER
    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
PLIST_EOF
        # bootout returns before the old instance is gone; bootstrapping too early fails with "5: Input/output error"
        launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
        for _ in $(seq 1 20); do
            launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || break
            sleep 0.5
        done
        launchctl bootstrap "gui/$(id -u)" "$PLIST"
        echo "Installed $LABEL: runs $WHEN"
        echo "Log: $LOG"
        ;;
    uninstall)
        launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
        /bin/rm -f "$PLIST"
        echo "Uninstalled $LABEL"
        ;;
    status)
        if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
            echo "$LABEL is loaded"
            launchctl print "gui/$(id -u)/$LABEL" | grep -E "state|last exit code|runs" || true
        else
            echo "$LABEL is not loaded"
        fi
        if [[ -f "$LOG" ]]; then
            echo
            echo "Last lines of $LOG:"
            tail -n 12 "$LOG"
        fi
        ;;
    run)
        launchctl kickstart "gui/$(id -u)/$LABEL"
        echo "Started $LABEL; follow $LOG"
        ;;
    restart)
        if [[ "$JOB" == "serve" ]]; then
            build_frontend
        fi
        launchctl kickstart -k "gui/$(id -u)/$LABEL"
        echo "Restarted $LABEL; follow $LOG"
        ;;
    *)
        show_help
        exit 1
        ;;
esac
