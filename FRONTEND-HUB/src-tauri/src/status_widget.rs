use std::{fs, sync::Mutex};
use tauri::{
    menu::CheckMenuItem, AppHandle, Emitter, LogicalSize, Manager, PhysicalPosition, WebviewUrl,
    WebviewWindowBuilder, WindowEvent,
};

const LABEL: &str = "status-widget";
pub struct WidgetState {
    enabled: Mutex<bool>,
    dismissed: Mutex<bool>,
    menu: Mutex<Option<CheckMenuItem<tauri::Wry>>>,
}

fn preference_path(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    app.path()
        .app_config_dir()
        .map(|path| path.join("status-widget.enabled"))
        .map_err(|_| "Não foi possível localizar as preferências do widget.".into())
}

pub fn enabled(app: &AppHandle) -> bool {
    *app.state::<WidgetState>()
        .enabled
        .lock()
        .unwrap_or_else(|error| error.into_inner())
}

pub fn register_menu(app: &AppHandle, menu: CheckMenuItem<tauri::Wry>) {
    *app.state::<WidgetState>()
        .menu
        .lock()
        .unwrap_or_else(|error| error.into_inner()) = Some(menu);
}

pub fn main_opened(app: &AppHandle) {
    *app.state::<WidgetState>()
        .dismissed
        .lock()
        .unwrap_or_else(|error| error.into_inner()) = false;
    if let Some(widget) = app.get_webview_window(LABEL) {
        let _ = widget.hide();
    }
}

pub fn sync_visibility(app: &AppHandle) {
    let background = app.get_webview_window("main").is_some_and(|main| {
        !main.is_visible().unwrap_or(true) || main.is_minimized().unwrap_or(false)
    });
    let dismissed = *app
        .state::<WidgetState>()
        .dismissed
        .lock()
        .unwrap_or_else(|error| error.into_inner());
    if let Some(widget) = app.get_webview_window(LABEL) {
        if background && enabled(app) && !dismissed {
            let _ = widget.show();
        } else {
            let _ = widget.hide();
        }
    }
    if !background {
        main_opened(app);
    }
}

pub fn set_enabled(app: &AppHandle, value: bool) -> Result<bool, String> {
    let path = preference_path(app)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|_| "Não foi possível salvar a preferência do widget.")?;
    }
    fs::write(path, if value { "true" } else { "false" })
        .map_err(|_| "Não foi possível salvar a preferência do widget.")?;
    *app.state::<WidgetState>()
        .enabled
        .lock()
        .unwrap_or_else(|error| error.into_inner()) = value;
    *app.state::<WidgetState>()
        .dismissed
        .lock()
        .unwrap_or_else(|error| error.into_inner()) = false;
    if let Some(menu) = app
        .state::<WidgetState>()
        .menu
        .lock()
        .unwrap_or_else(|error| error.into_inner())
        .as_ref()
    {
        let _ = menu.set_checked(value);
    }
    sync_visibility(app);
    Ok(value)
}

#[tauri::command]
pub fn widget_enabled(app: AppHandle) -> bool {
    enabled(&app)
}

#[tauri::command]
pub fn set_widget_enabled(app: AppHandle, enabled: bool) -> Result<bool, String> {
    set_enabled(&app, enabled)
}

#[tauri::command]
pub fn show_status_widget(app: AppHandle) -> Result<(), String> {
    set_enabled(&app, true)?;
    app.get_webview_window("main")
        .ok_or("Janela principal indisponível.")?
        .hide()
        .map_err(|_| "Não foi possível ocultar a janela principal.")?;
    sync_visibility(&app);
    Ok(())
}

#[tauri::command]
pub fn dismiss_status_widget(app: AppHandle) -> Result<(), String> {
    *app.state::<WidgetState>()
        .dismissed
        .lock()
        .unwrap_or_else(|error| error.into_inner()) = true;
    app.get_webview_window(LABEL)
        .ok_or("Widget indisponível.")?
        .hide()
        .map_err(|_| "Não foi possível ocultar o widget.".into())
}

#[tauri::command]
pub fn set_widget_compact(window: tauri::WebviewWindow, compact: bool) -> Result<(), String> {
    if window.label() != LABEL {
        return Err("Esta operação pertence ao widget.".into());
    }
    let resize = || -> tauri::Result<()> {
        let position = window.outer_position()?;
        let old_size = window.outer_size()?;
        let monitor = window.current_monitor()?;
        let (width, height) = if compact {
            (300.0, 112.0)
        } else {
            (344.0, 344.0)
        };
        window.set_size(LogicalSize::new(width, height))?;
        let size = window.outer_size()?;
        let mut x = position.x + old_size.width as i32 - size.width as i32;
        let mut y = position.y + old_size.height as i32 - size.height as i32;
        if let Some(monitor) = monitor {
            let area = monitor.work_area();
            x = x.clamp(
                area.position.x,
                (area.position.x + area.size.width as i32 - size.width as i32).max(area.position.x),
            );
            y = y.clamp(
                area.position.y,
                (area.position.y + area.size.height as i32 - size.height as i32)
                    .max(area.position.y),
            );
        }
        window.set_position(PhysicalPosition::new(x, y))?;
        Ok(())
    };
    resize().map_err(|_| "Não foi possível alterar o tamanho do widget.".into())
}

#[tauri::command]
pub fn open_main_from_widget(app: AppHandle, page: String) -> Result<(), String> {
    if !matches!(page.as_str(), "/monitor" | "/agendamentos" | "/conversas") {
        return Err("Página inválida.".into());
    }
    app.emit_to("main", "status-widget:navigate", page)
        .map_err(|_| "Não foi possível abrir a página.")?;
    crate::desktop_runtime::show_main(&app);
    Ok(())
}

pub fn setup(app: &mut tauri::App) -> tauri::Result<()> {
    let value = preference_path(app.handle())
        .ok()
        .and_then(|path| fs::read_to_string(path).ok())
        .map(|value| value.trim() != "false")
        .unwrap_or(true);
    app.manage(WidgetState {
        enabled: Mutex::new(value),
        dismissed: Mutex::new(false),
        menu: Mutex::new(None),
    });
    let widget = WebviewWindowBuilder::new(app, LABEL, WebviewUrl::App("index.html".into()))
        .title("Cargo Hub — Agendamentos")
        .inner_size(300.0, 112.0)
        .resizable(false)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .shadow(true)
        .focused(false)
        .visible(false)
        .devtools(false)
        .build()?;
    if let Some(monitor) = app
        .get_webview_window("main")
        .and_then(|main| main.current_monitor().ok().flatten())
    {
        let area = monitor.work_area();
        let size = widget.outer_size()?;
        let margin = (16.0 * monitor.scale_factor()) as i32;
        widget.set_position(PhysicalPosition::new(
            area.position.x + (area.size.width as i32 - size.width as i32 - margin).max(0),
            area.position.y + (area.size.height as i32 - size.height as i32 - margin).max(0),
        ))?;
    }
    let handle = app.handle().clone();
    widget.on_window_event(move |event| {
        if let WindowEvent::CloseRequested { api, .. } = event {
            api.prevent_close();
            let _ = dismiss_status_widget(handle.clone());
        }
    });
    crate::desktop_runtime::disable_browser_features(&widget)?;
    Ok(())
}
