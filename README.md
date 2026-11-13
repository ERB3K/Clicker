# Clicker

A modular auto-clicker and input automation tool targeting **Linux (Wayland & X11)**, built with Python, GTK4 / Libadwaita, and Flatpak.

## What It Is & What It Does

Clicker simulates mouse clicks (Left, Middle, Right), keyboard presses, and custom key/delay patterns repeatedly using the XDG RemoteDesktop portal.

### Features
- **Modular Architecture**:
  - `src/config.py`: Configuration dataclass (`AutomationConfig`), key/pattern parsing, and `Gio.Settings` persistence (`SettingsManager`).
  - `src/engine.py`: Thread-safe `AutomationEngine` handling XDG RemoteDesktop portal sessions, pointer positioning, clicking, and key simulation.
  - `src/shortcuts.py`: `ShortcutsManager` & `ShortcutRecorderDialog` supporting both XDG GlobalShortcuts portal and window-level key triggers.
  - `src/location_picker.py`: `LocationPickerOverlay` fullscreen crosshair coordinate picker.
  - `src/window.py`: GTK4 / Libadwaita main application window.
- **Flexible Timing, Speed & Duration**:
  - Custom start delay in seconds (`0s` to `3600s`).
  - Speed configurable as either **Interval (ms)** between repeats or **Speed (CPS / clicks per second)**.
  - Duration configurable as **Fixed Time** (minutes + seconds), **Repeat Count**, or **Until Stopped** (infinite).
- **Click Position Modes**:
  - **Current Cursor Location**: Clicks wherever the cursor currently is.
  - **Fixed Position (X, Y)**: Moves the pointer to target `(X, Y)` coordinates before clicking, with a **Pick Location** fullscreen crosshair overlay to select coordinates visually on screen.
- **Configurable Shortcuts**:
  - Customize **Start** (default `F6`), **Stop** (default `F5`), and **Toggle Start/Stop** (default `F8`) shortcuts from the header bar shortcut settings dialog.

## How to Clone and Run

### 1. Clone the repository
```bash
git clone https://github.com/ERB3K/Clicker.git
cd Clicker
```

### 2. Build and Run (Flatpak on Linux)
Clicker is packaged as a Flatpak application using `flatpak-builder` and `meson`:

```bash
flatpak-builder --user --install --force-clean build-dir io.github.erb3k.clicker.json
flatpak run io.github.erb3k.clicker
```

### 3. Build and Run Locally with Meson (Linux)
If you have GTK4, Libadwaita, GtkSourceView 5, libportal (`Xdp-1.0`), and `python3-libevdev` installed on your system:

```bash
meson setup builddir
meson compile -C builddir
meson install -C builddir
clicker
```

> **Note**: On Wayland, your desktop environment will prompt you to grant RemoteDesktop (and Global Shortcuts, if supported) permissions when starting an automation.

## License

This program is licensed under the GNU General Public License, version 3.0 or later. See [COPYING](COPYING) for details.

## Credits

Inspired by the original Clicker project by Satvik Patwardhan.
