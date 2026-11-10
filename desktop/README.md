# Build LocalLens for Windows with Tauri 2

The desktop shell opens the existing React/Vite UI in a WebView2 window. It
starts the bundled Python backend, reads its readiness message over a private
pipe, and loads its loopback URL. This keeps the same frontend, onboarding,
benchmark engine, API authentication, and result formats as the browser
launcher. The browser launcher and source build remain available from the
repository root.

## Build and verify

Use Windows x64 with current Python 3.13 x64, Node.js 22.12+ or 24, Rust with
the x86-64 MSVC target, and Visual Studio C++ Build Tools with a Windows SDK.
See the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

From the repository root:

```powershell
python -m venv .desktop-python
.\.desktop-python\Scripts\python.exe -m pip install -r desktop/requirements-build.txt -r requirements-devices.txt
npm --prefix frontend ci
.\desktop\build.ps1 -Mode Build -Python .\.desktop-python\Scripts\python.exe
.\desktop\build.ps1 -Mode Run
```

Check that the native window opens at the onboarding screen. Run **Scan &
Predict** and confirm hardware and model-fit estimates appear. Run a benchmark
when ready to download or reuse a model. Close the native window and verify
the backend exits before packaging.

```powershell
.\desktop\build.ps1 -Mode Installer
```

The NSIS setup executable is written to
`desktop/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/`. It
installs per user and uses the Microsoft WebView2 bootstrapper if needed.
The app carries its own Python runtime. The build tools are only needed on
the build machine. This preview targets Windows 10/11 x64. Setup is unsigned.

## Local data and security

- Desktop results and temporary benchmark files live in
  `%LOCALAPPDATA%\app.locallens.desktop`. Existing browser journals use their
  original directory and can be exported independently.
- The backend listens on an ephemeral IPv4 loopback port, validates the Host
  header, and requires a random per-launch token for API calls. The WebView is
  restricted to its startup page and the selected loopback origin. No native
  Tauri commands are granted to web content.
- Closing the app signals the sidecar through its private pipe. A Windows job
  object also terminates any remaining child processes if the app exits.
- The automatic test keeps the existing pinned engine and model downloads.
  Optional Intel OpenVINO reports its status in the bundled runtime. The
  default bundle does not include the optional OpenVINO packages.
- Native Android pairing remains optional. Opening Devices starts LAN discovery. To include an APK in the desktop
  download action, pass `-AndroidApk` with a built
  `LocalLens-Companion-debug.apk`. Phone compute remains disabled.


The backend resource folder contains Python, frontend and Rust dependency
notices. The bundled mDNS package is
[python-zeroconf 0.151.0](https://github.com/python-zeroconf/python-zeroconf/tree/0.151.0)
under LGPL-2.1-or-later. Its modules and native libraries are installed as
separate files in the backend resource folder.

## Optional Intel NPU build

Install `desktop/requirements-npu.txt` in the build Python environment, then
pass `-WithNpu` to `desktop/build.ps1 -Mode Build`. This includes OpenVINO
GenAI in the frozen backend. The default smaller build reports the runtime as
unavailable. Under **Manual benchmark**, check the runtime and choose a trusted
local OpenVINO model folder. An Intel NPU driver and compatible exported model
are required.
