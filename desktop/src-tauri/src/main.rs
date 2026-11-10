#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;

use std::sync::{
    atomic::{AtomicU16, Ordering},
    mpsc,
    Arc, Mutex,
};
use std::thread::{self, JoinHandle};
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use windows_sys::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK};

struct Lifecycle {
    stop: mpsc::Sender<()>,
    worker: Mutex<Option<JoinHandle<()>>>,
}

fn show_error(message: &str) {
    let title: Vec<u16> = "LocalLens".encode_utf16().chain([0]).collect();
    let text: Vec<u16> = message.encode_utf16().chain([0]).collect();
    unsafe {
        MessageBoxW(std::ptr::null_mut(), text.as_ptr(), title.as_ptr(), MB_OK | MB_ICONERROR);
    }
}

fn main() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let resource_dir = app.path().resource_dir()?;
            let data_dir = app.path().app_local_data_dir()?;
            let port = Arc::new(AtomicU16::new(0));
            let allowed_port = Arc::clone(&port);
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("LocalLens")
                .inner_size(1280.0, 900.0)
                .min_inner_size(360.0, 540.0)
                .on_navigation(move |url| {
                    let port = allowed_port.load(Ordering::Acquire);
                    let startup = matches!(url.host_str(), Some("tauri.localhost"))
                        && matches!(url.scheme(), "http" | "https")
                        && url.port().is_none()
                        && url.username().is_empty()
                        && url.password().is_none()
                        && matches!(url.path(), "/" | "/index.html");
                    let backend = port != 0
                        && url.scheme() == "http"
                        && url.host_str() == Some("127.0.0.1")
                        && url.port() == Some(port)
                        && url.username().is_empty()
                        && url.password().is_none();
                    startup || backend
                })
                .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
                .build()?;

            let handle = app.handle().clone();
            let (stop, signal) = mpsc::channel();
            let worker = thread::spawn(move || {
                let result = backend::supervise(
                    resource_dir.join("backend").join("locallens-backend.exe"),
                    data_dir,
                    signal,
                    |ready_port| {
                        let url = format!("http://127.0.0.1:{ready_port}/").parse()?;
                        port.store(ready_port, Ordering::Release);
                        window.navigate(url)?;
                        Ok(())
                    },
                );
                if let Err(error) = result {
                    let message = format!("LocalLens could not keep its local backend running.\n\n{error}");
                    let exit = handle.clone();
                    let _ = handle.run_on_main_thread(move || {
                        show_error(&message);
                        exit.exit(1);
                    });
                }
            });
            app.manage(Lifecycle {
                stop,
                worker: Mutex::new(Some(worker)),
            });
            Ok(())
        })
        .build(tauri::generate_context!());

    match app {
        Ok(app) => app.run(|handle, event| {
            if matches!(event, RunEvent::Exit) {
                let lifecycle = handle.state::<Lifecycle>();
                let _ = lifecycle.stop.send(());
                let worker = lifecycle.worker.lock().unwrap().take();
                if let Some(worker) = worker {
                    let _ = worker.join();
                }
            }
        }),
        Err(error) => {
            show_error(&format!("LocalLens could not open its desktop window.\n\n{error}"));
            std::process::exit(1);
        }
    }
}
