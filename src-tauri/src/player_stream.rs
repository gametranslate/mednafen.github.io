//! Linux/macOS display transport. Only a private, per-launch Unix socket is
//! exposed; the child keeps emulation/audio and the WebView draws RGBA frames.
use super::*;
use std::{
    io::{Read, Write},
    net::Shutdown,
    os::unix::{fs::PermissionsExt, net::{UnixListener, UnixStream}},
    process::Command,
    sync::{Arc, atomic::{AtomicBool, AtomicU32, AtomicU64}},
    time::{Duration, Instant},
};

const MAX_DIMENSION: u32 = 4096;
#[derive(Default)]
struct Connection {
    ended: AtomicBool,
    connected: AtomicBool,
    pid: AtomicU32,
    frames: AtomicU64,
    latest: Mutex<Vec<u8>>,
    writer: Mutex<Option<UnixStream>>,
}
struct Session {
    directory: tempfile::TempDir,
    connection: Arc<Connection>,
}
impl Drop for Session {
    fn drop(&mut self) {
        self.connection.ended.store(true, Ordering::SeqCst);
        if let Some(stream) = self.connection.writer.lock().unwrap().take() {
            let _ = stream.shutdown(Shutdown::Both);
        }
    }
}
#[derive(Default)]
pub struct Bridge {
    session: Mutex<Option<Session>>,
}
fn connection(app: &tauri::AppHandle) -> Option<Arc<Connection>> {
    app.state::<Player>().bridge.session.lock().ok()?.as_ref().map(|s| s.connection.clone())
}
pub fn prepare(app: &tauri::AppHandle) -> Result<(), String> {
    let state = app.state::<Player>();
    let mut slot = state.bridge.session.lock().map_err(crate::err)?;
    // /tmp keeps sockaddr_un paths short even with macOS's long user temp paths.
    let directory = tempfile::Builder::new().prefix("mednafen-play-").tempdir_in("/tmp").map_err(crate::err)?;
    std::fs::set_permissions(directory.path(), std::fs::Permissions::from_mode(0o700)).map_err(crate::err)?;
    let path = directory.path().join("display.sock");
    let listener = UnixListener::bind(&path).map_err(crate::err)?;
    std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600)).map_err(crate::err)?;
    listener.set_nonblocking(true).map_err(crate::err)?;
    let shared = Arc::new(Connection::default());
    *slot = Some(Session { directory, connection: shared.clone() });
    let handle = app.clone();
    std::thread::spawn(move || {
        let result = receive(&listener, &shared);
        shared.connected.store(false, Ordering::SeqCst);
        if let Some(stream) = shared.writer.lock().unwrap().take() {
            let _ = stream.shutdown(Shutdown::Both);
        }
        if let Err(error) = result {
            if !shared.ended.load(Ordering::SeqCst) {
                crate::lifecycle_log(&handle.state::<crate::Backend>(), &format!("Display transport closed: {error}"));
            }
        }
    });
    Ok(())
}
fn receive(listener: &UnixListener, shared: &Connection) -> std::io::Result<()> {
    let deadline = Instant::now() + Duration::from_secs(20);
    let mut stream = loop {
        if shared.ended.load(Ordering::SeqCst) || Instant::now() >= deadline { return Ok(()); }
        match listener.accept() {
            Ok((stream, _)) => break stream,
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => std::thread::sleep(Duration::from_millis(10)),
            Err(e) => return Err(e),
        }
    };
    // macOS inherits O_NONBLOCK from the listener; Linux does not. Frame reads
    // must wait for complete messages instead of treating EAGAIN as disconnect.
    stream.set_nonblocking(false)?;
    stream.set_read_timeout(Some(Duration::from_secs(10)))?;
    stream.set_write_timeout(Some(Duration::from_millis(250)))?;
    let mut hello = [0u8; 8];
    stream.read_exact(&mut hello)?;
    if &hello[..4] != b"MPH1" { return Err(invalid("Invalid display handshake")); }
    shared.pid.store(u32::from_le_bytes(hello[4..8].try_into().unwrap()), Ordering::SeqCst);
    // Pausing/debugging emulation may legitimately stop frame production.
    // Session teardown shuts down this socket to wake a blocked reader.
    stream.set_read_timeout(None)?;
    *shared.writer.lock().unwrap() = Some(stream.try_clone()?);
    shared.connected.store(true, Ordering::SeqCst);
    while !shared.ended.load(Ordering::SeqCst) {
        let mut header = [0u8; 24];
        stream.read_exact(&mut header)?;
        let (width, height, length, sequence) = decode_header(&header)?;
        let mut frame = vec![0u8; 16 + length];
        frame[..8].copy_from_slice(&sequence.to_le_bytes());
        frame[8..12].copy_from_slice(&width.to_le_bytes());
        frame[12..16].copy_from_slice(&height.to_le_bytes());
        stream.read_exact(&mut frame[16..])?;
        *shared.latest.lock().unwrap() = frame;
        shared.frames.store(sequence, Ordering::SeqCst);
    }
    Ok(())
}
fn invalid(message: &str) -> std::io::Error {
    std::io::Error::new(std::io::ErrorKind::InvalidData, message)
}
fn decode_header(header: &[u8; 24]) -> std::io::Result<(u32, u32, usize, u64)> {
    let word = |at| u32::from_le_bytes(header[at..at + 4].try_into().unwrap());
    let width = word(4);
    let height = word(8);
    let length = word(12) as usize;
    let sequence = u64::from_le_bytes(header[16..24].try_into().unwrap());
    if &header[..4] != b"MPF1" || width == 0 || height == 0 || width > MAX_DIMENSION || height > MAX_DIMENSION
        || length != width as usize * height as usize * 4 || sequence == 0 {
        return Err(invalid("Invalid display frame"));
    }
    Ok((width, height, length, sequence))
}
pub fn configure_command(app: &tauri::AppHandle, command: &mut Command) -> Result<(), String> {
    let state = app.state::<Player>();
    let session = state.bridge.session.lock().map_err(crate::err)?;
    let session = session.as_ref().ok_or("Display transport unavailable")?;
    command.env("MEDNAFEN_PLAY_SOCKET", session.directory.path().join("display.sock"))
        .env("SDL_MAC_BACKGROUND_APP", "1").env("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1");
    Ok(())
}
pub fn parent_id(_: &tauri::AppHandle) -> Result<String, String> { Ok("canvas".into()) }
pub fn child(app: &tauri::AppHandle) -> Option<usize> {
    let shared = connection(app)?;
    if !shared.connected.load(Ordering::SeqCst) { return None; }
    let pid = shared.pid.load(Ordering::SeqCst);
    let state = app.state::<crate::Backend>();
    let running = state.running.lock().ok()?;
    running.as_ref().filter(|r| r.child.id() == pid).map(|_| pid as usize)
}
pub fn frames(app: &tauri::AppHandle) -> u64 {
    if child(app).is_none() { return 0; }
    connection(app).map(|c| c.frames.load(Ordering::SeqCst)).unwrap_or(0)
}
pub fn frame(app: &tauri::AppHandle, after: u64) -> Vec<u8> {
    if child(app).is_none() || !*app.state::<Player>().visible.lock().unwrap() { return Vec::new(); }
    let Some(shared) = connection(app) else { return Vec::new(); };
    let frame = shared.latest.lock().unwrap();
    if frame.len() < 16 || u64::from_le_bytes(frame[..8].try_into().unwrap()) == after { Vec::new() } else { frame.clone() }
}
fn send(app: &tauri::AppHandle, kind: u32, code: u32, flags: u32, character: u32) -> Result<(), String> {
    let Some(shared) = connection(app) else { return Ok(()); };
    let mut writer = shared.writer.lock().map_err(crate::err)?;
    let Some(writer) = writer.as_mut() else { return Ok(()); };
    let mut message = [0u8; 16];
    for (i, value) in [kind, code, flags, character].iter().enumerate() {
        message[i * 4..i * 4 + 4].copy_from_slice(&value.to_le_bytes());
    }
    writer.write_all(&message).map_err(crate::err)
}
pub fn key(app: &tauri::AppHandle, scancode: u32, down: bool, modifiers: u16, character: Option<u32>) -> Result<(), String> {
    if scancode == 0 || scancode >= 512 { return Err("Invalid key.".into()); }
    if !*app.state::<Player>().visible.lock().unwrap() { return Ok(()); }
    send(app, 1, scancode, ((modifiers as u32) << 16) | down as u32, character.unwrap_or(0))
}
pub fn release_keys(app: &tauri::AppHandle) { let _ = send(app, 2, 0, 0, 0); }
pub fn stop(app: &tauri::AppHandle) -> Result<(), String> { send(app, 3, 0, 0, 0) }
pub fn focus(_: &tauri::AppHandle) -> Result<(), String> { Ok(()) }
pub fn install_drop_receiver(_: &tauri::AppHandle) -> Result<(), String> { Ok(()) }
pub fn fullscreen(app: &tauri::AppHandle, value: bool) -> Result<(), String> {
    let window = app.get_webview_window("main").ok_or("Window unavailable")?;
    if !(std::env::var_os("MEDNAFEN_PLAY_TEST_HOME").is_some() && std::env::var_os("MEDNAFEN_PLAY_BACKGROUND_QA").is_some()) {
        window.set_fullscreen(value).map_err(crate::err)?;
    }
    *app.state::<Player>().fullscreen.lock().unwrap() = value;
    app.emit("player-fullscreen", value).map_err(crate::err)
}
pub fn tick(app: &tauri::AppHandle) {
    if *app.state::<Player>().fullscreen.lock().unwrap() && app.state::<crate::Backend>().running.lock().unwrap().is_none() {
        let _ = fullscreen(app, false);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn accepts_delayed_fragmented_messages_from_nonblocking_listener() {
        let directory = tempfile::Builder::new().prefix("mp-socket-test-").tempdir_in("/tmp").unwrap();
        let path = directory.path().join("display.sock");
        let listener = UnixListener::bind(&path).unwrap();
        listener.set_nonblocking(true).unwrap();
        let shared = Arc::new(Connection::default());
        let receiver_state = shared.clone();
        let receiver = std::thread::spawn(move || receive(&listener, &receiver_state));
        let mut client = UnixStream::connect(path).unwrap();
        client.set_write_timeout(Some(Duration::from_secs(2))).unwrap();
        std::thread::sleep(Duration::from_millis(40));
        client.write_all(b"MP").unwrap();
        std::thread::sleep(Duration::from_millis(40));
        client.write_all(&[b'H', b'1', 123, 0, 0, 0]).unwrap();
        let mut header = [0u8; 24];
        header[..4].copy_from_slice(b"MPF1");
        header[4..8].copy_from_slice(&1u32.to_le_bytes());
        header[8..12].copy_from_slice(&1u32.to_le_bytes());
        header[12..16].copy_from_slice(&4u32.to_le_bytes());
        header[16..24].copy_from_slice(&1u64.to_le_bytes());
        client.write_all(&header[..7]).unwrap();
        std::thread::sleep(Duration::from_millis(40));
        client.write_all(&header[7..]).unwrap();
        client.write_all(&[12, 34, 56, 255]).unwrap();
        client.shutdown(Shutdown::Write).unwrap();
        assert_eq!(receiver.join().unwrap().unwrap_err().kind(), std::io::ErrorKind::UnexpectedEof);
        assert_eq!(shared.pid.load(Ordering::SeqCst), 123);
        assert_eq!(shared.frames.load(Ordering::SeqCst), 1);
        assert_eq!(&shared.latest.lock().unwrap()[16..], &[12, 34, 56, 255]);
    }
    #[test]
    fn rejects_bad_or_oversized_frames_before_allocation() {
        let mut h = [0u8; 24]; h[..4].copy_from_slice(b"MPF1");
        h[4..8].copy_from_slice(&256u32.to_le_bytes()); h[8..12].copy_from_slice(&240u32.to_le_bytes());
        h[12..16].copy_from_slice(&(256u32 * 240 * 4).to_le_bytes()); h[16..24].copy_from_slice(&1u64.to_le_bytes());
        assert_eq!(decode_header(&h).unwrap(), (256, 240, 245760, 1));
        h[4..8].copy_from_slice(&u32::MAX.to_le_bytes()); assert!(decode_header(&h).is_err());
        h[4..8].copy_from_slice(&256u32.to_le_bytes()); h[12..16].copy_from_slice(&4u32.to_le_bytes()); assert!(decode_header(&h).is_err());
        h[..4].copy_from_slice(b"BAD!"); assert!(decode_header(&h).is_err());
    }
}
