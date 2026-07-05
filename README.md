# Mullvad VPN Tray

A lightweight system tray applet for Linux that provides a quick-access menu to manage **Mullvad VPN** exit nodes via **Tailscale**.

## Overview

This tool integrates with Tailscale's exit-node feature, allowing you to route all your traffic through Mullvad's servers with a single click from your system tray. No browser needed — just select a country or city from the menu and you're connected.

**Why this exists**: Tailscale provides encrypted tunnel connectivity, but selecting an exit node requires the CLI or web dashboard. This applet puts that functionality directly into your system tray with a friendly UI, auto-rotation, and quick country lock.

## Features

- **System tray menu** — GTK/AppIndicator with country-grouped server list
- **Web-based picker** — browse servers by country and city in an embedded popup
- **Country lock** — stay on a specific country during auto-rotation
- **Auto-rotation** — cycle through exit nodes automatically at configurable intervals (15 min to 1 week)
- **Fast random connect** — jump to a random exit node in seconds
- **Quick disconnect** — clear the exit node with one click
- **Systemd watchdog** — keeps the tray alive via `sd_notify`
- **Graceful fallbacks** — works with `AyatanaAppIndicator3` or `AppIndicator3`

## How It Works

```
┌─────────────────┐     tailscale set      ┌──────────────────┐
│   VpnTray UI    │ ──────────────────────►│   Tailscale CLI   │
│  (GTK/Indicator)│   --exit-node=<IP>    │                  │
└─────────────────┘                        └──────────────────┘
        │                                          │
        │  tailscale status --json                 │
        └──────────────────────────────────────────┘
                           │
                   ┌───────▼───────┐
                   │  Mullvad Exit │
                   │    Nodes      │
                   └───────────────┘
```

1. On launch, the applet queries `tailscale status --json` to discover available Mullvad exit nodes
2. The menu displays them grouped by country and city
3. Selecting a node runs `tailscale set --exit-node=<IP>`
4. The tray icon updates to reflect connected/disconnected state
5. The watchdog timer (`NOTIFY_SOCKET`) keeps systemd informed

## Requirements

| Package | Note |
|---------|------|
| `python3-gi` | Python GTK3 bindings |
| `gir1.2-ayatanaappindicator3-0.1` | System tray (primary) |
| `gir1.2-appindicator3-0.1` | System tray (fallback) |
| `gir1.2-webkit2-4.1` | Web picker popup |
| `tailscale` | CLI tool (must be installed and logged in) |

## Installation

```bash
# Install dependencies (Debian/Ubuntu)
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 gir1.2-webkit2-4.1

# Install Tailscale if not present
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up

# Clone or copy the script
chmod +x vpn-tray.py
./vpn-tray.py
```

## Systemd Service (Optional)

For automatic startup and watchdog support:

```ini
# ~/.config/systemd/user/vpn-tray.service
[Unit]
Description=Mullvad VPN Tray
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/path/to/vpn-tray.py
Restart=on-failure
WatchdogSec=30

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now vpn-tray.service
```

## Usage

### Menu Options

| Item | Action |
|------|--------|
| **Status bar** | Shows current exit node (country + city) |
| **Country submenu** | Pick a country → random node in that country |
| **🌐 Pick a server** | Opens the web picker (filter by country + city) |
| **🎲 Fast connect** | Random exit node anywhere |
| **🔄 Rotate now** | Switch to a new random node |
| **🔒 Country lock** | Toggle — stay within the current country during rotation |
| **⏱️ Rotation interval** | Disable / 15min / 30min / 1h / 6h / 1d / 1w |
| **🔁 Refresh nodes** | Re-fetch the node list from Tailscale |
| **❌ Disconnect** | Clear the exit node |
| **Quit** | Exit the applet |

### Rotation Logic

- **Country lock ON**: picks a random node in the currently selected country
- **Country lock OFF**: picks a random node from any country
- **Fast connect**: equivalent to a single rotation step

## Configuration

Config stored at `~/.config/vpn-tray/config.json`:

```json
{
  "interval_min": 0,
  "country_lock": false
}
```

- `interval_min`: 0 = disabled, 15/30/60/360/1440/10080 = minutes
- `country_lock`: stay within the current country during rotation

## Architecture

```
vpn-tray.py
├── Module-level functions (layer data)
│   ├── sd_notify()          — systemd watchdog
│   ├── load_config/save_config() — JSON persistence
│   ├── ts_status_peers()    — raw Tailscale peer list
│   ├── list_nodes()         — filter + format exit nodes
│   ├── current_node()       — active exit node
│   ├── set_node(ip)         — set exit node via CLI
│   └── clear_node()         — disconnect
│
└── VpnTray class (layer UI)
    ├── __init__             — init indicator, load config, start timer
    ├── _initial_nodes_refresh() — bootstrap nodes on startup
    ├── build_menu()         — rebuild GTK menu
    ├── _chooser_html()      — HTML for web picker
    ├── on_choose_node()     — show picker popup
    ├── _on_web_connect()     — JS callback from picker
    ├── refresh()            — update icon + status
    ├── on_random()          — random node (current country)
    ├── on_random_fast()     — random node (any country)
    ├── on_rotate()          — rotate + schedule next
    ├── apply_rotation()     — execute rotation
    ├── set_interval()        — set rotation interval
    └── on_refresh_nodes()   — re-fetch from Tailscale
```

## Troubleshooting

**Tray icon not showing?**
```bash
# Verify Indicator support
python3 -c "from gi.repository import AyatanaAppIndicator3; print('ok')"

# Try the AppIndicator3 fallback
python3 -c "from gi.repository import AppIndicator3; print('ok')"
```

**No exit nodes found?**
```bash
# Verify Tailscale is running and logged in
tailscale status

# Check if Mullvad servers appear as peers
tailscale status --json | jq '.Peer | to_entries[] | select(.value.ExitNodeOption == true)'
```

**Rotation not working?**
```bash
# Run with logging to see what's happening
python3 vpn-tray.py 2>&1 | grep vpn-tray
```

## License

MIT
