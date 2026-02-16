import json
from pathlib import Path

config_path = Path.home() / ".openclaw" / "config.json"
print(f"配置文件: {config_path}")
print(f"存在: {config_path.exists()}")

if config_path.exists():
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 查找qmd相关配置
    print("\nQMD相关配置:")
    if 'memory' in config:
        memory = config['memory']
        print(f"  backend: {memory.get('backend', 'N/A')}")
        if 'qmd' in memory:
            qmd_config = memory['qmd']
            print(f"  command: {qmd_config.get('command', 'N/A')}")
            print(f"  paths: {qmd_config.get('paths', 'N/A')}")
        else:
            print("  (没有qmd子配置)")
    else:
        print("  (没有memory配置)")

    # 打印完整配置（安全部分）
    print("\n配置结构:")
    for key in config.keys():
        if key not in ['apiKeys', 'credentials', 'tokens']:
            value = config[key]
            if isinstance(value, dict):
                print(f"  {key}: {{{len(value)} keys}}")
            elif isinstance(value, list):
                print(f"  {key}: [{len(value)} items]")
            else:
                print(f"  {key}: {value}")
else:
    print("配置文件不存在")
