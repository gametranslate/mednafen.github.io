# Platform status — 0.3.0

| Platform | Working deliverable | Current requirement |
| --- | --- | --- |
| Windows x64 | Published 0.2.3 portable ZIP | Existing HWND/SDL adapter; WebView2 required |
| Linux x64 | 0.3.0 AppImage candidate | Private Unix-socket frame/input transport, native SDL audio/controllers, embedded canvas |
| macOS Intel / Apple Silicon | 0.3.0 native app ZIP candidates | Same embedded transport, native Cocoa/WebKit shell; ad-hoc signed, not notarized |
| Android | None | Use an Android-compatible emulator core and an in-process rendering surface; add touch/gamepad controls, lifecycle/audio and storage handling |

Linux/macOS build Mednafen 1.32.1 from its verified original source and link GameTranslate's separate display/input adapter. SDL renders to a hidden window, then sends RGBA frames to the frontend through a private socket. Emulation, save formats, audio and controller handling remain in Mednafen. Fullscreen belongs to the frontend; Esc restores the menu without restarting the game. Windows continues to use its unchanged original upstream executable.

The Linux CI baseline is Ubuntu 22.04 x64. A modern desktop with WebKitGTK 4.1 is required; [Tauri documents why newer build hosts cannot imply older Linux compatibility](https://tauri.app/distribute/appimage/). X11/Xvfb is the automated test environment. Wayland/XWayland, hardware controllers, actual speakers and multiple displays have not been validated.

macOS packages are built separately for x64 and arm64. The packaging script inspects bundled dylib minimum OS load commands and writes the effective requirement into Info.plist and validation metadata. Consult each release's validation JSON rather than assuming the Rust deployment target is the minimum. There is no Developer ID or Apple notarization. See [Apple's Open Anyway instructions](https://support.apple.com/en-us/102445) if Gatekeeper blocks the app.

Local Linux tests use an isolated WSL/Xvfb desktop with explicit X11 backends and private profiles. Remote package tests run on GitHub's Linux/macOS hosts, checking actual extracted applications. A build is not a validated release until its package report records PASS. Current results are in VALIDATION.md and release validation files.

Android remains outside this port: the desktop child-process/display integration is not an Android renderer or lifecycle implementation.
