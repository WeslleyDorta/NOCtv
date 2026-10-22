# Delivery review — 2026-10-22

The chosen story follows a site into its network and a failed port, then tours
all nine views and ends with screen selection and the demo-to-live setup.
The alternative brand-led trailer and installation-only tutorial were not built.
Actual frontend recordings preserve map flows, switch paths and the alert ticker.

## Verified

- Isolated demo capture: 38 synthetic devices, no external browser requests,
  no JavaScript errors, port DOWN/UP and service recovery assertions passed.
- HyperFrames checks passed in both languages without errors or warnings.
- Snapshot review covered scene beats and Portuguese text. Decoded final frames
  were inspected for map, port DOWN/UP, title placement and closing instructions.
- Both published MP4s: 75 seconds, 1920 × 1080, 30 fps, H.264 NVENC and audio.
  Frame comparisons confirm movement in map, ticker and switch paths, and changes
  during port/service recovery. This detects frozen output; it is not a full
  frame-by-frame visual comparison.
- RTX 3050 was selected for browser rendering and NVENC encoding. The project
  command does not alter the host PRIME profile or monitor configuration.
- Local chapter player: media metadata, 13 chapters, seeking, language switching
  with playback position preserved, and absence of browser errors all passed.
- Audio is limited to click effects. Presence/levels were measured, not heard.
  No voiceover or music was produced.

## Deliberate limits

Dense overview screens are the weakest shots at phone width. Use full-screen
1080p for device-level details; the large chapter headings explain the purpose
without requiring every metric to be read. A separate vertical/zoomed mobile
edit would be needed for small-screen detailed reading.

The interface stays English in both versions; explanatory text is translated.
All timings and incidents are simulated, not a real-source latency benchmark.
Real equipment/API integrations were not exercised in this media-only change.
The MP4 records clicks; the separate HTML player supplies clickable chapters.
