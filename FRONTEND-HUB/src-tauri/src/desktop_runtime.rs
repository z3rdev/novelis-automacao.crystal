use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, WindowEvent,
};
use tauri_plugin_autostart::ManagerExt;

pub fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

#[tauri::command]
pub fn startup_enabled(app: AppHandle) -> Result<bool, String> {
    app.autolaunch()
        .is_enabled()
        .map_err(|_| "Não foi possível consultar a inicialização com o Windows.".into())
}

#[tauri::command]
pub fn set_startup(app: AppHandle, enabled: bool) -> Result<bool, String> {
    let manager = app.autolaunch();
    if enabled {
        manager.enable()
    } else {
        manager.disable()
    }
    .map_err(|_| "Não foi possível alterar a inicialização com o Windows.".to_string())?;
    startup_enabled(app)
}

#[tauri::command]
pub fn hide_to_tray(app: AppHandle) -> Result<(), String> {
    app.get_webview_window("main")
        .ok_or("Janela principal indisponível.")?
        .hide()
        .map_err(|_| "Não foi possível ocultar a janela.".into())
}

pub fn setup(app: &mut tauri::App) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Abrir Cargo Hub", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Sair do Cargo Hub", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open, &quit])?;
    let icon = app
        .default_window_icon()
        .expect("Ícone do Cargo Hub ausente.")
        .clone();
    TrayIconBuilder::with_id("cargo-hub")
        .icon(icon)
        .tooltip("Cargo Hub — em segundo plano")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_main(app),
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main(tray.app_handle());
            }
        })
        .build(app)?;
    if let Some(window) = app.get_webview_window("main") {
        let main = window.clone();
        window.on_window_event(move |event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if main.hide().is_ok() {
                    api.prevent_close();
                }
            }
        });
        #[cfg(windows)]
        window.with_webview(|webview| unsafe {
            if let Ok(view) = webview.controller().CoreWebView2() {
                if let Ok(settings) = view.Settings() {
                    let _ = settings.SetAreDefaultContextMenusEnabled(false);
                }
            }
        })?;
        if std::env::args().any(|argument| argument == "--background") {
            window.hide()?;
        } else {
            window.show()?;
        }
    }
    Ok(())
}
