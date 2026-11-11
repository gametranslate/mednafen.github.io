# Mednafen Play 0.2.3

An independent Windows desktop frontend for Mednafen 1.32.1 by GameTranslate. The green/cream Library design includes embedded gameplay, a game-only fullscreen view, day/night switching, ten UI languages, and an approachable settings catalog containing all 7,908 engine keys. English is the default. Esc leaves fullscreen and keeps the game running.

See [the Vietnamese user guide](HUONG-DAN.md), [validation](VALIDATION.md) and [port status](PORTS.md).

0.2.3 routes gameplay keys away from WebView navigation, with held-key release on menus/focus loss. Defaults use arrow keys and letter buttons, hold Tab for fast-forward, F1 to save, F2 to load, F3/Shift+F3 to change slots. Existing custom mappings remain intact. Settings remembers the selected system/category automatically and explains that this selector chooses which settings to view. The user confirmed the previous black-screen fix works.

0.2.2 reserves the native game rectangle in the WebView window region and prevents the parent/interface from painting over it. The region follows resize/fullscreen and restores for Settings, About, Log and Stop. Resizing with a modal open keeps the game hidden. The user confirmed visible gameplay works with this fix on 11 November 2026.

0.2.1 adds ROM drop-to-play (including the game surface), a confirmed Clear library action that preserves files, graceful stop on window close, recovery for hung sessions and bounded startup with first-frame diagnostics.

## Development

Windows x64, Node/npm, stable Rust MSVC, Visual Studio C++ Build Tools with Windows SDK, WebView2, Python 3.12+ and 7-Zip for package extraction checks.

```powershell
npm ci
npm run prepare:engine
npm run desktop
```

Engine preparation verifies official archive/source SHA-256, downloads verified SDL headers and builds the window adapter. `npm run prepare:host` rebuilds it after native source changes. The original Mednafen EXE is unchanged, and the original SDL is retained as SDL2_original.dll. The adapter forwards exports to it. Engine hashes are bound to each application build, so an incompatible custom engine is rejected before it can create a separate window.

The checked-in settings schema can be regenerated with `npm run prepare:settings`. No online translation runs in the application. `scripts/translate_ui.py` is an optional maintainer tool that sends only static UI copy to Google Translate; all ten language bundles are checked in. Machine translations still need native-speaker review.

```powershell
npm test
cargo test --manifest-path src-tauri/Cargo.toml
npm run desktop:build
python scripts/package_release.py
```

Artifacts go into `release`. The ZIP contains the same engine, notices and corresponding Mednafen source as the installer. The frontend source ZIP includes the native adapter and build scripts. No ROM, BIOS, library, save or QA directory is packaged.

## Background verification

```powershell
python -m pip install -r tests/requirements.txt
python -m playwright install chromium
npm run dev
# Another terminal, while Vite is running:
python tests/frontend.spec.py
$env:MEDNAFEN_PLAY_TEST_ROM='D:/YourGames/Namco Super Wars (Japan).wsc'
python tests/native.spec.py
python tests/background.spec.py
```

Native tests use an isolated `.cache` home. The window is created hidden from the outset. No desktop screenshots, foreground activation, global keyboard injection or computer-use tooling is required. The rendering test reads only the emulator framebuffer and injects SDL events into that test process. Physical keyboard/gamepad routing is a separate manual test. Native OS fullscreen transitions are skipped in background mode to avoid interrupting the desktop; UI fullscreen bounds, Esc and session continuity are exercised. `MEDNAFEN_PLAY_TEST_EXE` can select a release or extracted package.

`MEDNAFEN_PLAY_TEST_HOME` plus `MEDNAFEN_PLAY_BACKGROUND_QA` enables this isolated mode; ordinary application launches do not use it. `MEDNAFEN_PLAY_QA_CAPTURE` optionally specifies a framebuffer output path. None of these variables are set by the distribution.

## Implementation and settings

- React/TypeScript: library, settings, translations, About and player layout.
- Rust/Tauri: persistence, process lifecycle, BIOS validation and native window management.
- `native/sdl-host.c`: hidden-window reparenting before presentation, aspect-preserving GPU/software output and fullscreen hotkeys.

The library is authoritative for settings. On launch, schema defaults are overlaid by global and per-game choices. Input mappings changed inside the emulator are synchronized after graceful exit. Fullscreen switching, monitor selection and viewport fitting belong to the frontend; the backbuffer is cleared every frame to prevent resize artifacts. Engine-only fullscreen sizing controls remain visible with an explanation instead of editable controls that have no effect. Advanced upstream descriptions remain English when not localized.

Mednafen's original notices and corresponding source are included. See `src-tauri/resources/THIRD-PARTY.txt`, `SDL-LICENSE.txt` and `FRONTEND-LICENSES.txt`. The official GitHub link in About opens the upstream website/distribution repository. Starring is the user's choice.

The normal-presentation regression suites run on an unselected private Windows desktop (never SwitchDesktop). With MEDNAFEN_PLAY_TEST_ROM set to the Namco fixture, run `python tests/session.spec.py`, `python tests/startup.spec.py`, `python tests/clipping.spec.py` and `python tests/keyboard.spec.py`. After packaging, `python scripts/verify_packages.py` extracts the installer and ZIP without installing either and runs those suites sequentially. Do not build into a resource directory while its test process is running.

Recommended keys are defined separately from the unchanged upstream catalog in src/data/input-defaults.json. Regenerate with python scripts/generate_input_defaults.py. Frontend and Rust load the same defaults, then apply explicit global/per-game overrides. The keyboard regression reads WonderSwan RTC values from isolated real save states to validate normal/fast-forward/released speed, save/load and slot switching.
