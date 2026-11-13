# Clicker

A modular auto-clicker and input automation tool targeting **Linux (Wayland)**, built with Python, GTK4, and Flatpak.

## What It Is & What It Does

Clicker simulates mouse clicks and key presses repeatedly using the XDG RemoteDesktop portal (supporting Wayland and X11).

### Planned Scope & Features
- **Modular Architecture**: Separate modules for input simulation, timing/configuration, global shortcuts, and the GTK4 UI.
- **Flexible Timing & Speed**: Configure click delay/interval, speed, and total duration.
- **Click Position Modes**:
  - **Current Location**: Click wherever the cursor currently is.
  - **Picked Location**: Select and lock a specific screen coordinate using a location picker.
- **Configurable Shortcuts**: Custom global shortcut to start and stop the automation (via the Global Shortcuts portal).

## How to Clone and Run

### 1. Clone the repository
```bash
git clone https://github.com/ERB3K/Clicker.git
cd Clicker
```

### 2. Build and Run (Flatpak)
Clicker is packaged as a Flatpak application using `flatpak-builder` and `meson`:

```bash
flatpak-builder --user --install --force-clean build-dir net.codelogistics.clicker.json
flatpak run net.codelogistics.clicker
```

> **Note**: On Wayland, your desktop environment will prompt you to grant RemoteDesktop (and Global Shortcuts, if supported) permissions when starting an automation.

## License

This program is licensed under the GNU General Public License, version 3.0 or later. See [COPYING](COPYING) for details.

## Credits

Originally based on [Clicker](https://codelogistics.net/) by Satvik Patwardhan.
