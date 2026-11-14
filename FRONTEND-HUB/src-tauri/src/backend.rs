use std::path::PathBuf;
use std::process::Command;
use tauri_plugin_dialog::{DialogExt, MessageDialogKind};

pub fn start_installed_backend(app: tauri::AppHandle) {
    let root: PathBuf = match std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
    {
        Some(root) if root.join(".automacao-novelis-install").is_file() => root,
        _ => return, // Development builds retain their existing explicit API startup.
    };
    std::thread::spawn(move || {
        let python = root.join("BACKEND/.venv/Scripts/python.exe");
        let script = root.join("scripts/setup/launch_backend.py");
        let mut command = Command::new(python);
        command
            .arg("-I")
            .arg(script)
            .arg("--interactive-network")
            .current_dir(&root);
        command.env("NOVELIS_DESKTOP_PARENT_PID", std::process::id().to_string());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }
        command.env_remove("PYTHONHOME").env_remove("PYTHONPATH");
        let successful = command.status().map(|s| s.success()).unwrap_or(false);
        if !successful {
            crate::desktop_runtime::show_main(&app);
            app.dialog().message(format!(
                "O backend local nao iniciou. Verifique o acesso ao banco compartilhado e os logs em {}.",
                root.join("runtime").display()
            )).title("Novelis Cargo Hub").kind(MessageDialogKind::Error).blocking_show();
        }
    });
}
