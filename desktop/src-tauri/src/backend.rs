use std::{
    ffi::c_void,
    io::{self, BufRead, BufReader, Read, Write},
    os::windows::{io::AsRawHandle, process::CommandExt},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::mpsc::{self, Receiver, RecvTimeoutError},
    thread,
    time::{Duration, Instant},
};
use windows_sys::Win32::{
    Foundation::{CloseHandle, HANDLE},
    System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    },
};

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const POLL: Duration = Duration::from_millis(150);
const START_TIMEOUT: Duration = Duration::from_secs(60);
const STOP_TIMEOUT: Duration = Duration::from_secs(6);

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

struct Job(HANDLE);

impl Job {
    fn new() -> io::Result<Self> {
        let handle = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
        if handle.is_null() {
            return Err(io::Error::last_os_error());
        }
        let job = Self(handle);
        let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let result = unsafe {
            SetInformationJobObject(
                job.0,
                JobObjectExtendedLimitInformation,
                (&limits as *const JOBOBJECT_EXTENDED_LIMIT_INFORMATION).cast::<c_void>(),
                std::mem::size_of_val(&limits) as u32,
            )
        };
        if result == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(job)
    }

    fn attach(&self, child: &Child) -> io::Result<()> {
        if unsafe { AssignProcessToJobObject(self.0, child.as_raw_handle() as HANDLE) } == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
}

impl Drop for Job {
    fn drop(&mut self) {
        unsafe { CloseHandle(self.0) };
    }
}

fn read_lines(pipe: impl Read + Send + 'static) -> Receiver<String> {
    let (send, receive) = mpsc::channel();
    thread::spawn(move || {
        for line in BufReader::new(pipe).lines().map_while(std::result::Result::ok) {
            if send.send(line).is_err() {
                break;
            }
        }
    });
    receive
}

fn graceful_stop(child: &mut Child) -> io::Result<()> {
    drop(child.stdin.take());
    let deadline = Instant::now() + STOP_TIMEOUT;
    while Instant::now() < deadline {
        if child.try_wait()?.is_some() {
            return Ok(());
        }
        thread::sleep(POLL);
    }
    child.kill()?;
    child.wait()?;
    Ok(())
}

pub fn supervise(
    executable: PathBuf,
    data_dir: PathBuf,
    stop: Receiver<()>,
    on_ready: impl FnOnce(u16) -> Result<()>,
) -> Result<()> {
    if !executable.is_file() {
        return Err("The bundled backend is missing. Reinstall LocalLens.".into());
    }
    std::fs::create_dir_all(&data_dir)?;
    let job = Job::new()?;
    let mut child = Command::new(executable)
        .arg("--desktop-sidecar")
        .current_dir(&data_dir)
        .env("LOCALLENS_DATA", &data_dir)
        .env("PYTHONUTF8", "1")
        .env_remove("LOCALLENS_LEGACY_UI")
        .env_remove("PYTHONHOME")
        .env_remove("PYTHONPATH")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()?;
    if let Err(error) = job.attach(&child) {
        let _ = child.kill();
        let _ = child.wait();
        return Err(format!("Could not supervise the backend process: {error}").into());
    }

    child.stdin.as_mut().unwrap().write_all(&[1])?;
    let output = read_lines(child.stdout.take().unwrap());
    let errors = read_lines(child.stderr.take().unwrap());
    let startup_deadline = Instant::now() + START_TIMEOUT;
    let mut ready = Some(on_ready);
    loop {
        match stop.recv_timeout(POLL) {
            Ok(()) | Err(RecvTimeoutError::Disconnected) => {
                graceful_stop(&mut child)?;
                return Ok(());
            }
            Err(RecvTimeoutError::Timeout) => {}
        }
        if let Some(status) = child.try_wait()? {
            let detail = errors.try_iter().filter(|line| !line.trim().is_empty()).last();
            return Err(match detail {
                Some(detail) => format!("Backend exited ({status}). {detail}"),
                None => format!("Backend exited ({status})."),
            }
            .into());
        }
        if ready.is_some() {
            let port = output.try_iter().find_map(|line| {
                line.strip_prefix("LOCALLENS_READY ")?
                    .parse::<u16>()
                    .ok()
                    .filter(|port| *port != 0)
            });
            if let Some(port) = port {
                ready.take().unwrap()(port)?;
            } else if Instant::now() >= startup_deadline {
                return Err("The backend did not start within 60 seconds.".into());
            }
        } else {
            // Drain diagnostic output while the backend is running.
            output.try_iter().for_each(drop);
            errors.try_iter().for_each(drop);
        }
    }
}
