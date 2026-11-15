#[tauri::command]
pub fn play_notification_sound() -> Result<(), String> {
    #[cfg(windows)]
    unsafe {
        use windows_sys::Win32::System::Diagnostics::Debug::MessageBeep;
        use windows_sys::Win32::UI::WindowsAndMessaging::MB_ICONINFORMATION;
        if MessageBeep(MB_ICONINFORMATION) == 0 {
            return Err("Não foi possível tocar o som de notificação.".into());
        }
    }
    Ok(())
}
