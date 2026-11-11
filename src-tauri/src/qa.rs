//! Opt-in isolated package tests. Disabled unless both explicit QA environment
//! variables are set by the test runner; never reads the normal user profile.
use crate::*;
fn directory() -> Result<PathBuf, String> {
    if std::env::var_os("MEDNAFEN_PLAY_QA_SCRIPT").is_none() { return Err("QA is disabled".into()); }
    std::env::var_os("MEDNAFEN_PLAY_TEST_HOME").map(PathBuf::from).ok_or("QA is disabled".into())
}
#[tauri::command]
pub fn qa_context(b: State<Backend>) -> Result<serde_json::Value, String> {
    directory()?;
    if let Some(root) = std::env::var_os("MEDNAFEN_PLAY_EXPECT_RESOURCE_ROOT") {
        let expected = PathBuf::from(root).canonicalize().map_err(err)?;
        if !b.default_engine.canonicalize().map_err(err)?.starts_with(expected) {
            return Err("Package test resolved an engine outside the extracted package".into());
        }
    }
    Ok(serde_json::json!({"rom": std::env::var("MEDNAFEN_PLAY_TEST_ROM").map_err(err)?,
        "driver": std::env::var("MEDNAFEN_PLAY_QA_DRIVER").unwrap_or("softfb".into())}))
}
#[tauri::command]
pub fn qa_probe(app: tauri::AppHandle, slot: u8, checkpoint: Option<String>) -> Result<serde_json::Value, String> {
    let home = directory()?;
    if slot > 9 { return Err("Invalid slot".into()); }
    let folder = home.join("mednafen/mcs");
    let file = fs::read_dir(folder).ok().and_then(|entries| entries.flatten().map(|e| e.path())
        .find(|p| p.extension().is_some_and(|s| s == format!("mc{slot}").as_str())));
    let hash = if let Some(path) = file {
        let bytes = fs::read(&path).map_err(err)?;
        if let Some(name) = checkpoint {
            if name.is_empty() || name.len() > 40 || !name.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'-') {
                return Err("Invalid checkpoint name".into());
            }
            fs::write(home.join(format!("{name}.state")), &bytes).map_err(err)?;
        }
        Some(format!("{:x}", Sha256::digest(&bytes)))
    } else { None };
    let pid = app.state::<Backend>().running.lock().map_err(err)?.as_ref().map(|r| r.child.id());
    Ok(serde_json::json!({"hash": hash, "pid": pid,
        "fullscreen": app.get_webview_window("main").ok_or("Window unavailable")?.is_fullscreen().map_err(err)?}))
}
#[tauri::command]
pub fn qa_report(report: serde_json::Value) -> Result<(), String> {
    let home = directory()?;
    fs::write(home.join("ui-result.json"), serde_json::to_vec_pretty(&report).map_err(err)?).map_err(err)
}
#[tauri::command]
pub fn qa_request_close(app: tauri::AppHandle) -> Result<(), String> {
    directory()?;
    #[cfg(target_os = "macos")]
    app.exit(0); // Same native exit path as Cmd+Q; no global input injection.
    #[cfg(not(target_os = "macos"))]
    app.get_webview_window("main").ok_or("Window unavailable")?.close().map_err(err)?;
    Ok(())
}
pub fn page_loaded(webview: &tauri::Webview, payload: &tauri::webview::PageLoadPayload<'_>) {
    if payload.event() != tauri::webview::PageLoadEvent::Finished || directory().is_err() { return; }
    let Some(path) = std::env::var_os("MEDNAFEN_PLAY_QA_SCRIPT") else { return; };
    if let Ok(script) = fs::read_to_string(path) {
        if script.len() <= 262144 { let _ = webview.eval(&script); }
    }
}
