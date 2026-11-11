# Platform status — 0.2.3

| Platform | Working deliverable | Current requirement |
| --- | --- | --- |
| Windows x64 | Installer and ZIP after validation | Native HWND/SDL integration implemented |
| Linux | None | Implement native viewport hosting (including a Wayland-compatible strategy), package a native engine, install Rust/GTK/WebKit build dependencies, then validate |
| macOS | None | Implement Cocoa/Metal/OpenGL host integration and build/test on macOS with Xcode; signing/notarization is a separate release step |
| Android | None | Use an Android-compatible emulator core and an in-process rendering surface; add touch/gamepad controls, lifecycle/audio and storage handling |

The installed WSL Ubuntu-24.04 has GCC/CMake but no Cargo or required GTK/WebKit package set. No macOS/Xcode host was available. The existing integration launches a Windows subprocess and reparents its HWND; a Tauri cross-platform shell alone would not provide working emulation on the other platforms. No Linux, macOS or Android emulator artifact has been produced or advertised as functional.

Suggested order: Linux desktop integration first, macOS desktop second, Android as a separate core-integration milestone. Reuse library/settings/localization code while keeping platform-specific playback implementations separate.
