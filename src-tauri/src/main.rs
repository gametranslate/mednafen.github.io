#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod model;
mod player;
mod session;
mod qa;
use model::*;
use serde::Serialize;
use session::lifecycle_log;
use sha2::{Digest, Sha256};
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::{
    collections::BTreeSet,
    fs,
    io::Read,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    time::{SystemTime, UNIX_EPOCH},
};
use tauri::{Manager, State};
use tauri_plugin_opener::OpenerExt;

struct Running {
    child: Child,
    id: String,
    baseline: Settings,
}
struct Backend {
    store: Mutex<Store>,
    data: PathBuf,
    default_engine: PathBuf,
    running: Mutex<Option<Running>>,
    session: Mutex<()>,
    quitting: AtomicBool,
    load_error: Option<String>,
    last_error: Mutex<Option<String>>,
}
fn err<E: std::fmt::Display>(e: E) -> String {
    e.to_string()
}
fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}
fn normal(path: &Path) -> String {
    path.to_string_lossy()
        .trim_start_matches("\\\\?\\")
        .to_string()
}
fn cfg_path(b: &Backend) -> PathBuf {
    b.data.join("mednafen/mednafen.cfg")
}
fn store_path(b: &Backend) -> PathBuf {
    b.data.join("library.json")
}
fn engine_path(b: &Backend, s: &Store) -> PathBuf {
    if s.preferences.engine_path.is_empty() {
        b.default_engine.clone()
    } else {
        PathBuf::from(&s.preferences.engine_path)
    }
}
fn require_stopped(b: &Backend) -> Result<(), String> {
    refresh(b)?;
    if b.running.lock().map_err(err)?.is_some() {
        Err("Stop the game before saving settings.".into())
    } else {
        Ok(())
    }
}
fn refresh(b: &Backend) -> Result<(), String> {
    let mut active = b.running.lock().map_err(err)?;
    let done = if let Some(run) = active.as_mut() {
        run.child.try_wait().map_err(err)?
    } else {
        None
    };
    if let Some(status) = done {
        let run = active.take().unwrap();
        drop(active);
        let after = fs::read_to_string(cfg_path(b))
            .map(|s| parse_config(&s).values)
            .unwrap_or_default();
        let mut store = b.store.lock().map_err(err)?;
        for (k, v) in after {
            if schema().get(&k).is_some_and(|d| {
                (d.key.starts_with("command.") && d.key != "command.toggle_fs")
                    || d.key.contains(".input.")
            }) && run
                .baseline
                .get(&k)
                .or_else(|| schema().get(&k).map(|d| &d.default))
                != Some(&v)
            {
                if store
                    .game_settings
                    .get(&run.id)
                    .is_some_and(|s| s.contains_key(&k))
                {
                    store
                        .game_settings
                        .entry(run.id.clone())
                        .or_default()
                        .insert(k, v);
                } else {
                    store.settings.insert(k, v);
                }
            }
        }
        save_store(&store_path(b), &store)?;
        drop(store);
        if !status.success() {
            let tail = read_log(b);
            *b.last_error.lock().map_err(err)? = Some(format!(
                "Mednafen stopped (code {}). {}",
                status.code().unwrap_or(-1),
                tail
            ));
        }
    }
    Ok(())
}
fn read_log(b: &Backend) -> String {
    let dir = engine_path(b, &b.store.lock().unwrap());
    let dir = dir.parent().unwrap_or(Path::new("."));
    let paths = [
        b.data.join("mednafen/stderr.txt"),
        dir.join("stderr.txt"),
        b.data.join("mednafen/stdout.txt"),
        dir.join("stdout.txt"),
        b.data.join("mednafen/session.log"),
        b.data.join("lifecycle.log"),
    ];
    let mut text = String::new();
    for path in paths {
        if let Ok(s) = fs::read_to_string(path) {
            if !s.trim().is_empty() {
                text.push_str(&s);
                text.push('\n');
            }
        }
    }
    let chars: Vec<char> = text.chars().collect();
    chars[chars.len().saturating_sub(12000)..].iter().collect()
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct Snapshot {
    store: Store,
    data_dir: String,
    engine_path: String,
    engine_exists: bool,
    running: Option<String>,
    last_error: Option<String>,
}
#[tauri::command]
fn load_snapshot(b: State<Backend>) -> Result<Snapshot, String> {
    if let Some(e) = &b.load_error {
        return Err(e.clone());
    }
    refresh(&b)?;
    let store = b.store.lock().map_err(err)?.clone();
    let engine = engine_path(&b, &store);
    let running = b
        .running
        .lock()
        .map_err(err)?
        .as_ref()
        .map(|r| r.id.clone());
    let last_error = b.last_error.lock().map_err(err)?.take();
    Ok(Snapshot {
        store,
        data_dir: normal(&b.data),
        engine_path: normal(&engine),
        engine_exists: engine.is_file(),
        running,
        last_error,
    })
}
#[tauri::command]
fn save_settings(
    b: State<Backend>,
    scope: Option<String>,
    values: Settings,
    preferences: Option<Preferences>,
) -> Result<Store, String> {
    require_stopped(&b)?;
    validate_settings(&values)?;
    let mut store = b.store.lock().map_err(err)?;
    if b.running.lock().map_err(err)?.is_some() {
        return Err("Stop the game before saving settings.".into());
    }
    let mut next = store.clone();
    if let Some(id) = scope {
        if !next.games.iter().any(|g| g.id == id) {
            return Err("Game not found.".into());
        }
        next.game_settings.insert(id, values);
    } else {
        next.settings = values;
        if let Some(p) = preferences {
            if !["light", "dark", "system"].contains(&p.theme.as_str()) {
                return Err("Invalid theme.".into());
            }
            if !p.engine_path.is_empty() && !Path::new(&p.engine_path).is_file() {
                return Err("The selected Mednafen program was not found.".into());
            }
            next.preferences = p;
        }
    }
    save_store(&store_path(&b), &next)?;
    *store = next.clone();
    Ok(next)
}
#[tauri::command]
fn add_games(b: State<Backend>, paths: Vec<String>) -> Result<Store, String> {
    let mut store = b.store.lock().map_err(err)?;
    let mut next = store.clone();
    for path in paths {
        let path = PathBuf::from(path);
        if !path.is_file() {
            continue;
        }
        if let Some(system) = detect_system(&path) {
            let path = fs::canonicalize(path).map_err(err)?;
            let id = game_id(&path);
            if next.games.iter().any(|g| g.id == id) {
                continue;
            }
            let title = path
                .file_stem()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            next.games.push(Game {
                id,
                path: normal(&path),
                title,
                system: system.into(),
                favorite: false,
                last_played: None,
            });
        }
    }
    save_store(&store_path(&b), &next)?;
    *store = next.clone();
    Ok(next)
}
#[tauri::command]
async fn scan_folder(b: State<'_, Backend>, path: String) -> Result<Store, String> {
    let folder = PathBuf::from(path);
    if !folder.is_dir() {
        return Err("Folder not found.".into());
    }
    let paths = tauri::async_runtime::spawn_blocking(move || {
        let mut paths = Vec::new();
        for e in walkdir::WalkDir::new(folder)
            .follow_links(false)
            .max_depth(16)
            .into_iter()
            .filter_map(Result::ok)
        {
            if e.file_type().is_file() && detect_system(e.path()).is_some() {
                paths.push(normal(e.path()));
                if paths.len() > 20000 {
                    return Err(
                        "Too many games in this folder. Choose a smaller folder.".to_string()
                    );
                }
            }
        }
        let mut referenced = BTreeSet::new();
        for p in &paths {
            if extension(Path::new(p)) == "m3u" {
                for r in descriptor_references(Path::new(p)).unwrap_or_default() {
                    if let Ok(c) = fs::canonicalize(r) {
                        referenced.insert(normal(&c).to_lowercase());
                    }
                }
            }
        }
        paths.retain(|p| {
            fs::canonicalize(p)
                .map(|c| !referenced.contains(&normal(&c).to_lowercase()))
                .unwrap_or(true)
        });
        Ok(paths)
    })
    .await
    .map_err(err)??;
    add_games(b, paths)
}
#[tauri::command]
fn update_game(
    b: State<Backend>,
    id: String,
    title: String,
    system: String,
    favorite: bool,
) -> Result<Store, String> {
    if ![
        "auto",
        "apple2",
        "nes",
        "snes",
        "snes_faust",
        "gb",
        "gba",
        "pce",
        "pce_fast",
        "md",
        "sms",
        "gg",
        "psx",
        "ss",
        "pcfx",
        "ngp",
        "wswan",
        "vb",
        "lynx",
        "ssfplay",
        "sasplay",
        "cdplay",
    ]
    .contains(&system.as_str())
    {
        return Err("Invalid system.".into());
    }
    let mut store = b.store.lock().map_err(err)?;
    let mut next = store.clone();
    let g = next
        .games
        .iter_mut()
        .find(|g| g.id == id)
        .ok_or("Game not found.")?;
    g.title = title.trim().to_string();
    if g.title.is_empty() {
        return Err("Enter a game title.".into());
    }
    g.system = system;
    g.favorite = favorite;
    save_store(&store_path(&b), &next)?;
    *store = next.clone();
    Ok(next)
}
#[tauri::command]
fn remove_game(b: State<Backend>, id: String) -> Result<Store, String> {
    require_stopped(&b)?;
    let mut store = b.store.lock().map_err(err)?;
    let mut next = store.clone();
    next.games.retain(|g| g.id != id);
    next.game_settings.remove(&id);
    save_store(&store_path(&b), &next)?;
    *store = next.clone();
    Ok(next)
}
fn launch_game_inner(app: &tauri::AppHandle, b: &Backend, id: String) -> Result<u32, String> {
    if b.quitting.load(Ordering::SeqCst) {
        return Err("The app is closing.".into());
    }
    require_stopped(&b)?;
    let mut store = b.store.lock().map_err(err)?;
    if b.running.lock().map_err(err)?.is_some() {
        return Err("A game is already running. Stop it before opening another.".into());
    }
    let game = store
        .games
        .iter()
        .find(|g| g.id == id)
        .ok_or("Game not found.")?
        .clone();
    let executable = engine_path(&b, &store);
    if !executable.is_file() {
        return Err("Mednafen was not found. Check Settings → General.".into());
    }
    verify_game(Path::new(&game.path))?;
    #[cfg(windows)]
    let verified_files: Vec<(String, String)> = [
        ("mednafen.exe", env!("MP_ENGINE_SHA")),
        ("SDL2.dll", env!("MP_HOST_SHA")),
        ("SDL2_original.dll", env!("MP_SDL_SHA")),
    ].into_iter().map(|(name, hash)| (name.to_string(), hash.to_string())).collect();
    #[cfg(not(windows))]
    let verified_files: Vec<(String, String)> = serde_json::from_str::<std::collections::BTreeMap<String, String>>(env!("MP_RUNTIME_MANIFEST"))
        .map_err(err)?.into_iter().collect();
    for (name, expected) in verified_files {
        let file = executable.parent().unwrap().join(name);
        if fs::read(file)
            .map(|bytes| format!("{:x}", Sha256::digest(bytes)) != expected)
            .unwrap_or(true)
        {
            return Err("Embedded playback requires the matching bundled engine and window adapter. Clear the custom engine path in Settings → General, or reinstall this app.".into());
        }
    }
    let home = b.data.join("mednafen");
    fs::create_dir_all(&home).map_err(err)?;
    let mut values = store.settings.clone();
    if let Some(overrides) = store.game_settings.get(&id) {
        values.extend(overrides.clone());
    }
    let parent = player::parent_id(&app)?;
    values.insert("video.fs".into(), "0".into());
    // The host can resize without a Mednafen video-mode change. Clear every
    // frame so old pixels cannot remain in the newly exposed letterbox bars.
    values.insert("video.force_bbclear".into(), "1".into());
    values.insert("command.toggle_fs".into(), "".into());
    let profile = home.join("play-profile.cfg");
    atomic_write(&profile, serialize_config(&values)?.as_bytes())?;
    // The library is authoritative. Rebuild the base so reset and inheritance
    // cannot pick up stale values from an earlier emulator session.
    let mut baseline: Settings = schema()
        .values()
        .map(|d| (d.key.clone(), d.default.clone()))
        .collect();
    baseline.extend(values);
    atomic_write(&cfg_path(&b), serialize_config(&baseline)?.as_bytes())?;
    let log = fs::File::create(home.join("session.log")).map_err(err)?;
    let mut cmd = Command::new(&executable);
    cmd.env("MEDNAFEN_HOME", &home)
        .env("MEDNAFEN_NOPOPUPS", "1")
        .env("MEDNAFEN_PLAY_PARENT", parent)
        .current_dir(&home)
        .arg("-ovconfig")
        .arg(normal(&profile));
    if game.system != "auto" {
        cmd.arg("-force_module").arg(&game.system);
    }
    cmd.arg(&game.path)
        .stdin(Stdio::null())
        .stdout(log.try_clone().map_err(err)?)
        .stderr(log);
    #[cfg(windows)]
    cmd.creation_flags(0x08000000);
    player::prepare(app)?;
    player::configure_command(app, &mut cmd)?;
    let child = cmd
        .spawn()
        .map_err(|e| format!("Unable to start Mednafen: {e}"))?;
    let pid = child.id();
    lifecycle_log(b, &format!("Launching {id}; process {pid}"));
    *b.running.lock().map_err(err)? = Some(Running {
        child,
        id: id.clone(),
        baseline,
    });
    if let Some(g) = store.games.iter_mut().find(|g| g.id == id) {
        g.last_played = Some(now());
    }
    save_store(&store_path(&b), &store)?;
    Ok(pid)
}
#[tauri::command]
fn import_config(path: String) -> Result<ImportResult, String> {
    let p = Path::new(&path);
    if fs::metadata(p).map_err(err)?.len() > 10_000_000 {
        return Err("The configuration file is larger than 10 MB.".into());
    }
    Ok(parse_config(&fs::read_to_string(p).map_err(err)?))
}
#[tauri::command]
fn export_config(path: String, values: Settings) -> Result<(), String> {
    let content = serialize_config(&values)?;
    atomic_write(Path::new(&path), content.as_bytes())
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct BiosCheck {
    key: String,
    path: String,
    exists: bool,
    sha256: Option<String>,
    matches: Option<bool>,
}
#[tauri::command]
async fn check_bios(b: State<'_, Backend>, values: Settings) -> Result<Vec<BiosCheck>, String> {
    let home = b.data.join("mednafen");
    tauri::async_runtime::spawn_blocking(move || {
        let expected = [
            (
                "psx.bios_jp",
                "9c0421858e217805f4abe18698afea8d5aa36ff0727eb8484944e00eb5e7eadb",
            ),
            (
                "psx.bios_na",
                "11052b6499e466bbf0a709b1f9cb6834a9418e66680387912451e971cf8a1fef",
            ),
            (
                "psx.bios_eu",
                "1faaa18fa820a0225e488d9f086296b8e6c46df739666093987ff7d8fd352c09",
            ),
            (
                "ss.bios_jp",
                "dcfef4b99605f872b6c3b6d05c045385cdea3d1b702906a0ed930df7bcb7deac",
            ),
            (
                "ss.bios_na_eu",
                "96e106f740ab448cf89f0dd49dfbac7fe5391cb6bd6e14ad5e3061c13330266f",
            ),
        ];
        let fw = values
            .get("filesys.path_firmware")
            .map(String::as_str)
            .unwrap_or("firmware");
        let folder = home.join(fw);
        let mut out = Vec::new();
        for def in schema().values().filter(|d| {
            d.kind == "string"
                && (d.key.contains("bios") || d.key.contains("firmware"))
                && !d.key.starts_with("filesys.")
        }) {
            let val = values.get(&def.key).unwrap_or(&def.default);
            if val.is_empty() {
                continue;
            }
            let first = folder.join(val);
            let path = if first.is_file() {
                first
            } else {
                let alt = home.join(val);
                if alt.is_file() {
                    alt
                } else {
                    first
                }
            };
            let exists = path.is_file();
            let hash = if exists && fs::metadata(&path).map_err(err)?.len() < 32_000_000 {
                let mut file = fs::File::open(&path).map_err(err)?;
                let mut hasher = Sha256::new();
                let mut buf = [0u8; 65536];
                loop {
                    let n = file.read(&mut buf).map_err(err)?;
                    if n == 0 {
                        break;
                    }
                    hasher.update(&buf[..n]);
                }
                Some(format!("{:x}", hasher.finalize()))
            } else {
                None
            };
            let matches = expected
                .iter()
                .find(|(k, _)| *k == def.key)
                .and_then(|(_, h)| hash.as_ref().map(|actual| actual == h));
            out.push(BiosCheck {
                key: def.key.clone(),
                path: normal(&path),
                exists,
                sha256: hash,
                matches,
            });
        }
        Ok(out)
    })
    .await
    .map_err(err)?
}
#[tauri::command]
fn open_data_folder(app: tauri::AppHandle, b: State<Backend>, kind: String) -> Result<(), String> {
    let path = match kind.as_str() {
        "data" => b.data.clone(),
        "firmware" => b.data.join("mednafen/firmware"),
        "saves" => b.data.join("mednafen/sav"),
        "states" => b.data.join("mednafen/mcs"),
        "screenshots" => b.data.join("mednafen/snaps"),
        _ => return Err("Invalid folder.".into()),
    };
    fs::create_dir_all(&path).map_err(err)?;
    app.opener()
        .open_path(normal(&path), None::<&str>)
        .map_err(err)
}
#[tauri::command]
fn open_game_translate(app: tauri::AppHandle) -> Result<(), String> {
    app.opener()
        .open_url("https://gametranslate.us", None::<&str>)
        .map_err(err)
}
#[tauri::command]
fn get_log(b: State<Backend>) -> String {
    read_log(&b)
}
#[tauri::command]
fn save_appearance(
    b: State<Backend>,
    theme: Option<String>,
    language: Option<String>,
) -> Result<Store, String> {
    let mut store = b.store.lock().map_err(err)?;
    let mut next = store.clone();
    if let Some(t) = theme {
        if !["light", "dark", "system"].contains(&t.as_str()) {
            return Err("Invalid theme.".into());
        }
        next.preferences.theme = t;
    }
    if let Some(l) = language {
        if ![
            "en", "de", "vi", "fr", "es", "it", "ko", "zh-TW", "zh-CN", "ja",
        ]
        .contains(&l.as_str())
        {
            return Err("Invalid language.".into());
        }
        next.preferences.language = l;
    }
    save_store(&store_path(&b), &next)?;
    *store = next.clone();
    Ok(next)
}
#[tauri::command]
fn open_project_link(app: tauri::AppHandle, key: String) -> Result<(), String> {
    let url = match key.as_str() {
        "mednafen" => "https://github.com/mednafen/mednafen.github.io",
        "credits" => "https://mednafen.github.io/documentation/mednafen.html#Section_legal",
        "source" => "https://mednafen.github.io/releases/files/mednafen-1.32.1.tar.xz",
        "sdl" => "https://github.com/libsdl-org/SDL",
        "tauri" => "https://github.com/tauri-apps/tauri",
        "react" => "https://github.com/facebook/react",
        "lucide" => "https://github.com/lucide-icons/lucide",
        _ => return Err("Unknown project link.".into()),
    };
    app.opener().open_url(url, None::<&str>).map_err(err)
}
fn main() {
    let mut context = tauri::generate_context!();
    if std::env::var_os("MEDNAFEN_PLAY_TEST_HOME").is_some()
        && std::env::var_os("MEDNAFEN_PLAY_BACKGROUND_QA").is_some()
    {
        for window in &mut context.config_mut().app.windows {
            window.visible = false;
            window.focus = false;
        }
    }
    tauri::Builder::default()
        .on_page_load(qa::page_loaded)
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(player::Player::default())
        .setup(|app| {
            let data = std::env::var_os("MEDNAFEN_PLAY_TEST_HOME")
                .map(PathBuf::from)
                .unwrap_or(app.path().app_data_dir()?);
            fs::create_dir_all(data.join("mednafen"))?;
            let store_result = load_store(&data.join("library.json"));
            let load_error = store_result.as_ref().err().cloned();
            let resource = app
                .path()
                .resource_dir()?
                .join("resources/engine").join(env!("MP_ENGINE_NAME"));
            let fallback =
                Path::new(env!("CARGO_MANIFEST_DIR")).join("resources/engine").join(env!("MP_ENGINE_NAME"));
            let default_engine = if resource.is_file() {
                resource
            } else {
                fallback
            };
            app.manage(Backend {
                store: Mutex::new(store_result.unwrap_or_default()),
                data,
                default_engine,
                running: Mutex::new(None),
                session: Mutex::new(()),
                quitting: AtomicBool::new(false),
                load_error,
                last_error: Mutex::new(None),
            });
            player::install_drop_receiver(app.handle())?;
            player::start(app.handle().clone());
            session::supervise(app.handle().clone());
            Ok(())
        })
        .on_window_event(|window, event| {
            // Last resort when Windows destroys the host without a normal close request.
            if window.label() == "main" && matches!(event, tauri::WindowEvent::Destroyed) {
                let b = window.state::<Backend>();
                b.quitting.store(true, Ordering::SeqCst);
                if let Some(mut run) = b.running.lock().unwrap().take() {
                    let _ = run.child.kill();
                    let _ = run.child.wait();
                };
            }
        })
        .invoke_handler(tauri::generate_handler![
            qa::qa_context,
            qa::qa_probe,
            qa::qa_report,
            player::player_bounds,
            player::player_visible,
            player::player_fullscreen,
            player::player_status,
            player::player_frame,
            session::stop_game,
            player::focus_game,
            player::player_key,
            player::player_release_keys,
            session::quit_app,
            session::clear_library,
            session::prepare_dropped_game,
            load_snapshot,
            save_settings,
            add_games,
            scan_folder,
            update_game,
            remove_game,
            session::launch_game,
            import_config,
            export_config,
            check_bios,
            open_data_folder,
            open_game_translate,
            get_log,
            save_appearance,
            open_project_link
        ])
        .run(context)
        .expect("Unable to start Mednafen Play");
}
