use std::env;

#[derive(serde::Serialize)]
pub struct DeviceIdentity {
    windows_user: String,
    computer_name: String,
    mac_addresses: Vec<String>,
}

fn basic_identity() -> DeviceIdentity {
    let user = env::var("USERNAME").unwrap_or_default();
    let domain = env::var("USERDOMAIN").unwrap_or_default();
    DeviceIdentity {
        windows_user: if domain.is_empty() {
            user
        } else {
            format!("{domain}\\{user}")
        },
        computer_name: env::var("COMPUTERNAME").unwrap_or_else(|_| "Dispositivo local".into()),
        mac_addresses: Vec::new(),
    }
}

fn read_identity() -> DeviceIdentity {
    let mut result = basic_identity();
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        use std::process::{Command, Stdio};
        let system =
            std::path::PathBuf::from(env::var_os("WINDIR").unwrap_or_else(|| "C:\\Windows".into()));
        if let Ok(output) = Command::new(system.join("System32/getmac.exe"))
            .args(["/fo", "csv", "/nh"])
            .stdin(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x08000000)
            .output()
        {
            for line in String::from_utf8_lossy(&output.stdout).lines() {
                let address = line
                    .split(',')
                    .next()
                    .unwrap_or("")
                    .trim_matches('"')
                    .replace('-', ":")
                    .to_uppercase();
                let parts: Vec<_> = address.split(':').collect();
                if parts.len() == 6
                    && parts
                        .iter()
                        .all(|part| part.len() == 2 && u8::from_str_radix(part, 16).is_ok())
                    && address != "00:00:00:00:00:00"
                    && u8::from_str_radix(parts[0], 16).unwrap_or(1) & 1 == 0
                {
                    result.mac_addresses.push(address);
                }
            }
            result.mac_addresses.sort();
            result.mac_addresses.dedup();
        }
    }
    result
}

#[tauri::command]
pub async fn device_identity() -> DeviceIdentity {
    tauri::async_runtime::spawn_blocking(read_identity)
        .await
        .unwrap_or_else(|_| basic_identity())
}
