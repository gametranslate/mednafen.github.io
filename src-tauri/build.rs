fn main() {
    use sha2::{Digest, Sha256};
    let windows = std::env::var("CARGO_CFG_TARGET_OS").unwrap() == "windows";
    println!("cargo:rustc-env=MP_ENGINE_NAME={}", if windows { "mednafen.exe" } else { "mednafen" });
    if !windows {
        let manifest = "resources/engine/RUNTIME-MANIFEST.json";
        println!("cargo:rerun-if-changed=resources/engine");
        let data = std::fs::read_to_string(manifest).expect("Run python3 scripts/prepare_unix.py first");
        println!("cargo:rustc-env=MP_RUNTIME_MANIFEST={}", data.replace('\n', ""));
        tauri_build::build();
        return;
    }
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
