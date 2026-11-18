# Changelog

## Unreleased

### Window position

- Move the dashboard anywhere, on any screen: drag it by its right edge or by the top/bottom edge you don't resize from, or hold Alt and drag from anywhere on it. It reopens where you left it, including after a restart. If that screen is unplugged it goes back next to the tray until the screen returns.
- Tray menu → "Reset window position" puts it back next to the tray.

### Turn the PC on and off from Home Assistant

- New setting (off by default): *Settings → Home Assistant → Allow shutdown from Home Assistant*. Home Assistant can then send `command_shutdown`, `command_restart`, `command_sleep`, `command_hibernate`, `command_lock` or `command_cancel` to `notify.mobile_app_<this PC>`, with an optional `delay` in seconds. Only messages sent to that notify service count; persistent notifications never do.
- "Add the On/Off switch to Home Assistant" creates a **Power** switch on this PC's device page in Home Assistant: on wakes the PC with Wake-on-LAN, off shuts it down through Prism. Its state follows a new *Power* sensor that Prism reports every 30 s.

### Assist (beta)

- Typed messages now go through your preferred Assist pipeline, the same as voice, so they reach the same conversation agent (for example an LLM agent) and share one conversation.
- Replies from agents that stream now appear as they are written.
- When the agent asks a follow-up question by voice, the mic re-opens after the reply has been spoken.
- "Couldn't understand that" replies are shown as soft warnings, and "didn't catch that" is a status message instead of an error bubble. A request that stalls now times out with a clear message.
- A reply from a closed or stopped request can no longer appear in the next conversation.
- The chat follows the light theme and your accent colour.
- New: a typing indicator while Home Assistant thinks, a mic level halo while listening, and one button that switches between talk, send and stop.
- New: a "new conversation" button, an empty-state hint, and Up/Down history for typed messages.
- Esc now stops listening, a running request or speech, one at a time, before it closes the popup.
- New setting: "Speak replies" turns off spoken replies to voice requests.

### Fixes

- `--toggle` and `--assist` now reach the running app on Windows instead of crashing.
- `prism.log` is more useful for bug reports: shortcut and icon messages (such as an invalid hotkey) are written to it instead of being lost in packaged builds, and unexpected errors include where they happened.

### Security

- Raised minimum dependency versions so source installs don't pull in releases with known vulnerabilities. Running from source now needs Python 3.11 or newer.
- Updated the workflow actions.
- The auto-updater now refuses a download it cannot check against the release's SHA256SUMS, instead of installing it unchecked when that file is missing.
- On Windows, when the Credential Manager can't be used, the token file is now encrypted with your Windows account (DPAPI) instead of a key derived from the machine ID, which any local program could read. An existing token file is converted the next time the app starts.
