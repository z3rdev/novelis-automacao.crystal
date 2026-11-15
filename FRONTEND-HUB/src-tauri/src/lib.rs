#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, args, _cwd| {
            if args.iter().any(|argument| argument == "--finance-preview") {
                let handle = app.clone();
                std::thread::spawn(move || { let _ = finance_preview::open(&handle); });
                return;
            }
            if !args.iter().any(|argument| argument == "--background") {
                desktop_runtime::show_main(app);
            }
        }))
        .plugin(
            tauri_plugin_autostart::Builder::new()
                .app_name("Novelis Cargo Hub")
                .args(["--background"])
                .build(),
        )
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            desktop_runtime::startup_enabled,
            desktop_runtime::set_startup,
            desktop_runtime::hide_to_tray,
            status_widget::widget_enabled,
            status_widget::set_widget_enabled,
            status_widget::show_status_widget,
            status_widget::dismiss_status_widget,
            status_widget::set_widget_compact,
            status_widget::open_main_from_widget,
            notifications::play_notification_sound,
            device::device_identity,
            network::network_status
        ])
        .setup(|app| {
            status_widget::setup(app)?;
            desktop_runtime::setup(app)?;
            backend::start_installed_backend(app.handle().clone());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Falha ao iniciar o Novelis Cargo Hub");
}
mod backend;
mod desktop_runtime;
mod device;
mod network;
mod status_widget;
mod notifications;
mod finance_preview;
