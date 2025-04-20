#!/usr/bin/env python3
import os
import yaml
import time
import subprocess
import concurrent.futures
import random

DEBUG = True
TIMEOUT = 30
TEST_URLS = [
    "https://www.gstatic.com/generate_204",
    "http://cp.cloudflare.com/generate_204",
    "http://connectivitycheck.android.com/generate_204"
]
SPEED_TEST_URL = "https://speed.cloudflare.com/__down?bytes=1000000"
MAX_WORKERS = 6
TOP_NODES = 50
RETRY_COUNT = 2

def log(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open("sub.log", "a", encoding='utf-8') as f:
        f.write(log_msg + "\n")

def test_ss(node):
    """SS节点精准测试"""
    for attempt in range(RETRY_COUNT + 1):
        try:
            test_url = random.choice(TEST_URLS)
            proxy_url = f"socks5://{node['cipher']}:{node['password']}@{node['server']}:{node['port']}"
            
            # 基础连通测试
            base_cmd = [
                'curl', '-sS',
                '--connect-timeout', '15',
                '--max-time', '20',
                '--proxy', proxy_url,
                '-o', '/dev/null',
                '-w', '%{http_code} %{time_total}',
                test_url
            ]
            
            result = subprocess.run(
                base_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=25
            )
            
            if result.returncode == 0 and '204' in result.stdout:
                latency = float(result.stdout.split()[1]) * 1000
                
                # 速度测试
                speed_cmd = [
                    'curl', '-s',
                    '--connect-timeout', '15',
                    '--max-time', '30',
                    '--proxy', proxy_url,
                    '-o', '/dev/null',
                    '-w', '%{speed_download}',
                    SPEED_TEST_URL
                ]
                
                speed_result = subprocess.run(
                    speed_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30
                )
                
                if speed_result.returncode == 0:
                    speed = float(speed_result.stdout)
                    # 修正后的评分公式
                    score = (1000 / (latency + 1) * 0.4) + (speed / 1024 * 0.6)
                    log(f"✅ SS验证成功 {node['name']} | 延迟: {latency:.2f}ms | 速度: {speed/1024:.2f}KB/s")
                    return {'node': node, 'latency': latency, 'speed': speed, 'score': score}
            
            log(f"❌ SS测试失败({attempt+1}次) {node['name']} [错误: {result.stderr.strip()[:50]}]")
            time.sleep(2)
            
        except Exception as e:
            log(f"SS测试异常 {node['name']}: {str(e)}")
    
    return None

def load_nodes(sources):
    all_nodes = []
    for url in sources:
        try:
            result = subprocess.run(
                ['curl', '-sSL', '--retry', '3', url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            data = yaml.safe_load(result.stdout)
            valid_nodes = [n for n in data.get('proxies', []) if isinstance(n, dict)]
            all_nodes.extend(valid_nodes)
            log(f"📥 从 {url} 加载 {len(valid_nodes)} 节点")
        except Exception as e:
            log(f"❌ 加载失败 {url}: {str(e)}")
    return all_nodes

def main():
    log("=== 节点质量检测系统启动 ===")
    
    sources = [
        "https://your.subscription.link/nodes.yaml",
        "https://backup.subscription.link/nodes.yml"
    ]
    all_nodes = load_nodes(sources)
    
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node.get('type')}_{node.get('server')}_{node.get('port')}"
        if key not in seen and node.get('type') == 'ss':
            seen.add(key)
            unique_nodes.append(node)
    log(f"🔍 待测SS节点数: {len(unique_nodes)}")

    valid_nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_ss, n): n for n in unique_nodes}
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                valid_nodes.append(result)

    valid_nodes.sort(key=lambda x: -x['score'])
    best_nodes = valid_nodes[:TOP_NODES]
    
    os.makedirs("output", exist_ok=True)
    
    with open("output/nodes.yml", "w") as f:
        yaml.safe_dump(
            {"proxies": [n['node'] for n in best_nodes]},
            f,
            default_flow_style=False,
            allow_unicode=True
        )
    
    with open("output/speed.txt", "w") as f:
        f.write("排名 | 节点名称 | 延迟(ms) | 速度(KB/s) | 综合评分\n")
        f.write("-"*80 + "\n")
        for idx, node in enumerate(best_nodes, 1):
            f.write(f"{idx:2d}. {node['node']['name']} | {node['latency']:.2f} | {node['speed']/1024:.2f} | {node['score']:.2f}\n")
    
    log(f"🎉 测试完成！有效节点: {len(best_nodes)}/{len(unique_nodes)}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f"!!! 系统错误: {str(e)}")
