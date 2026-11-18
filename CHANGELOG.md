# Changelog

## Unreleased

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
