use crate::*;
use std::time::{Duration, Instant};

pub fn lifecycle_log(b: &Backend, message: &str) {
    use std::io::Write;
    if let Ok(mut file) = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(b.data.join("lifecycle.log"))
    {
        let _ = writeln!(file, "{} {message}", now());
    }
}
// The session mutex serializes changes. Only this application's child is stopped.
fn stop_owned(app: &tauri::AppHandle) -> Result<bool, String> {
    let b = app.state::<Backend>();
    refresh(&b)?;
    if b.running.lock().map_err(err)?.is_none() {
        return Ok(false);
    }
    let deadline = Instant::now() + Duration::from_secs(4);
    loop {
        let _ = player::request_stop(app);
        refresh(&b)?;
        if b.running.lock().map_err(err)?.is_none() {
            lifecycle_log(&b, "Game stopped gracefully.");
            return Ok(false);
        }
        if Instant::now() >= deadline {
            break;
        }
        std::thread::sleep(Duration::from_millis(80));
    }
    {
        let mut active = b.running.lock().map_err(err)?;
        if let Some(run) = active.as_mut() {
            if run.child.try_wait().map_err(err)?.is_none() {
                run.child.kill().map_err(err)?;
            }
            run.child.wait().map_err(err)?;
        }
    }
    refresh(&b)?;
    lifecycle_log(
        &b,
        "Game did not respond to Stop and was terminated. Unsaved progress may be lost.",
    );
    Ok(true)
}
pub fn supervise(app: tauri::AppHandle) {
    std::thread::spawn(move || {
        let mut observed = None;
        let mut had_frame = false;
        let mut lost_since = None;
        loop {
            if app.get_webview_window("main").is_none() {
                break;
            }
            let b = app.state::<Backend>();
            let _ = refresh(&b);
            let pid = b.running.lock().unwrap().as_ref().map(|r| r.child.id());
            if pid != observed {
                observed = pid;
                had_frame = false;
                lost_since = None;
            }
            if pid.is_some() {
                if player::ready(&app) {
                    had_frame = true;
                    lost_since = None;
                } else if had_frame && !player::embedded(&app) {
                    let since = lost_since.get_or_insert_with(Instant::now);
                    if since.elapsed() >= Duration::from_secs(1) {
                        if let Ok(_session) = b.session.try_lock() {
                            let same =
                                b.running.lock().unwrap().as_ref().map(|r| r.child.id()) == pid;
                            if same && !player::embedded(&app) {
                                lifecycle_log(
                                    &b,
                                    "Game window disappeared; cleaning up the session.",
                                );
                                let _ = stop_owned(&app);
                            }
                        }
                    }
                }
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    });
}
#[tauri::command]
pub async fn launch_game(app: tauri::AppHandle, id: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let b = app.state::<Backend>();
        let pid = {
            let _session = b.session.lock().map_err(err)?;
            launch_game_inner(&app, &b, id)?
        };
        let deadline = Instant::now() + Duration::from_secs(15);
        loop {
            refresh(&b)?;
            let matches = b.running.lock().map_err(err)?.as_ref().is_some_and(|r| r.child.id() == pid);
            if !matches { return Err("The game stopped before it could display a frame. Open Log for details.".into()); }
            if player::ready(&app) {
                lifecycle_log(&b, "First game frame received.");
                return Ok(());
            }
            if Instant::now() >= deadline { break; }
            std::thread::sleep(Duration::from_millis(50));
        }
        let _session = b.session.lock().map_err(err)?;
        let matches = b.running.lock().map_err(err)?.as_ref().is_some_and(|r| r.child.id() == pid);
        if matches {
            lifecycle_log(&b, "Startup timed out: no frame after 15 seconds.");
            stop_owned(&app)?;
        }
        Err("The game did not display a frame within 15 seconds. Open Log for details, then try Software rendering in Settings → Video.".into())
    }).await.map_err(err)?
}
#[tauri::command]
pub async fn stop_game(app: tauri::AppHandle) -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let b = app.state::<Backend>();
        let _session = b.session.lock().map_err(err)?;
        let forced = stop_owned(&app)?;
        player::player_fullscreen(app.clone(), false)?;
        Ok(forced)
    })
    .await
    .map_err(err)?
}
#[tauri::command]
pub async fn quit_app(app: tauri::AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let b = app.state::<Backend>();
        b.quitting.store(true, Ordering::SeqCst);
        let result = (|| {
            let _session = b.session.lock().map_err(err)?;
            stop_owned(&app)?;
            if let Some(win) = app.get_webview_window("main") {
                win.destroy().map_err(err)?;
            }
            Ok(())
        })();
        if result.is_err() {
            b.quitting.store(false, Ordering::SeqCst);
        }
        result
    })
    .await
    .map_err(err)?
}
#[derive(Serialize)]
pub struct DroppedGame {
    store: Store,
    game: Game,
}
#[tauri::command]
pub fn prepare_dropped_game(b: State<Backend>, paths: Vec<String>) -> Result<DroppedGame, String> {
    if paths.len() != 1 {
        return Err("Drop one game at a time.".into());
    }
    let path = fs::canonicalize(&paths[0])
        .map_err(|_| "The dropped file could not be found.".to_string())?;
    if !path.is_file() || detect_system(&path).is_none() {
        return Err(
            "This file type is not supported. Drop a ROM, disc descriptor or archive.".into(),
        );
    }
    verify_game(&path)?;
    let id = game_id(&path);
    let store = add_games(b, vec![normal(&path)])?;
    let game = store
        .games
        .iter()
        .find(|g| g.id == id)
        .ok_or("Game not found.")?
        .clone();
    Ok(DroppedGame { store, game })
}
#[tauri::command]
pub async fn clear_library(app: tauri::AppHandle) -> Result<Store, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let b = app.state::<Backend>();
        let _session = b.session.lock().map_err(err)?;
        stop_owned(&app)?;
        player::player_fullscreen(app.clone(), false)?;
        let mut store = b.store.lock().map_err(err)?;
        let mut next = store.clone();
        next.games.clear();
        next.game_settings.clear();
        save_store(&store_path(&b), &next)?;
        *store = next.clone();
        Ok(next)
    })
    .await
    .map_err(err)?
}
