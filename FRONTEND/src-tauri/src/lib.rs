#[cfg(windows)]
mod browser_embed;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let builder = tauri::Builder::default().setup(|app| {
    if cfg!(debug_assertions) {
      app.handle().plugin(
        tauri_plugin_log::Builder::default()
          .level(log::LevelFilter::Info)
          .build(),
      )?;
    }
    Ok(())
  });

  #[cfg(windows)]
  let builder = builder.invoke_handler(tauri::generate_handler![
    browser_embed::embed_browser_window,
    browser_embed::unembed_browser_window,
  ]);

  builder
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
