# NOCtv animated tour

Two 75-second HyperFrames videos of the actual community UI, with English and
Portuguese explanations. Data is synthetic, including the port and service
outages. Recorded map flows, switch paths and scrolling notifications remain
animated in the output. The MP4 demonstrates clicks; it is not a running NOC.

The tour explains both uses: a TV viewed across a room and interactive inspection
at a desk. Nine views are shown, followed by screen selection and the demo-to-live
configuration flow. See `SPEC.md`, `chapters.json` and `assets/CREDITS.md`.

## Recreate

From the repository root, install the browser-test dependencies (`npm ci` and
`npx playwright install chromium`), then run:

```sh
node videos/noctv-tour/scripts/capture.mjs
cd videos/noctv-tour
npx hyperframes media-use resolve --type sfx --intent 'soft mouse click' --project . --local-only
cp .media/audio/sfx/sfx_001.mp3 assets/click.mp3
node scripts/build.mjs en
npm run check
npm run dev
npm run render -- --quality delivery --fps 30 --output renders/noctv-tour-en.mp4
node scripts/build.mjs pt-BR
npm run check
npm run render -- --quality delivery --fps 30 --output renders/noctv-tour-pt-BR.mp4
```

Requires Python 3.12+, Node 22+, FFmpeg and the HyperFrames CLI. Capture starts its
own demo on `127.0.0.1:8877` and rejects external browser requests. Use an unused
port; do not point the capture at a real installation. `PYTHON`,
`NOCTV_PLAYWRIGHT_MODULE` and `NOCTV_CHROMIUM` can select existing runtimes.
Recordings, raw captures, click audio and render cache stay out of Git. Running
`build.mjs` chooses the language of the editable `index.html`; it does not translate
the application. Rendering does not require changes to NOCtv or its Docker image.

## NVIDIA rendering (optional)

On a Linux workstation with working NVIDIA PRIME offload and NVENC:

```sh
npm run render:rtx -- --quality delivery --fps 30 --workers 2 --output renders/noctv-tour-pt-BR.mp4
```

This sets NVIDIA offload variables for this process and enables HyperFrames GPU
capture/encoding. It does not change the primary GPU, driver, monitor routing or
system PRIME profile. Keep `npm run render` for other machines. Tested on an RTX
3050 6 GB; verify the render log and encoder metadata on your own hardware.

## Verify the deliverables

From the repository root, after rendering and copying the MP4s to `docs/video/`:

```sh
python3 videos/noctv-tour/scripts/verify.py docs/video/noctv-tour-en.mp4 docs/video/noctv-tour-pt-BR.mp4
node videos/noctv-tour/scripts/verify-player.mjs
```

The first check decodes frames to confirm movement and recovery, duration,
resolution and audio presence. The second tests chapter navigation and language
switching in the local player. Neither requires a real monitoring source.
