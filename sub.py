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

def main():  # <- 函数定义开始
    # 加载节点源 (此处开始缩进)
    sources = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@main/trial.yaml"
    ]
    
    all_nodes = []
    for url in sources:
        try:
            result = subprocess.run(
                ['curl', '-sSL', url],
                stdout=subprocess.PIPE,
                check=True
            )
            data = yaml.safe_load(result.stdout)
            valid_nodes = [n for n in data.get('proxies', []) if 'type' in n]
            all_nodes.extend(valid_nodes)
            log(f"📥 加载 {len(valid_nodes)} 节点 from {url}")
        except Exception as e:
            log(f"❌ 加载失败 {url}: {str(e)}")

    # 节点去重
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node['type']}-{node['server']}:{node['port']}"
        if key not in seen:
            seen.add(key)
            unique_nodes.append(node)
    log(f"🔍 去重后节点数: {len(unique_nodes)}")

    # 并发测试
    valid_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_proxy, n): n for n in unique_nodes}
        
        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            try:
                result = future.result()
                if result:
                    valid_results.append(result)
            except Exception as e:
                log(f"⚠️ 并发错误: {str(e)}")

    # 生成结果文件
    if valid_results:
        sorted_nodes = sorted(valid_results, key=lambda x: x['latency'])[:50]
        timestamp = datetime.now().isoformat()
        
        with open('nodes.yml', 'w') as f:
            f.write(f"# Auto generated at {timestamp}\n")
            yaml.safe_dump(
                {'proxies': [n['node'] for n in sorted_nodes]},
                f,
                default_flow_style=False,
                allow_unicode=True
            )
            
        with open('speed.txt', 'w') as f:
            f.write(f"Last update: {timestamp}\n")
            f.write("排名 | 节点名称 | 延迟(ms)\n")
            f.write("-"*40 + "\n")
            for idx, item in enumerate(sorted_nodes, 1):
                f.write(f"{idx:2d}. {item['node']['name']} | {item['latency']:.2f}\n")
        
        log(f"🎉 生成 {len(sorted_nodes)} 个有效节点")
    else:
        log("❌ 未找到有效节点")

if __name__ == '__main__':
    main()
