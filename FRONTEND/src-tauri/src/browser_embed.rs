use std::sync::Once;

use windows::core::{w, BOOL, PCWSTR};
use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, RECT, WPARAM};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::HiDpi::GetDpiForWindow;
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, EnumChildWindows, EnumWindows, GetClassNameW,
    GetClientRect, GetWindowLongPtrW, GetWindowTextLengthW, GetWindowThreadProcessId,
    IsWindowVisible, RegisterClassExW, SetParent, SetWindowLongPtrW, SetWindowPos, CS_HREDRAW,
    CS_VREDRAW, GWL_STYLE, HWND_TOP, SWP_FRAMECHANGED, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER,
    SWP_SHOWWINDOW, WINDOW_EX_STYLE, WNDCLASSEXW, WS_CAPTION, WS_CHILD, WS_POPUP, WS_THICKFRAME,
    WS_VISIBLE,
};

// Physical pixels reserved at the top of the Tauri window: the app's own
// persistent topbar (AppShell, min-height 64px) PLUS the LiveBrowserPage
// toolbar (Embutir/Desembutir/Voltar buttons, ~56px) sit above where the
// reparented Chrome window starts. GetClientRect only knows the raw window
// size — it has no idea these controls exist — so this margin is padded
// well past the ~120px both regions actually need. Better to waste a strip
// of vertical space than to make "Desembutir" unclickable.
const TOOLBAR_RESERVED_PX: i32 = 140;

// The embedded window keeps its own natural page viewport size (Playwright
// controls that separately via CDP, not the raw HWND client area) — stretching
// the OS window wider than that just leaves blank canvas, since the page
// content inside doesn't grow to match. So instead of filling the whole
// width, we only use the left share of it and leave the rest free for the
// step-controls panel the React side renders alongside it.
const BROWSER_WIDTH_FRACTION: f64 = 0.58;

// Chrome draws its own tab strip + address bar itself (not the OS non-client
// frame — that part was already confirmed removed via the WS_CAPTION style
// change below) and there is no supported way to ask it not to: launching
// with `--app=` was tried and does nothing once Playwright drives the page
// through its normal multi-tab CDP session, it still renders full chrome
// regardless of the launch flag. So instead of hiding it we crop it: an
// intermediate plain "viewport" child window is sized to the area we
// actually want visible, and Chrome's own (taller) window is placed inside
// it shifted upward by this amount. Win32 always clips a child window's
// visible area to its parent's client rect, so the tab strip/address bar —
// now sitting above the viewport's y=0 — is simply never painted or
// hit-tested; only the page content below it is. That also kills the
// "still draggable" issue, since the draggable strip is no longer part of
// what's on screen to click on.
//
// Measured against a real Chrome window at 96 DPI (tab row + toolbar row);
// scaled at runtime by the window's actual DPI. A little generous on
// purpose — cropping a few extra px of page content is harmless, leaving a
// sliver of address bar clickable is not.
const TAB_STRIP_CROP_BASE_PX: i32 = 100;

const VIEWPORT_CLASS: PCWSTR = w!("NovelisBrowserViewport");

static REGISTER_VIEWPORT_CLASS: Once = Once::new();

unsafe extern "system" fn viewport_wndproc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    DefWindowProcW(hwnd, msg, wparam, lparam)
}

fn ensure_viewport_class_registered() {
    REGISTER_VIEWPORT_CLASS.call_once(|| unsafe {
        let Ok(hinstance) = GetModuleHandleW(None) else {
            return;
        };
        let class = WNDCLASSEXW {
            cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(viewport_wndproc),
            hInstance: hinstance.into(),
            lpszClassName: VIEWPORT_CLASS,
            ..Default::default()
        };
        // Ignore failure: harmless if it's already registered (e.g. a
        // previous embed in this same process instance).
        RegisterClassExW(&class);
    });
}

struct FindByPid {
    target_pid: u32,
    found: Option<isize>,
}

unsafe extern "system" fn enum_windows_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
    let state = &mut *(lparam.0 as *mut FindByPid);
    let mut pid: u32 = 0;
    let _ = GetWindowThreadProcessId(hwnd, Some(&mut pid));
    if pid == state.target_pid && IsWindowVisible(hwnd).as_bool() && GetWindowTextLengthW(hwnd) > 0
    {
        state.found = Some(hwnd.0 as isize);
        return BOOL(0);
    }
    BOOL(1)
}

// The main Chrome process owns exactly one visible top-level window (its
// renderer/gpu/utility helper processes do not), so the first visible,
// titled window we find for this PID is the one we want — as long as it's
// still top-level. EnumWindows only walks top-level windows, so once we've
// reparented Chrome under our own viewport (below) it's no longer one, and
// this alone would go back to finding nothing on every re-embed call after
// the first. `search_root` lets the caller also look inside a specific
// window's whole descendant subtree (EnumChildWindows, unlike EnumWindows,
// recurses through grandchildren) to catch that already-embedded case.
fn find_window_by_pid(pid: u32, search_root: Option<HWND>) -> Option<HWND> {
    let mut state = FindByPid {
        target_pid: pid,
        found: None,
    };
    unsafe {
        let _ = EnumWindows(
            Some(enum_windows_proc),
            LPARAM(&mut state as *mut FindByPid as isize),
        );
        if state.found.is_none() {
            if let Some(root) = search_root {
                let _ = EnumChildWindows(
                    Some(root),
                    Some(enum_windows_proc),
                    LPARAM(&mut state as *mut FindByPid as isize),
                );
            }
        }
    }
    state.found.map(|raw| HWND(raw as *mut core::ffi::c_void))
}

