# sub.py
import requests
import yaml
import socket
import concurrent.futures
import time
from urllib.parse import urlparse

DEBUG = True
TIMEOUT = 10
TEST_URL = "http://www.gstatic.com/generate_204"

def log(message):
    if DEBUG:
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

def test_proxy_connection(proxy_type, server, port):
    """通用代理连接测试"""
    proxies = {
        "http": f"{proxy_type}://{server}:{port}",
        "https": f"{proxy_type}://{server}:{port}"
    }
    
    try:
        start = time.time()
        response = requests.get(TEST_URL, 
                              proxies=proxies,
                              timeout=TIMEOUT)
        if response.status_code == 204:
            return (time.time() - start) * 1000  # 返回毫秒
        return None
    except Exception as e:
        log(f"连接测试失败 {server}:{port} ({proxy_type}) - {str(e)}")
        return None

def validate_node(node):
    """基础节点验证"""
    required_fields = ['name', 'server', 'port', 'type']
    if not all(field in node for field in required_fields):
        log(f"节点 {node.get('name')} 缺少必要字段")
        return False
    
    if node['type'] not in ['http', 'socks5', 'ss']:
        log(f"不支持的协议类型: {node['type']}")
        return False
    
    return True

def test_node(node):
    try:
        if not validate_node(node):
            return None
            
        latency = test_proxy_connection(node['type'], node['server'], node['port'])
        if not latency:
            return None
            
        return {
            'node': node,
            'latency': latency
        }
    except Exception as e:
        log(f"测试异常: {str(e)}")
        return None

def main():
    urls = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@refs/heads/main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@refs/heads/main/trial.yaml"
    ]

    all_nodes = []
    for url in urls:
        try:
            resp = requests.get(url, timeout=15)
            data = yaml.safe_load(resp.text)
            all_nodes.extend(data.get('proxies', []))
            log(f"从 {url} 加载 {len(data['proxies'])} 个节点")
        except Exception as e:
            log(f"加载失败: {str(e)}")

    # 去重
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node['type']}_{node['server']}_{node['port']}"
        if key not in seen:
            seen.add(key)
            unique_nodes.append(node)
    
    # 并发测试
    valid_nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_node, node): node for node in unique_nodes}
        
        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            result = future.result()
            if result:
                valid_nodes.append(result)
                log(f"有效节点: {result['node']['name']} - {result['latency']:.2f}ms")

    # 生成结果
    if valid_nodes:
        sorted_nodes = sorted(valid_nodes, key=lambda x: x['latency'])
        top_50 = sorted_nodes[:50]
        
        with open('nodes.yml', 'w') as f:
            yaml.safe_dump({'proxies': [n['node'] for n in top_50]}, f,
                          default_flow_style=False,
                          allow_unicode=True)
        
        with open('speed.txt', 'w') as f:
            f.write("Top 50 Nodes:\n")
            for idx, node in enumerate(top_50, 1):
                f.write(f"{idx:2d}. {node['node']['name']} - {node['latency']:.2f}ms\n")
        
        log(f"生成 {len(top_50)} 个有效节点")
    else:
        log("未找到有效节点")

if __name__ == '__main__':
    main()
