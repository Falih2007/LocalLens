[CmdletBinding()]
param(
    [ValidateSet('Build', 'Run', 'Installer')]
    [string]$Mode = 'Build',
    [string]$Python = 'python',
    [string]$AndroidApk,
    [switch]$WithNpu
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$tauri = Join-Path $PSScriptRoot 'src-tauri'
$scratch = Join-Path $PSScriptRoot '.build'
$target = 'x86_64-pc-windows-msvc'
$cli = '@tauri-apps/cli@2.12.4'
$previousRustFlags = $env:CARGO_ENCODED_RUSTFLAGS

function Assert-Exit([string]$Task) {
    if ($LASTEXITCODE -ne 0) { throw "$Task failed (exit $LASTEXITCODE)." }
}

Push-Location $root
try {
    if ($Mode -eq 'Build') {
        if (Test-Path -LiteralPath $Python -PathType Leaf) {
            $Python = (Resolve-Path -LiteralPath $Python).Path
        }
        & $Python -m PyInstaller --version
        Assert-Exit 'Python bundler check'
        & npm.cmd --prefix frontend run build
        Assert-Exit 'Frontend build'
        New-Item -ItemType Directory -Path $scratch -Force | Out-Null
        $env:PYINSTALLER_CONFIG_DIR = Join-Path $scratch 'pyinstaller-cache'
        $buildArgs = @(
            '--noconfirm', '--onedir', '--console', '--noupx', '--debug', 'noarchive',
            '--name', 'locallens-backend',
            '--distpath', (Join-Path $tauri 'sidecar'),
            '--workpath', (Join-Path $scratch 'pyinstaller-work'),
            '--specpath', $scratch,
            '--collect-submodules', 'zeroconf',
            '--copy-metadata', 'zeroconf',
            '--copy-metadata', 'ifaddr',
            '--copy-metadata', 'pyinstaller'
        )
        if ($WithNpu) {
            & $Python -c 'import openvino, openvino_genai, openvino_tokenizers'
            Assert-Exit 'OpenVINO dependencies. Install desktop/requirements-npu.txt in the build environment'
            foreach ($module in @('openvino', 'openvino_genai', 'openvino_tokenizers')) {
                $buildArgs += @('--collect-all', $module, '--copy-metadata', $module)
            }
            $buildArgs += @('--copy-metadata', 'numpy', '--copy-metadata', 'openvino-telemetry')
        } else {
            foreach ($module in @('openvino', 'openvino_genai', 'openvino_tokenizers')) {
                $buildArgs += @('--exclude-module', $module)
            }
        }
        $data = [ordered]@{
            'models.json' = '.'
            'frontend/dist' = 'frontend/dist'
            'ui' = 'ui'
            'CONNECT-DEVICES.md' = '.'
            'companion.py' = '.'
            'connectnet.py' = '.'
            'licenses' = 'licenses'
            'docs/DEVICES-ARCHITECTURE.md' = 'docs'
        }
        foreach ($source in $data.Keys) {
            $path = (Resolve-Path -LiteralPath $source).Path
            $buildArgs += @('--add-data', ($path + ':' + $data[$source]))
        }
        $pythonRoot = & $Python -c 'import sys; print(sys.base_prefix)'
        Assert-Exit 'Python license location'
        $buildArgs += @('--add-data', ((Join-Path $pythonRoot 'LICENSE.txt') + ':licenses/python'))
        if ($AndroidApk) {
            $apk = Get-Item -LiteralPath $AndroidApk
            if ($apk.Name -ne 'LocalLens-Companion-debug.apk') {
                throw 'The optional APK must be named LocalLens-Companion-debug.apk.'
            }
            $buildArgs += @('--add-data', ($apk.FullName + ':android'))
        }
        & $Python -m PyInstaller @buildArgs app.py
        Assert-Exit 'Backend bundle'
        $metadata = & cargo metadata --format-version 1 --locked --filter-platform $target --manifest-path (Join-Path $tauri 'Cargo.toml')
        Assert-Exit 'Resolve Rust notices'
        $notices = Join-Path $tauri 'sidecar/locallens-backend/_internal/licenses/rust'
        New-Item -ItemType Directory -Path $notices -Force | Out-Null
        $inventory = foreach ($package in ($metadata | ConvertFrom-Json).packages) {
            if (!$package.source) { continue }
            $crate = Split-Path $package.manifest_path -Parent
            $folder = Join-Path $notices "$($package.name)-$($package.version)"
            $files = @(Get-ChildItem -LiteralPath $crate -File |
                Where-Object Name -Match '^(LICENSE|COPYING|NOTICE)([._-]|$)')
            if ($package.license_file) {
                $files += Get-Item -LiteralPath (Join-Path $crate $package.license_file)
            }
            if ($files) {
                New-Item -ItemType Directory -Path $folder -Force | Out-Null
                $files | Sort-Object FullName -Unique | ForEach-Object {
                    Copy-Item -LiteralPath $_.FullName -Destination $folder
                }
            }
            "$($package.name) $($package.version) | $($package.license) | https://crates.io/crates/$($package.name)/$($package.version)"
        }
        $inventory | Set-Content -LiteralPath (Join-Path $notices 'INDEX.txt') -Encoding utf8
    }

    $exe = Join-Path $tauri "target/$target/release/locallens.exe"
    if ($Mode -eq 'Run') {
        if (!(Test-Path -LiteralPath $exe)) { throw 'Build LocalLens first.' }
        Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe -Parent)
    } else {
        Set-Location $PSScriptRoot
        if ($Mode -eq 'Installer') {
            if (!(Test-Path -LiteralPath $exe)) { throw 'Build and test LocalLens first.' }
            & npx.cmd --yes $cli bundle --bundles nsis --target $target
            Assert-Exit 'Windows installer'
        } else {
            # Keep source and toolchain paths out of panic metadata in distributed builds.
            $cargoHome = if ($env:CARGO_HOME) { $env:CARGO_HOME } else { Join-Path $env:USERPROFILE '.cargo' }
            $remaps = @(
                "--remap-path-prefix=$($env:USERPROFILE)=/build-user",
                "--remap-path-prefix=$root=/locallens",
                "--remap-path-prefix=$cargoHome=/cargo"
            )
            $env:CARGO_ENCODED_RUSTFLAGS = (@($previousRustFlags) + $remaps | Where-Object { $_ }) -join [char]31
            & npx.cmd --yes $cli build --no-bundle --target $target
            Assert-Exit 'Native desktop build'
            # Cargo copies resources incrementally and can leave files from an older Python bundle.
            $release = (Resolve-Path -LiteralPath (Split-Path $exe -Parent)).Path
            $expected = Join-Path $tauri "target/$target/release"
            if ([IO.Path]::GetFullPath($release) -ine [IO.Path]::GetFullPath($expected)) {
                throw 'Unexpected native build output path.'
            }
            $staged = Join-Path $release 'backend'
            if (Test-Path -LiteralPath $staged) {
                $item = Get-Item -LiteralPath $staged -Force
                if (!$item.PSIsContainer -or $item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                    throw 'Unexpected staged backend path.'
                }
                Remove-Item -LiteralPath $item.FullName -Recurse -Force
            }
            Copy-Item -LiteralPath (Join-Path $tauri 'sidecar/locallens-backend') -Destination $staged -Recurse
        }
    }
} finally {
    $env:CARGO_ENCODED_RUSTFLAGS = $previousRustFlags
    Pop-Location
}
