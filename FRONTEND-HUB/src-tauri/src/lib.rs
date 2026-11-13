#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            backend::start_installed_backend(app.handle().clone());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Falha ao iniciar o Novelis Cargo Hub");
}
mod backend;
