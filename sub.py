import os
import yaml
import time
import json
import requests
import subprocess
import concurrent.futures
from datetime import datetime
from tempfile import NamedTemporaryFile

DEBUG = True
TIMEOUT = 20  # 总超时时间(秒)
TEST_URL = "https://www.gstatic.com/generate_204"

def log(message):
    if DEBUG:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

# ----------------- 节点加载函数 -----------------
def fetch_nodes(url):
    """从指定URL抓取节点数据"""
    try:
        log(f"⏳ 开始抓取节点源: {url}")
        
        # 通过CDN获取数据
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        
        # 解析YAML内容
        data = yaml.safe_load(resp.text)
        nodes = data.get('proxies', [])
        
        log(f"✅ 成功加载 {len(nodes)} 个节点 from {url}")
        return nodes
        
    except Exception as e:
        log(f"❌ 抓取失败 {url}: {str(e)}")
        return []

# ----------------- 主逻辑 -----------------
def main():
    # 配置节点源列表
    sources = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@refs/heads/main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@refs/heads/main/trial.yaml"
    ]
    
    # 抓取所有节点
    all_nodes = []
    for url in sources:
        nodes = fetch_nodes(url)
        all_nodes.extend(nodes)
    
    # 去重处理（服务器+端口+类型）
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node['type']}-{node['server']}:{node['port']}"
        if key not in seen:
            seen.add(key)
            unique_nodes.append(node)
    log(f"🔍 去重后节点数: {len(unique_nodes)}")

    # 协议测试函数（保持原有实现）
    # ... [test_ss, test_vmess, test_hysteria2, test_vless 等函数保持不变]

    # 并发测试
    valid_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_proxy, node): node for node in unique_nodes}
        
        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            try:
                result = future.result()
                if result:
                    valid_results.append(result)
                    log(f"✅ 有效节点: {node['name']} - {result['latency']:.2f}ms")
            except Exception as e:
                log(f"⚠️ 测试异常: {str(e)}")

    # 生成结果文件
    if valid_results:
        sorted_nodes = sorted(valid_results, key=lambda x: x['latency'])[:50]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 生成 nodes.yml
        with open('nodes.yml', 'w') as f:
            f.write(f"# 最后更新时间: {timestamp}\n")
            yaml.safe_dump(
                {'proxies': [n['node'] for n in sorted_nodes]},
                f,
                default_flow_style=False,
                allow_unicode=True
            )
        
        # 生成 speed.txt
        with open('speed.txt', 'w') as f:
            f.write(f"最后测试时间: {timestamp}\n")
            f.write("="*40 + "\n")
            for idx, item in enumerate(sorted_nodes, 1):
                f.write(f"{idx:2d}. {item['node']['name']:30} {item['latency']:.2f}ms\n")
        
        log(f"🎉 成功筛选 {len(sorted_nodes)} 个优质节点")
    else:
        log("⚠️ 未找到任何有效节点")

if __name__ == '__main__':
    main()
