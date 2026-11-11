# Mednafen Play 0.3.0 — Validation, 12 November 2026

## Linux/macOS port validation

The Unix adapter builds from the pinned original Mednafen 1.32.1 source without changing emulation code. Runtime binaries and libraries are hashed before packaging, and extracted-package hashes must match before launching tests. Linux tests force GDK/SDL X11 with Xvfb, and macOS tests run on the CI desktop. No tests operate the user's active Windows desktop.

Linux x64 AppImage: PASS on software and OpenGL, built and tested on Ubuntu 22.04 in [CI run 43063988996](https://github.com/gametranslate/mednafen.github.io/actions/runs/43063988996), then the same downloaded artifact passed on local Ubuntu 24.04. Tests verified nonblank pixels from the actual WebView canvas, advancing game frames, F1 save/F2 RTC restoration, F3/Shift+F3 slot selection, Tab retaining UI focus, and measured roughly 1.05x / 4.2x / 1.05x RTC rates before/during/after fast-forward. Blur releases held keys. Native fullscreen hides the sidebar; Esc restores windowed UI, another Esc opens Library, and Now playing resumes the same process. Stop/replay creates a new process, and close leaves neither old nor replay process alive. Separate packaged-engine tests produced over 300 KB of PCM with over 190,000 nonzero bytes for each renderer; private audio files were deleted after inspection.

Final AppImage/macOS ZIP package validation is recorded separately in `validation-<platform>-<architecture>.json` and CI artifacts. Linux success does not establish macOS success. Mac Intel validation is pending; ARM runner allocation failed due to GitHub capacity limits. An artifact is published only after its extracted-package test reports PASS. Tests use the user-authorized Namco Super Wars ROM; no ROM, profile, save or framebuffer/audio capture is included in public artifacts. The temporary remote fixture is removed after testing.

Limits: synthetic WebView input, PCM capture/dummy audio output and one WonderSwan game do not validate physical keyboards/gamepads, real speakers, every emulated system, complete playthroughs, Wayland, multiple monitors or Gatekeeper first-run behavior. macOS signing is ad-hoc, not Apple notarization. Generated engine settings retain their original advanced English descriptions.

## 0.2.3 keyboard and settings regression

The user confirmed 0.2.2 resolves the black viewport and games are playable on the visible desktop. They then reported Tab moving between UI buttons and the Settings system selection resetting after navigation, and requested F1 save/F2 load/F3 next slot.

Gameplay keys received by the WebView are consumed and forwarded to the owned engine's SDL event queue. This uses Mednafen KBMan event handling, without global hooks or desktop input injection. Native game focus is requested only while the app is already foreground. Both key down and key up are handled; blur, navigation and modals release held keys. Esc returns from fullscreen or from windowed gameplay to Library, preserving the session; native Alt+F4 forwards application close.

The separate recommended-defaults file covers player-one gamepads, arrow/letter controls, Tab hold-to-fast-forward, F1/F2/F3 and Shift+F3. Conflicting upstream command bindings move to Ctrl combinations. Explicit custom mappings remain higher priority. The selected Settings system/category persists as view state; explanatory copy distinguishes it from a game or engine option. New help is present in all ten locales.

The new private-desktop keyboard suite deliberately focuses a UI button, sends keys only through that test WebView, verifies no Tab navigation, reads the emulator's real WonderSwan RTC from save files to measure roughly 1x/4x/1x speed, exercises real F1 save/F2 load/F3 next/Shift+F3 previous slots, and verifies modal/blur release, normal Settings typing, view persistence, saved video settings, custom-key preservation, native Esc and native Alt+F4. Original ROM hashes and isolated test profiles protect user data. Final extracted-package results are recorded in checkpoints/2026-11-11-0.2.3.

Implementation references: [SDL_PushEvent](https://wiki.libsdl.org/SDL2/SDL_PushEvent) and [SetFocus](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setfocus); the unchanged bundled Mednafen source implements KBMan::Event in src/drivers/keyboard.cpp. SDL_PushEvent does not change SDL device state; Mednafen consumes the queued key events directly.

## Previous black-video investigation

The user corrected the report: 0.2.1 has game audio but a black viewport. Read-only inspection found frames advancing (1167 to 1287 in two seconds), a visible, correctly parented native game child above WRY, and normal OpenGL/WASAPI initialization. The main window lacked WS_CLIPCHILDREN and WRY lacked WS_CLIPSIBLINGS. The old frame tests did not prove the user could see the native surface.

0.2.2 adds those clipping styles and excludes the game rectangle from the WebView using SetWindowRgn, on the UI thread with stale-request cancellation, region ownership cleanup and retry on failure. It restores the full UI for hidden/stopped gameplay. Player resize updates now respect modal visibility, including an empty Log.

The compositor/overpainting diagnosis remains an inference. The new regression fails on an isolated copy of 0.2.1 (WebView overlaps the native viewport), and passes on the 0.2.2 candidate for OpenGL and software rendering. It checks actual native regions at game edges/center, retained header/sidebar/toolbar, resized windows, Log plus resize, Settings/About, fullscreen exclusion, Esc continuity and full restoration after Stop. Tests enable WASAPI with volume zero and capture a nonblank Namco frame. Final package results are recorded in the versioned checkpoint; the user subsequently confirmed the visible black-screen problem is resolved.

Implementation references: [Microsoft window styles](https://learn.microsoft.com/en-us/windows/win32/winmsg/window-styles), [child-window clipping](https://learn.microsoft.com/en-us/windows/win32/gdi/child-window-update-region), and [SetWindowRgn coordinates and ownership](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowrgn).

## Retained 0.2.1 regression scope

The user reported indefinite “Starting game…”, no audio/log error, an unclosable session and no clear-library action in 0.2.0. Earlier hidden tests did not establish normal desktop presentation. Those earlier delivery results are not evidence that the reported defect was absent.

This update removes startup's dependency on two requestAnimationFrame callbacks, commits/measures the player directly, moves launch work off the UI thread, waits for the first actual emulator frame, and stops a failed startup after 15 seconds. The exact trigger on the user's visible desktop was not conclusively reproduced. The suspended-animation-frame case is tested explicitly.

Stop and close wait for graceful engine exit, with a four-second fallback to terminate this application's own nonresponsive child. Forced termination can lose unsaved progress. A supervisor cleans up exited processes and disappeared game windows. Close no longer requires manually choosing Stop first. Unsaved Settings still have a discard/cancel prompt.

## Automated evidence

- TypeScript/Vite build; seven JavaScript tests, including matching keys and placeholders in ten locale bundles (538 messages each); six Rust tests.
- Headless frontend checks: Settings categories, validation, inheritance, dirty navigation, language/theme persistence, branding, About and responsive layouts.
- New normal-presentation tests create a separate Windows desktop with CreateDesktopW/CreateProcessW. They never select that desktop, activate the user's desktop or use computer-use. Native OS fullscreen transitions are enabled in these tests.
- Namco Super Wars: actual framebuffer capture, native child parent/visibility checks, first-frame status, startup while requestAnimationFrame is suppressed, fullscreen/Esc continuity, Stop from library and replay.
- Drop handler tests: native Tauri drop events, duplicate/unsupported/multiple-file handling, SDL child WM_DROPFILES forwarding, graceful game switching and unsaved Settings protection. Dragging the physical mouse through Explorer is not exercised.
- Clear-library confirmation/cancel and execution while playing, with sentinel ROM/BIOS/save files retained and settings cleared from the library only.
- Fault injection suspends only the test emulator process: bounded startup failure, replay after timeout, Stop recovery and window-close recovery. Dirty close cancellation preserves the session.
- Existing hidden native/background checks cover settings persistence, missing tracks/invalid ROMs and both OpenGL/software playback, resizing, aspect ratio and process-local input.
- The original user ROM is hash-checked; tests use separate data directories under .cache with audio disabled or volume zero. No user saves are read or overwritten.

Per-run logs/results and final extracted-package checks are recorded in checkpoints/2026-11-11-0.2.3. A check is complete only when that checkpoint records PASS.

## Distribution

Mednafen EXE and SDL2_original.dll are verified against the official archive. SDL2.dll is the separate GameTranslate window adapter with a source/build manifest. Corresponding Mednafen source, COPYING/documentation, SDL and frontend dependency notices are bundled. No ROM, BIOS, library, save, test capture or private profile is packaged.

## Limits

No automated test touches the user’s normal Windows desktop. The user confirmed the 0.2.2 video fix there; physical keyboard focus in 0.2.3 still needs user validation. Physical input/controller focus, multiple monitors/DPI changes, all emulated systems and a full game playthrough are not validated. Startup/title/opening dialogue and native framebuffer evidence do not imply those checks.

Installer extraction is tested, not the complete installer/uninstaller flow or a clean machine without WebView2. Builds are unsigned. Advanced technical descriptions retain upstream English; translations need further native-speaker review.

The Windows results above describe 0.2.3. Linux/macOS use the separate transport and validation described at the top of this document. Android is not supported. See PORTS.md.
