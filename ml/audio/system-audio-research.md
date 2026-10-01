# Week 01 (10-08-2026 - 16-08-2026)
Task: Research system-audio capture APIs for bot-free recording

Why this matters:
The audio stage begins the meeting pipeline, so its capture choice determines whether later ASR receives the remote meeting audio, the local microphone, or both. A clear platform plan prevents the team from assuming that one cross-platform browser API captures every system sound source.

What this deliverable does:
Compares browser, macOS, Windows, and Linux system-audio capture paths and recommends a staged implementation and normalized audio handoff for ASR.

## Findings

| Capture path | What it can capture | Strengths | Limits and integration cost |
|---|---|---|---|
| Browser Screen Capture API (`getDisplayMedia`) | User-selected display/tab/window and optional audio track | Fastest browser prototype; permission is user initiated; can pair audio with selected meeting tab | Audio track availability depends on browser, chosen surface, and operating system. A request for system audio is only a hint; the returned stream may have no audio track. It requires a fresh user gesture and permission for each capture. [MDN Screen Capture API](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia) |
| macOS ScreenCaptureKit | Selected display, app, or window, with audio and optionally microphone samples | Native, app/window-scoped capture; supports screen and audio sample streams | Requires a native macOS implementation, user-granted Screen Recording permission, and permission messaging. This adds Swift/platform-specific work. [Apple ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit), [Apple macOS capture sample](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-in-macos) |
| Windows WASAPI loopback | Audio rendered to a selected output endpoint (system mix) | Native system mix capture without depending on a particular meeting app | Requires a Windows-specific capture module. Capturing the full output mix can include unrelated notifications or media; output-device changes need handling. [Microsoft WASAPI loopback recording](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording) |
| Linux PipeWire monitor capture | Audio routed through PipeWire sink monitor ports | Uses the Linux audio graph and supports selecting/routing audio streams | Depends on the installed audio server/session configuration and permissions; needs Linux-specific discovery and testing. [PipeWire audio capture example](https://docs.pipewire.org/audio-capture_8c-example.html) |
| Meeting bot/platform integration | Platform-provided participant audio or media stream | Can provide meeting-scoped audio and participant context where the platform supports it | Platform-specific APIs, authentication, permissions, and policy review; not a universal fallback for all meeting tools. |

## Recommendation

Build a small browser capture prototype first for a user-selected meeting tab, because it can validate the ASR handoff with little platform code. Treat the audio track as optional and detect/report when the browser returns none. For the bot-free desktop goal, plan native adapters behind one interface: ScreenCaptureKit on macOS, WASAPI loopback on Windows, and PipeWire monitor capture on Linux. Preserve uploaded recordings as a universal fallback. Do not advertise “system audio capture” as cross-platform until each supported OS and browser combination is tested.

Capture should make the source explicit: `browser_tab`, `system_mix`, `microphone`, or `uploaded_file`. If local microphone and meeting output are both captured, keep them as separately identified sources where possible; mixing them immediately removes useful diarization evidence and risks echo duplication.

## Proposed ASR handoff

The capture adapter should emit timestamped chunks independent of the native/browser API:

```json
{
  "session_id": "session-uuid",
  "chunk_id": "chunk-uuid",
  "source": "browser_tab",
  "captured_at": "2026-08-10T09:00:00Z",
  "sequence": 0,
  "sample_rate_hz": 16000,
  "channels": 1,
  "encoding": "pcm_s16le",
  "duration_ms": 1000,
  "audio_ref": "local-or-object-storage-reference"
}
```

This is a proposed envelope, not a selected ASR vendor contract. Keep the native capture rate/format in metadata when resampling; ASR can then receive normalized 16 kHz mono PCM while the source stays traceable.

## Open questions for the next capture week

- Which desktop operating systems and browsers are in the thesis demo scope?
- Does the first prototype need to capture microphone and remote audio separately?
- Will audio chunks be sent directly to ASR or written to short temporary files first?
- What consent notice and retention behavior should the capture UI expose?

## Week output contract

**Input:** Meeting bot-free capture requirement and current project platform assumptions.

**Output:** Capture-source decision and proposed normalized chunk envelope for ASR; downstream stages receive `session_id`, ordered audio chunks, timestamps, and source metadata.

## Sources

- [MDN: `getDisplayMedia()`](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia)
- [Apple: ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit)
- [Apple: Capturing screen content in macOS](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-in-macos)
- [Microsoft: Loopback Recording](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)
- [PipeWire: Audio capture example](https://docs.pipewire.org/audio-capture_8c-example.html)
