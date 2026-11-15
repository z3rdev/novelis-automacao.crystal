use tauri::{AppHandle, Manager};

pub fn open(app: &AppHandle) -> Result<(), String> {
    #[cfg(debug_assertions)]
    {
        use tauri::{WebviewUrl, WebviewWindowBuilder};
        if let Some(window) = app.get_webview_window("finance-preview") {
            let _ = window.unminimize();
            window.show().map_err(|error| error.to_string())?;
            return window.set_focus().map_err(|error| error.to_string());
        }
        let window = WebviewWindowBuilder::new(
            app, "finance-preview",
            WebviewUrl::External("http://127.0.0.1:1421/#/conversas".parse().unwrap()),
        )
        .title("Cargo Hub — Financeiro · teste de mensagens")
        .inner_size(1200.0, 800.0)
        .min_inner_size(1024.0, 700.0)
        .build()
        .map_err(|error| error.to_string())?;
        crate::desktop_runtime::disable_browser_features(&window)
            .map_err(|error| error.to_string())?;
        return Ok(());
    }
    #[cfg(not(debug_assertions))]
    {
        let _ = app;
        Err("A segunda janela de teste pertence à prévia de desenvolvimento.".into())
    }
}