struct FindViewport {
    found: Option<isize>,
}

unsafe extern "system" fn enum_child_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
    let state = &mut *(lparam.0 as *mut FindViewport);
    let mut buf = [0u16; 64];
    let len = GetClassNameW(hwnd, &mut buf);
    if len > 0 && String::from_utf16_lossy(&buf[..len as usize]) == "NovelisBrowserViewport" {
        state.found = Some(hwnd.0 as isize);
        return BOOL(0);
    }
    BOOL(1)
}

// The viewport window is created once and reused across embed calls (the
// auto-embed poll re-invokes embed_browser_window regularly to fight the
// drag issue) — searched for by class name each time rather than tracked in
// Rust-side state, matching how the Chrome window itself is looked up, and
// so it survives fine across repeated calls without leaking one window per
// tick.
fn find_viewport_child(parent: HWND) -> Option<HWND> {
    let mut state = FindViewport { found: None };
    unsafe {
        let _ = EnumChildWindows(
            Some(parent),
            Some(enum_child_proc),
            LPARAM(&mut state as *mut FindViewport as isize),
        );
    }
    state.found.map(|raw| HWND(raw as *mut core::ffi::c_void))
}

fn ensure_viewport(tauri_hwnd: HWND, x: i32, y: i32, width: i32, height: i32) -> Result<HWND, String> {
    ensure_viewport_class_registered();
    if let Some(existing) = find_viewport_child(tauri_hwnd) {
        unsafe {
            let _ = SetWindowPos(existing, None, x, y, width, height, SWP_NOZORDER | SWP_SHOWWINDOW);
        }
        return Ok(existing);
    }
    unsafe {
        let hinstance = GetModuleHandleW(None).map_err(|err| err.to_string())?;
        CreateWindowExW(
            WINDOW_EX_STYLE(0),
            VIEWPORT_CLASS,
            PCWSTR::null(),
            WS_CHILD | WS_VISIBLE,
            x,
            y,
            width,
            height,
            Some(tauri_hwnd),
            None,
            Some(hinstance.into()),
            None,
        )
        .map_err(|err| err.to_string())
    }
}

#[tauri::command]
pub fn embed_browser_window(window: tauri::WebviewWindow, pid: u32) -> Result<(), String> {
    let tauri_hwnd = window.hwnd().map_err(|err| err.to_string())?;
    let chrome_hwnd = find_window_by_pid(pid, Some(tauri_hwnd))
        .ok_or_else(|| format!("Nenhuma janela visível para o PID {pid}."))?;

    unsafe {
        let mut rect = RECT::default();
        GetClientRect(tauri_hwnd, &mut rect).map_err(|err| err.to_string())?;
        let full_width = rect.right - rect.left;
        let width = ((full_width as f64) * BROWSER_WIDTH_FRACTION).round() as i32;
        let height = (rect.bottom - rect.top - TOOLBAR_RESERVED_PX).max(0);

        let viewport_hwnd = ensure_viewport(tauri_hwnd, 0, TOOLBAR_RESERVED_PX, width, height)?;

        SetParent(chrome_hwnd, Some(viewport_hwnd)).map_err(|err| err.to_string())?;

        let style = GetWindowLongPtrW(chrome_hwnd, GWL_STYLE) as u32;
        let new_style = (style & !(WS_POPUP.0 | WS_CAPTION.0 | WS_THICKFRAME.0)) | WS_CHILD.0;
        SetWindowLongPtrW(chrome_hwnd, GWL_STYLE, new_style as isize);
        let readback = GetWindowLongPtrW(chrome_hwnd, GWL_STYLE) as u32;
        log::info!(
            "browser_embed: style before=0x{style:08X} requested=0x{new_style:08X} after=0x{readback:08X}"
        );

        let dpi = GetDpiForWindow(tauri_hwnd).max(1);
        let crop = ((TAB_STRIP_CROP_BASE_PX as f64) * (dpi as f64) / 96.0).round() as i32;

        SetWindowPos(
            chrome_hwnd,
            Some(HWND_TOP),
            0,
            -crop,
            width,
            height + crop,
            SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        )
        .map_err(|err| err.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn unembed_browser_window(window: tauri::WebviewWindow, pid: u32) -> Result<(), String> {
    let tauri_hwnd = window.hwnd().map_err(|err| err.to_string())?;
    let chrome_hwnd = find_window_by_pid(pid, Some(tauri_hwnd))
        .ok_or_else(|| format!("Nenhuma janela visível para o PID {pid}."))?;

    unsafe {
        SetParent(chrome_hwnd, None).map_err(|err| err.to_string())?;

        let style = GetWindowLongPtrW(chrome_hwnd, GWL_STYLE) as u32;
        let new_style = (style & !WS_CHILD.0) | WS_POPUP.0 | WS_CAPTION.0 | WS_THICKFRAME.0;
        SetWindowLongPtrW(chrome_hwnd, GWL_STYLE, new_style as isize);

        SetWindowPos(
            chrome_hwnd,
            None,
            0,
            0,
            0,
            0,
            SWP_FRAMECHANGED | SWP_NOZORDER | SWP_SHOWWINDOW | SWP_NOMOVE | SWP_NOSIZE,
        )
        .map_err(|err| err.to_string())?;

        if let Some(viewport_hwnd) = find_viewport_child(tauri_hwnd) {
            let _ = DestroyWindow(viewport_hwnd);
        }
    }
    Ok(())
}
