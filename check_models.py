from pathlib import Path

cache_dir = Path('C:/Users/Administrator/.cache/qmd/models')

print(f'Cache dir exists: {cache_dir.exists()}')

if cache_dir.exists():
    folders = list(cache_dir.iterdir())
    print(f'Model folders: {len(folders)}')
    for f in folders:
        print(f'  - {f.name}')
        # 检查大小
        if f.is_dir():
            size = sum(p.stat().st_size for p in f.rglob('*') if p.is_file())
            print(f'    Size: {size / 1024 / 1024:.1f} MB')
