use serde::{Deserialize, Serialize};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Mutex,
};
use tauri::{Emitter, Manager};

#[derive(Clone, Copy, Default, Deserialize, PartialEq, Eq)]
pub struct Bounds {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}
#[derive(Default)]
pub struct Player {
    pub bounds: Mutex<Bounds>,
    pub visible: Mutex<bool>,
    pub fullscreen: Mutex<bool>,
    pub parent: AtomicUsize,
    clip: Mutex<Option<Clip>>,
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    bridge: platform::Bridge,
}
#[derive(Clone, Copy, PartialEq, Eq)]
struct Clip {
    bounds: Bounds,
    visible: bool,
    width: i32,
    height: i32,
}
#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct PlayerStatus {
    pub transport: &'static str,
    pub fullscreen: bool,
    pub embedded: bool,
    pub ready: bool,
    pub frames: u64,
}

#[cfg(windows)]
mod platform {
    use super::*;
    use windows_sys::Win32::Foundation::HWND;
    use windows_sys::Win32::Graphics::Gdi::ScreenToClient;
    use windows_sys::Win32::UI::WindowsAndMessaging::*;
    const FRAMES: &[u16] = &[77, 80, 70, 114, 97, 109, 101, 115, 0];
    const X: &[u16] = &[77, 80, 88, 0];
    const Y: &[u16] = &[77, 80, 89, 0];
    const W: &[u16] = &[77, 80, 87, 0];
    const H: &[u16] = &[77, 80, 72, 0];
    const CHILD: &[u16] = &[77, 80, 67, 104, 105, 108, 100, 0];
    const FULL: &[u16] = &[77, 80, 70, 117, 108, 108, 115, 99, 114, 101, 101, 110, 0];
    const REQUEST: &[u16] = &[77, 80, 82, 101, 113, 117, 101, 115, 116, 0];
    fn retry_clip(app: &tauri::AppHandle, clip: Clip) {
        let state = app.state::<Player>();
        let mut cached = state.clip.lock().unwrap();
        if *cached == Some(clip) {
            *cached = None;
        }
    }
    // WebView2 uses a GPU-composited surface. HWND z-order alone does not reserve
    // space for the emulator: explicitly exclude its rectangle from the WebView.
    fn clip_webview(app: &tauri::AppHandle, p: HWND, bounds: Bounds, visible: bool) {
        let mut r = unsafe { std::mem::zeroed() };
        if unsafe { GetClientRect(p, &mut r) } == 0 {
            return;
        }
        let clip = Clip {
            bounds,
            visible,
            width: r.right,
            height: r.bottom,
        };
        {
            let state = app.state::<Player>();
            let mut previous = state.clip.lock().unwrap();
            if *previous == Some(clip) {
                return;
            }
            *previous = Some(clip);
        }
        let handle = app.clone();
        let scheduled = app.run_on_main_thread(move || unsafe {
            use windows_sys::Win32::Graphics::Gdi::*;
            if *handle.state::<Player>().clip.lock().unwrap() != Some(clip) {
                return;
            }
            let Ok(p) = parent(&handle) else {
                retry_clip(&handle, clip);
                return;
            };
            if IsWindow(p) == 0 {
                retry_clip(&handle, clip);
                return;
            }
            SetWindowLongW(
                p,
                GWL_STYLE,
                (GetWindowLongW(p, GWL_STYLE) as u32 | WS_CLIPCHILDREN) as i32,
            );
            let mut webview = GetWindow(p, GW_CHILD);
            while !webview.is_null() {
                let mut name = [0u16; 64];
                let n = GetClassNameW(webview, name.as_mut_ptr(), 64);
                if String::from_utf16_lossy(&name[..n.max(0) as usize]) == "WRY_WEBVIEW" {
                    break;
                }
                webview = GetWindow(webview, GW_HWNDNEXT);
            }
            if webview.is_null() {
                retry_clip(&handle, clip);
                return;
            }
            SetWindowLongW(
                webview,
                GWL_STYLE,
                (GetWindowLongW(webview, GWL_STYLE) as u32 | WS_CLIPSIBLINGS) as i32,
            );
            if !clip.visible {
                if SetWindowRgn(webview, std::ptr::null_mut(), 1) == 0 {
                    retry_clip(&handle, clip);
                }
                return;
            }
            let mut full = std::mem::zeroed();
            if GetWindowRect(webview, &mut full) == 0 {
                retry_clip(&handle, clip);
                return;
            }
            let mut point = windows_sys::Win32::Foundation::POINT {
                x: clip.bounds.x,
                y: clip.bounds.y,
            };
            if ClientToScreen(p, &mut point) == 0 {
                retry_clip(&handle, clip);
                return;
            }
            // SetWindowRgn uses window coordinates, including any nonclient border.
            point.x -= full.left;
            point.y -= full.top;
            let region = CreateRectRgn(0, 0, full.right - full.left, full.bottom - full.top);
            let hole = CreateRectRgn(
                point.x,
                point.y,
                point.x + clip.bounds.width,
                point.y + clip.bounds.height,
            );
            if region.is_null() || hole.is_null() {
                if !region.is_null() {
                    DeleteObject(region);
                }
                if !hole.is_null() {
                    DeleteObject(hole);
                }
                retry_clip(&handle, clip);
                return;
            }
            let combined = CombineRgn(region, region, hole, RGN_DIFF);
            DeleteObject(hole);
            // A successful SetWindowRgn transfers region ownership to Windows.
            if combined == 0 || SetWindowRgn(webview, region, 1) == 0 {
                DeleteObject(region);
                retry_clip(&handle, clip);
            }
        });
        if scheduled.is_err() {
            retry_clip(app, clip);
        }
    }
    pub fn parent(app: &tauri::AppHandle) -> Result<HWND, String> {
        let hwnd = app.state::<Player>().parent.load(Ordering::SeqCst) as HWND;
        if hwnd.is_null() {
            Err("Window unavailable".into())
        } else {
            Ok(hwnd)
        }
    }
    pub fn fullscreen(app: &tauri::AppHandle, value: bool) -> Result<(), String> {
        let win = app.get_webview_window("main").ok_or("Window unavailable")?;
        // Hidden QA never alters the user's desktop or restores a visible window.
        if !(std::env::var_os("MEDNAFEN_PLAY_TEST_HOME").is_some()
            && std::env::var_os("MEDNAFEN_PLAY_BACKGROUND_QA").is_some())
        {
            win.set_fullscreen(value).map_err(|e| e.to_string())?;
        }
        *app.state::<Player>().fullscreen.lock().unwrap() = value;
        unsafe {
            SetPropW(
                parent(app)?,
                FULL.as_ptr(),
                if value {
                    1usize as _
                } else {
                    std::ptr::null_mut()
                },
            );
        }
        app.emit("player-fullscreen", value)
            .map_err(|e| e.to_string())
    }
    pub fn child(app: &tauri::AppHandle) -> Option<HWND> {
        let p = parent(app).ok()?;
        unsafe {
            let c = GetPropW(p, CHILD.as_ptr()) as HWND;
            if c.is_null() || IsWindow(c) == 0 {
                return None;
            }
            let mut pid = 0;
            GetWindowThreadProcessId(c, &mut pid);
            let state = app.state::<crate::Backend>();
            if state.running.lock().ok()?.as_ref()?.child.id() != pid {
                return None;
            }
            Some(c)
        }
    }
    pub fn stop(app: &tauri::AppHandle) -> Result<(), String> {
        if let Some(c) = child(app) {
            unsafe {
                PostMessageW(c, WM_CLOSE, 0, 0);
            }
            Ok(())
        } else {
            Err("The game is still starting. Please wait.".into())
        }
    }
    pub fn focus(app: &tauri::AppHandle) -> Result<(), String> {
        if let Some(c) = child(app) {
            unsafe {
                PostMessageW(c, WM_APP + 71, 0, 0);
            }
            Ok(())
        } else {
            Ok(())
        }
    }
    pub fn key(
        app: &tauri::AppHandle,
        scancode: u32,
        down: bool,
        modifiers: u16,
        character: Option<u32>,
    ) -> Result<(), String> {
        if scancode == 0 || scancode >= 512 {
            return Err("Invalid key.".into());
        }
        if !*app.state::<Player>().visible.lock().unwrap() {
            return Ok(());
        }
        if let Some(c) = child(app) {
            unsafe {
                let testing = std::env::var_os("MEDNAFEN_PLAY_TEST_HOME").is_some();
                if down && !testing && GetForegroundWindow() != parent(app)? {
                    return Ok(());
                }
                PostMessageW(
                    c,
                    WM_APP + 73,
                    scancode as usize,
                    ((modifiers as isize) << 16) | down as isize,
                );
                if down {
                    if let Some(value) = character.filter(|v| *v <= 0x10ffff) {
                        PostMessageW(c, WM_APP + 75, value as usize, 0);
                    }
                }
            }
        }
        Ok(())
    }
    pub fn release_keys(app: &tauri::AppHandle) {
        if let Some(c) = child(app) {
            unsafe {
                PostMessageW(c, WM_APP + 74, 0, 0);
            }
        }
    }
    pub fn tick(app: &tauri::AppHandle) {
        let Ok(p) = parent(app) else {
            return;
        };
        let state = app.state::<Player>();
        let mut bounds = *state.bounds.lock().unwrap();
        let mut full = *state.fullscreen.lock().unwrap();
        let visible = *state.visible.lock().unwrap();
        unsafe {
            let request = RemovePropW(p, REQUEST.as_ptr()) as usize;
            if request == 3 {
                release_keys(app);
                let _ = app.emit("player-menu", ());
            } else if request != 0 {
                let next = if request == 1 { false } else { !full };
                if fullscreen(app, next).is_ok() {
                    full = next;
                }
            }
            if full {
                let mut r = std::mem::zeroed();
                GetClientRect(p, &mut r);
                bounds = Bounds {
                    x: 0,
                    y: 0,
                    width: r.right,
                    height: r.bottom,
                };
            }
            for (key, value) in [
                (X, bounds.x),
                (Y, bounds.y),
                (W, bounds.width),
                (H, bounds.height),
            ] {
                SetPropW(p, key.as_ptr(), value as isize as _);
            }
            let current_child = child(app);
            clip_webview(app, p, bounds, visible && current_child.is_some());
            if let Some(c) = current_child {
                if visible {
                    if GetWindowLongW(c, GWL_STYLE) as u32 & WS_VISIBLE == 0 {
                        ShowWindowAsync(c, SW_SHOWNA);
                    }
                    let mut r = std::mem::zeroed();
                    GetWindowRect(c, &mut r);
                    let mut point = windows_sys::Win32::Foundation::POINT {
                        x: r.left,
                        y: r.top,
                    };
                    ScreenToClient(p, &mut point);
                    if point.x != bounds.x
                        || point.y != bounds.y
                        || r.right - r.left != bounds.width
                        || r.bottom - r.top != bounds.height
                        || !GetWindow(c, GW_HWNDPREV).is_null()
                    {
                        SetWindowPos(
                            c,
                            HWND_TOP,
                            bounds.x,
                            bounds.y,
                            bounds.width.max(1),
                            bounds.height.max(1),
                            SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS,
                        );
                    }
                } else if GetWindowLongW(c, GWL_STYLE) as u32 & WS_VISIBLE != 0 {
                    ShowWindowAsync(c, SW_HIDE);
                }
            } else if full {
                let stopped = app
                    .state::<crate::Backend>()
                    .running
                    .lock()
                    .unwrap()
                    .is_none();
                if stopped {
                    let _ = fullscreen(app, false);
                }
            }
        }
    }
    pub fn parent_id(app: &tauri::AppHandle) -> Result<String, String> {
        Ok((parent(app)? as usize).to_string())
    }
    pub fn frames(app: &tauri::AppHandle) -> u64 {
        if child(app).is_none() {
            return 0;
        }
        parent(app)
            .map(|p| unsafe { GetPropW(p, FRAMES.as_ptr()) as usize as u64 })
            .unwrap_or(0)
    }
    pub fn prepare(app: &tauri::AppHandle) -> Result<(), String> {
        unsafe {
            let p = parent(app)?;
            RemovePropW(p, CHILD.as_ptr());
            RemovePropW(p, FRAMES.as_ptr());
        }
        Ok(())
    }
    unsafe extern "system" fn drop_proc(
        hwnd: HWND,
        msg: u32,
        w: usize,
        l: isize,
        _id: usize,
        data: usize,
    ) -> isize {
        use windows_sys::Win32::UI::Shell::*;
        if msg == WM_COPYDATA && l != 0 {
            let packet = &*(l as *const windows_sys::Win32::System::DataExchange::COPYDATASTRUCT);
            let app = &*(data as *const tauri::AppHandle);
            if packet.dwData == 0x4d504452
                && child(app) == Some(w as HWND)
                && packet.cbData <= 131072
                && packet.cbData % 2 == 0
                && !packet.lpData.is_null()
            {
                let raw = std::slice::from_raw_parts(
                    packet.lpData as *const u16,
                    packet.cbData as usize / 2,
                );
                let paths: Vec<String> = raw
                    .split(|v| *v == 0)
                    .filter(|v| !v.is_empty())
                    .map(String::from_utf16_lossy)
                    .collect();
                let _ = app.emit("player-file-drop", paths);
                return 1;
            }
        }
        if msg == WM_NCDESTROY {
            RemoveWindowSubclass(hwnd, Some(drop_proc), 71);
            drop(Box::from_raw(data as *mut tauri::AppHandle));
        }
        DefSubclassProc(hwnd, msg, w, l)
    }
    pub fn install_drop_receiver(app: &tauri::AppHandle) -> Result<(), String> {
        let hwnd = app
            .get_webview_window("main")
            .ok_or("Window unavailable")?
            .hwnd()
            .map_err(|e| e.to_string())?
            .0 as HWND;
        app.state::<Player>()
            .parent
            .store(hwnd as usize, Ordering::SeqCst);
        let data = Box::into_raw(Box::new(app.clone()));
        unsafe {
            if windows_sys::Win32::UI::Shell::SetWindowSubclass(
                hwnd,
                Some(drop_proc),
                71,
                data as usize,
            ) == 0
            {
                drop(Box::from_raw(data));
                return Err("Unable to install file drop handler".into());
            }
        }
        Ok(())
    }
}
#[cfg(any(target_os = "linux", target_os = "macos"))]
#[path = "player_stream.rs"]
mod platform;
#[cfg(not(any(windows, target_os = "linux", target_os = "macos")))]
mod platform {
    pub fn parent_id(_: &tauri::AppHandle) -> Result<String, String> {
        Err("Embedded playback is not available on this platform yet.".into())
    }
    pub fn child(_: &tauri::AppHandle) -> Option<usize> {
        None
    }
    pub fn fullscreen(_: &tauri::AppHandle, _: bool) -> Result<(), String> {
        Err("Embedded playback is not available on this platform yet.".into())
    }
    pub fn stop(_: &tauri::AppHandle) -> Result<(), String> {
        Err("No embedded game.".into())
    }
    pub fn focus(_: &tauri::AppHandle) -> Result<(), String> {
        Ok(())
    }
    pub fn key(
        _: &tauri::AppHandle,
        _: u32,
        _: bool,
        _: u16,
        _: Option<u32>,
    ) -> Result<(), String> {
        Ok(())
    }
    pub fn release_keys(_: &tauri::AppHandle) {}
    pub fn tick(_: &tauri::AppHandle) {}
    pub fn frames(_: &tauri::AppHandle) -> u64 {
        0
    }
    pub fn prepare(_: &tauri::AppHandle) -> Result<(), String> {
        Ok(())
    }
    pub fn install_drop_receiver(_: &tauri::AppHandle) -> Result<(), String> {
        Ok(())
    }
}
pub use platform::{install_drop_receiver, parent_id, prepare};
pub fn configure_command(app: &tauri::AppHandle, command: &mut std::process::Command) -> Result<(), String> {
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    return platform::configure_command(app, command);
    #[cfg(not(any(target_os = "linux", target_os = "macos")))]
    { let _ = (app, command); Ok(()) }
}
#[tauri::command]
pub fn player_frame(app: tauri::AppHandle, after: u64) -> tauri::ipc::Response {
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    let bytes = platform::frame(&app, after);
    #[cfg(not(any(target_os = "linux", target_os = "macos")))]
    let bytes = { let _ = (app, after); Vec::<u8>::new() };
    tauri::ipc::Response::new(bytes)
}
pub fn ready(app: &tauri::AppHandle) -> bool {
    platform::frames(app) > 0
}
pub fn embedded(app: &tauri::AppHandle) -> bool {
    platform::child(app).is_some()
}
pub fn request_stop(app: &tauri::AppHandle) -> Result<(), String> {
    platform::stop(app)
}
#[tauri::command]
pub fn player_bounds(app: tauri::AppHandle, bounds: Bounds, visible: bool) -> Result<(), String> {
    if bounds.width < 1 || bounds.height < 1 || bounds.width > 32768 || bounds.height > 32768 {
        return Err("Invalid player bounds.".into());
    }
    let state = app.state::<Player>();
    *state.bounds.lock().unwrap() = bounds;
    *state.visible.lock().unwrap() = visible;
    platform::tick(&app);
    Ok(())
}
#[tauri::command]
pub fn player_visible(app: tauri::AppHandle, visible: bool) {
    if !visible {
        platform::release_keys(&app);
    }
    *app.state::<Player>().visible.lock().unwrap() = visible;
    platform::tick(&app);
}
#[tauri::command]
pub fn player_fullscreen(app: tauri::AppHandle, value: bool) -> Result<(), String> {
    platform::fullscreen(&app, value)
}
#[tauri::command]
pub fn player_status(app: tauri::AppHandle) -> PlayerStatus {
    let fullscreen = *app.state::<Player>().fullscreen.lock().unwrap();
    let frames = platform::frames(&app);
    PlayerStatus {
        transport: if cfg!(windows) { "native" } else { "canvas" },
        fullscreen,
        embedded: platform::child(&app).is_some(),
        ready: frames > 0,
        frames,
    }
}
#[tauri::command]
pub fn focus_game(app: tauri::AppHandle) -> Result<(), String> {
    platform::focus(&app)
}
#[tauri::command]
pub fn player_key(
    app: tauri::AppHandle,
    scancode: u32,
    down: bool,
    modifiers: u16,
    character: Option<u32>,
) -> Result<(), String> {
    platform::key(&app, scancode, down, modifiers, character)
}
#[tauri::command]
pub fn player_release_keys(app: tauri::AppHandle) {
    platform::release_keys(&app);
}
pub fn start(app: tauri::AppHandle) {
    std::thread::spawn(move || loop {
        if app.get_webview_window("main").is_none() {
            break;
        }
        platform::tick(&app);
        std::thread::sleep(std::time::Duration::from_millis(30));
    });
}
