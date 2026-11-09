from pathlib import Path
import argparse,os,zipfile
ROOT=Path(__file__).resolve().parent
EXCLUDED={'node_modules','__pycache__','.vite','.git','.codex','.gradle','build'}
def package(destination,include_results=False):
    destination=Path(destination).resolve()
    if destination.is_relative_to(ROOT):raise ValueError('Write the archive outside the source project.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for base,dirs,files in os.walk(ROOT):
            dirs[:]=[d for d in dirs if d not in EXCLUDED and not (Path(base)==ROOT and d=='data' and not include_results)]
            for name in files:
                f=Path(base)/name
                if f.suffix in {'.pyc','.tsbuildinfo','.jks','.keystore'} or name.startswith('.env') or name=='local.properties':continue
                z.write(f,Path('LocalLens')/f.relative_to(ROOT))
    return destination
def package_runtime(destination):
    """Create the Windows preview from a fixed list and the production frontend."""
    destination = Path(destination).resolve()
    if destination.is_relative_to(ROOT):
        raise ValueError('Write the archive outside the source project.')

    files = [
        'Start-LocalLens.cmd', 'README.md', 'CONNECT-DEVICES.md',
        'app.py', 'autotest.py', 'cluster.py', 'companion.py', 'connectnet.py',
        'device.py', 'devices_manager.py', 'mdns_discovery.py', 'truststore.py',
        'openvino_adapter.py', 'models.json', 'requirements-devices.txt',
        'result.schema.json', 'scan.schema.json', 'connection.schema.json',
        'ui/index.html', 'ui/app.js', 'ui/style.css',
        'licenses/shadcn-ui-MIT.md', 'licenses/geist-OFL.txt',
        'licenses/tailwindcss-MIT.txt', 'licenses/tw-animate-css-MIT.txt',
        'android/companion/README.md', 'docs/locallens-preview.png',
        'docs/benchmark-methodology.md', 'docs/benchmark-results.md',
        'docs/DESIGN.md', 'docs/DEVICES-ARCHITECTURE.md', 'docs/DEVICES-TESTING.md',
        'docs/DISTRIBUTED-RESEARCH.md', 'docs/FRONTEND.md', 'docs/TESTING.md',
        'docs/release-notes.md',
        'frontend/dist/index.html', 'frontend/dist/THIRD-PARTY-LICENSES.md',
        'frontend/dist/assets/favicon.svg',
    ]
    assets = ROOT / 'frontend/dist/assets'
    files.extend(path.relative_to(ROOT) for path in sorted(assets.iterdir())
                 if path.is_file() and path.suffix in {'.js', '.css', '.woff2'})
    for name in files:
        path = ROOT / name
        if not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f'Missing or unsafe release input: {name}')

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(ROOT / name, Path('LocalLens') / name)
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Create a clean portable LocalLens source/build archive.')
    parser.add_argument('--output',type=Path,default=ROOT.parent/'LocalLens-Windows-Prototype.zip')
    parser.add_argument('--include-results',action='store_true',help='Explicitly include local runtime reports; normally leave this off.')
    parser.add_argument('--runtime-only', action='store_true', help='Include only the Windows runtime and built frontend.')
    args = parser.parse_args()
    if args.runtime_only and args.include_results:
        parser.error('The Windows preview never includes local results.')
    print(package_runtime(args.output) if args.runtime_only else package(args.output, args.include_results))
