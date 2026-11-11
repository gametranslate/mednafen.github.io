use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs,
    io::Write,
    path::{Path, PathBuf},
    sync::OnceLock,
};
pub type Settings = BTreeMap<String, String>;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Game {
    pub id: String,
    pub path: String,
    pub title: String,
    pub system: String,
    pub favorite: bool,
    pub last_played: Option<u64>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub struct Preferences {
    pub theme: String,
    pub engine_path: String,
    pub language: String,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            theme: "system".into(),
            engine_path: String::new(),
            language: "en".into(),
        }
    }
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub struct Store {
    pub version: u32,
    pub games: Vec<Game>,
    pub settings: Settings,
    pub game_settings: BTreeMap<String, Settings>,
    pub preferences: Preferences,
}
impl Default for Store {
    fn default() -> Self {
        Self {
            version: 1,
            games: Vec::new(),
            settings: Settings::new(),
            game_settings: BTreeMap::new(),
            preferences: Preferences::default(),
        }
    }
}
#[derive(Debug, Clone, Deserialize)]
pub struct OptionDef {
    pub value: String,
}
#[derive(Debug, Clone, Deserialize)]
pub struct Definition {
    pub key: String,
    #[serde(rename = "type")]
    pub kind: String,
    pub default: String,
    pub min: String,
    pub max: String,
    pub options: Vec<OptionDef>,
    pub aliases: Vec<String>,
}
pub fn schema() -> &'static BTreeMap<String, Definition> {
    static DEFS: OnceLock<BTreeMap<String, Definition>> = OnceLock::new();
    DEFS.get_or_init(|| {
        let defaults: Settings =
            serde_json::from_str(include_str!("../../src/data/input-defaults.json"))
                .expect("input defaults");
        serde_json::from_str::<Vec<Definition>>(include_str!("../../src/data/settings.json"))
            .expect("embedded schema")
            .into_iter()
            .map(|mut x| {
                if let Some(value) = defaults.get(&x.key) {
                    x.default = value.clone();
                }
                (x.key.clone(), x)
            })
            .collect()
    })
}
fn integer(s: &str) -> Result<i128, String> {
    if let Some(h) = s.strip_prefix("0x").or_else(|| s.strip_prefix("0X")) {
        i128::from_str_radix(h, 16)
            .map_err(|_| "Enter a valid integer or hexadecimal number.".into())
    } else {
        s.parse().map_err(|_| "Enter a valid integer.".into())
    }
}
pub fn validate_value(def: &Definition, value: &str) -> Result<(), String> {
    if value.contains(['\r', '\n', '\0']) || value.len() > 32768 {
        return Err("The value is too long or contains a line break.".into());
    }
    match def.kind.as_str() {
        "bool" if !["0", "1"].contains(&value) => return Err("Choose On or Off.".into()),
        "enum"
            if !def
                .options
                .iter()
                .any(|x| x.value.eq_ignore_ascii_case(value)) =>
        {
            return Err("Invalid option.".into())
        }
        "multi_enum"
            if value
                .split_whitespace()
                .any(|s| !def.options.iter().any(|o| o.value.eq_ignore_ascii_case(s))) =>
        {
            return Err("Invalid option list.".into())
        }
        "uint" | "int" => {
            let n = integer(value)?;
            if def.kind == "uint" && (n < 0 || n > u64::MAX as i128) {
                return Err("Enter an unsigned 64-bit integer.".into());
            }
            if def.kind == "int" && (n < i64::MIN as i128 || n > i64::MAX as i128) {
                return Err("The integer exceeds the 64-bit limit.".into());
            }
            if !def.min.is_empty() && n < integer(&def.min)?
                || !def.max.is_empty() && n > integer(&def.max)?
            {
                return Err(format!(
                    "Value must be between {} and {}.",
                    def.min, def.max
                ));
            }
        }
        "float" => {
            let n: f64 = value.parse().map_err(|_| "Enter a valid number.")?;
            if !n.is_finite() {
                return Err("Enter a finite number.".into());
            }
            if !def.min.is_empty() && n < def.min.parse().unwrap_or(f64::MIN)
                || !def.max.is_empty() && n > def.max.parse().unwrap_or(f64::MAX)
            {
                return Err(format!(
                    "Value must be between {} and {}.",
                    def.min, def.max
                ));
            }
        }
        _ => {}
    }
    Ok(())
}
pub fn validate_settings(values: &Settings) -> Result<(), String> {
    for (key, value) in values {
        let def = schema()
            .get(key)
            .ok_or_else(|| format!("Unknown setting: {key}"))?;
        validate_value(def, value).map_err(|e| format!("{key}: {e}"))?;
    }
    Ok(())
}
pub fn serialize_config(values: &Settings) -> Result<String, String> {
    validate_settings(values)?;
    let mut out = ";Mednafen Play - managed profile\n".to_string();
    for (k, v) in values {
        out.push_str(&format!("{k} {v}\n"));
    }
    Ok(out)
}
#[derive(Serialize)]
pub struct ImportResult {
    pub values: Settings,
    pub skipped: Vec<String>,
}
pub fn parse_config(text: &str) -> ImportResult {
    let mut values = Settings::new();
    let mut skipped = Vec::new();
    let aliases: BTreeMap<&str, &str> = schema()
        .values()
        .flat_map(|d| d.aliases.iter().map(move |a| (a.as_str(), d.key.as_str())))
        .collect();
    for line in text.trim_start_matches('\u{feff}').lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with(';') || line.starts_with('#') {
            continue;
        }
        let split = line.find(char::is_whitespace).unwrap_or(line.len());
        let key = &line[..split];
        let val = line[split..].trim();
        let key = aliases.get(key).copied().unwrap_or(key);
        if let Some(def) = schema().get(key) {
            if validate_value(def, val).is_ok() {
                values.insert(key.to_string(), val.to_string());
                continue;
            }
        }
        skipped.push(key.to_string());
    }
    ImportResult { values, skipped }
}
pub fn atomic_write(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let parent = path.parent().ok_or("The destination folder is missing.")?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let mut temp = tempfile::NamedTempFile::new_in(parent).map_err(|e| e.to_string())?;
    temp.write_all(bytes)
        .and_then(|_| temp.as_file().sync_all())
        .map_err(|e| e.to_string())?;
    temp.persist(path).map_err(|e| e.to_string())?;
    Ok(())
}
pub fn load_store(path: &Path) -> Result<Store, String> {
    if !path.exists() {
        return Ok(Store::default());
    }
    let bytes = fs::read(path).map_err(|e| e.to_string())?;
    let s: Store = serde_json::from_slice(&bytes).map_err(|e| {
        format!(
            "Unable to read the library. Your original data is preserved at {}: {e}",
            path.display()
        )
    })?;
    if s.version != 1 {
        return Err("Unsupported library version.".into());
    }
    Ok(s)
}
pub fn save_store(path: &Path, s: &Store) -> Result<(), String> {
    if path.exists() {
        fs::copy(path, path.with_extension("json.bak")).map_err(|e| e.to_string())?;
    }
    atomic_write(
        path,
        &serde_json::to_vec_pretty(s).map_err(|e| e.to_string())?,
    )
}
pub fn game_id(path: &Path) -> String {
    format!(
        "{:x}",
        Sha256::digest(path.to_string_lossy().to_lowercase().as_bytes())
    )[..20]
        .to_string()
}
pub fn extension(path: &Path) -> String {
    path.extension()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase()
}
pub fn detect_system(path: &Path) -> Option<&'static str> {
    Some(match extension(path).as_str() {
        "nes" | "unf" | "unif" | "fds" => "nes",
        "sfc" | "smc" => "snes",
        "gb" | "gbc" => "gb",
        "gba" | "agb" => "gba",
        "pce" | "sgx" => "pce",
        "md" | "gen" | "smd" => "md",
        "sms" => "sms",
        "gg" => "gg",
        "ngp" | "ngc" => "ngp",
        "ws" | "wsc" => "wswan",
        "vb" | "vboy" => "vb",
        "lnx" => "lynx",
        "ss" => "ss",
        "cue" | "ccd" | "toc" | "m3u" | "zip" | "gz" | "zst" => "auto",
        "mai" | "woz" | "dsk" | "do" | "po" => "apple2",
        "psf" | "minipsf" => "psx",
        "gsf" | "minigsf" => "gba",
        "ssf" | "minissf" => "ssfplay",
        _ => return None,
    })
}
pub fn descriptor_references(path: &Path) -> Result<Vec<PathBuf>, String> {
    let ext = extension(path);
    if !["m3u", "cue", "toc", "ccd"].contains(&ext.as_str()) {
        return Ok(Vec::new());
    }
    let base = path.parent().ok_or("Unable to find the game folder.")?;
    if ext == "ccd" {
        return Ok(vec![path.with_extension("img"), path.with_extension("sub")]);
    }
    let bytes = fs::read(path).map_err(|e| e.to_string())?;
    if bytes.len() > 4_000_000 {
        return Err("The disc list is too large.".into());
    }
    let txt = String::from_utf8_lossy(&bytes);
    let mut result = Vec::new();
    for line in txt.trim_start_matches('\u{feff}').lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let name = if ext == "m3u" {
            Some(line.trim_matches('"').to_string())
        } else {
            let upper = line.to_uppercase();
            if upper.starts_with("FILE ")
                || upper.starts_with("DATAFILE ")
                || upper.starts_with("AUDIOFILE ")
            {
                let rest = line
                    .split_once(char::is_whitespace)
                    .map(|(_, r)| r.trim())
                    .unwrap_or("");
                if let Some(rest) = rest.strip_prefix('"') {
                    rest.split_once('"').map(|(n, _)| n.to_string())
                } else {
                    rest.split_whitespace().next().map(str::to_string)
                }
            } else {
                None
            }
        };
        if let Some(name) = name {
            let p = base.join(name);
            result.push(p)
        }
    }
    Ok(result)
}
pub fn verify_game(path: &Path) -> Result<(), String> {
    fn walk(path: &Path, seen: &mut Vec<PathBuf>, depth: usize) -> Result<(), String> {
        if depth > 16 {
            return Err("The disc list has too many nested levels.".into());
        }
        if !path.is_file() {
            return Err(format!("File not found: {}", path.display()));
        }
        let canonical = fs::canonicalize(path).map_err(|e| e.to_string())?;
        if seen.contains(&canonical) {
            return Err("The M3U playlist contains a reference cycle.".into());
        }
        seen.push(canonical);
        for p in descriptor_references(path)? {
            walk(&p, seen, depth + 1)?;
        }
        seen.pop();
        Ok(())
    }
    walk(path, &mut Vec::new(), 0)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn config_validation_blocks_newlines() {
        let mut v = Settings::new();
        v.insert("sound.device".into(), "default\nvideo.fs 1".into());
        assert!(serialize_config(&v).is_err());
    }
    #[test]
    fn exact_large_integer_ranges() {
        let d = schema().get("affinity.emu").unwrap();
        assert!(validate_value(d, "18446744073709551615").is_ok());
        assert!(validate_value(d, "18446744073709551616").is_err());
        assert!(validate_value(d, "-1").is_err());
    }
    #[test]
    fn import_preserves_empty_strings_and_reports_unknown() {
        let r = parse_config(";note\nfs 1\nnetplay.password \nunknown 1\nsound.volume 151\n");
        assert_eq!(r.values["video.fs"], "1");
        assert_eq!(r.values["netplay.password"], "");
        assert_eq!(r.skipped.len(), 2);
    }
    #[test]
    fn no_nonfinite_numbers() {
        assert!(validate_value(schema().get("ffspeed").unwrap(), "NaN").is_err());
    }
    #[test]
    fn unicode_paths_and_atomic_backup() {
        let t = tempfile::tempdir().unwrap();
        let p = t.path().join("thư viện.json");
        let mut s = Store::default();
        save_store(&p, &s).unwrap();
        s.settings.insert("sound.volume".into(), "80".into());
        save_store(&p, &s).unwrap();
        assert_eq!(load_store(&p).unwrap().settings["sound.volume"], "80");
        assert!(p.with_extension("json.bak").exists());
    }
    #[test]
    fn cue_missing_tracks_and_m3u_cycles() {
        let t = tempfile::tempdir().unwrap();
        let cue = t.path().join("game.cue");
        fs::write(&cue, "FILE \"Disc 1.bin\" BINARY\nTRACK 01 MODE2/2352").unwrap();
        assert!(verify_game(&cue).is_err());
        fs::write(t.path().join("Disc 1.bin"), [0]).unwrap();
        assert!(verify_game(&cue).is_ok());
        let p = t.path().join("game.m3u");
        fs::write(&p, "game.m3u").unwrap();
        assert!(verify_game(&p).is_err());
    }
}
