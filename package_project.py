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
if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Create a clean portable LocalLens source/build archive.')
    parser.add_argument('--output',type=Path,default=ROOT.parent/'LocalLens-Windows-Prototype.zip')
    parser.add_argument('--include-results',action='store_true',help='Explicitly include local runtime reports; normally leave this off.')
    args=parser.parse_args();print(package(args.output,args.include_results))
