import os
import yaml
import time
import subprocess
import concurrent.futures
from datetime import datetime

DEBUG = True
TIMEOUT = 15
TEST_URL = "https://www.gstatic.com/generate_204"

def log(message):
    if DEBUG:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def test_proxy(node):
    # 协议测试逻辑（保持原有实现）
    # ...
    # 返回延迟或None

def main():
    # 加载节点源
    sources = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@main/trial.yaml"
    ]
    
    # 节点处理逻辑
    # ...
    
    # 生成带时间戳的结果
    timestamp = datetime.now().isoformat()
    with open('nodes.yml', 'w') as f:
        f.write(f"# Auto generated at {timestamp}\n")
        yaml.safe_dump({'proxies': valid_nodes}, f)
    
    with open('speed.txt', 'w') as f:
        f.write(f"Last update: {timestamp}\n")
        # 写入测速结果

if __name__ == '__main__':
    main()
