fn main() {
    use sha2::{Digest, Sha256};
    for (name, key) in [
        ("mednafen.exe", "MP_ENGINE_SHA"),
        ("SDL2.dll", "MP_HOST_SHA"),
        ("SDL2_original.dll", "MP_SDL_SHA"),
    ] {
        let path = std::path::Path::new("resources/engine").join(name);
        println!("cargo:rerun-if-changed={}", path.display());
        let bytes = std::fs::read(path).expect("Run npm run prepare:engine first");
        println!("cargo:rustc-env={}={:x}", key, Sha256::digest(bytes));
    }
    tauri_build::build()
}
