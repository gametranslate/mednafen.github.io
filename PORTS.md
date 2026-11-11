# Platform status — 0.3.0

| Platform | Working deliverable | Current requirement |
| --- | --- | --- |
| Windows x64 | Published 0.2.3 portable ZIP | Existing HWND/SDL adapter; WebView2 required |
| Linux x64 | 0.3.0 AppImage; package tests PASS on Ubuntu 22.04 and 24.04 | Private Unix-socket frame/input transport, native SDL audio/controllers, embedded canvas |
| macOS Intel | 0.3.0 native app ZIP candidate, validation pending | Same embedded transport, native Cocoa/WebKit shell; ad-hoc signed, not notarized |
| macOS Apple Silicon | No validated artifact yet | GitHub ARM runners failed allocation due to capacity constraints; no runtime validation claimed |
| Android | None | Use an Android-compatible emulator core and an in-process rendering surface; add touch/gamepad controls, lifecycle/audio and storage handling |

Linux/macOS build Mednafen 1.32.1 from its verified original source and link GameTranslate's separate display/input adapter. SDL renders to a hidden window, then sends RGBA frames to the frontend through a private socket. Emulation, save formats, audio and controller handling remain in Mednafen. Fullscreen belongs to the frontend; Esc restores the menu without restarting the game. Windows continues to use its unchanged original upstream executable.

The Linux release is built on Ubuntu 22.04 x64 and the same AppImage passed extracted-package tests on Ubuntu 22.04 and 24.04. The package includes WebKitGTK 4.1 and its desktop dependencies, while glibc and graphics drivers come from the host. [Tauri documents why newer build hosts cannot imply older Linux compatibility](https://tauri.app/distribute/appimage/). X11/Xvfb is the automated test environment. Wayland/XWayland, hardware controllers, actual speakers and multiple displays have not been validated.

macOS builds use genuine SDL2 2.32.10, compiled from its checksum-verified upstream archive. Homebrew SDL2-compat is not used. The packaging script inspects bundled dylib minimum OS load commands and writes the effective requirement into Info.plist and validation metadata. Consult each release's validation JSON rather than assuming the Rust deployment target is the minimum. There is no Developer ID or Apple notarization. See [Apple's Open Anyway instructions](https://support.apple.com/en-us/102445) if Gatekeeper blocks the app.

Local Linux tests use an isolated WSL/Xvfb desktop with explicit X11 backends and private profiles. Remote package tests run on GitHub's Linux/macOS hosts, checking actual extracted applications. A build is not a validated release until its package report records PASS. Current results are in VALIDATION.md and release validation files.

Android remains outside this port: the desktop child-process/display integration is not an Android renderer or lifecycle implementation.
