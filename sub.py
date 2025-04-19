import requests
import yaml
import socket
import concurrent.futures
import time
from collections import OrderedDict

DEBUG = True  # 开启调试模式

def log(message):
    if DEBUG:
        print(message)

def fetch_yaml(url):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return yaml.safe_load(resp.text)
    except Exception as e:
        log(f"🚨 Error fetching {url}: {str(e)}")
        return None

def tcp_ping(server, port, timeout=5):
    try:
        start = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((server, port))
            latency = (time.time() - start) * 1000
            log(f"✅ TCP connection to {server}:{port} succeeded ({latency:.2f}ms)")
            return latency
    except Exception as e:
        log(f"❌ TCP connection to {server}:{port} failed: {str(e)}")
        return None

def validate_proxy(node):
    """ 执行协议级验证 """
    try:
        if node.get('type') == 'ss':
            # 简单的Shadowsocks协议验证
            if not all(key in node for key in ['cipher', 'password']):
                log(f"⚠️ Shadowsocks node {node['name']} missing required fields")
                return False
        elif node.get('type') == 'vmess':
            # VMess基础验证
            if not all(key in node for key in ['uuid', 'alterId', 'cipher']):
                log(f"⚠️ VMess node {node['name']} missing required fields")
                return False
        return True
    except Exception as e:
        log(f"Validation error: {str(e)}")
        return False

def test_node(node):
    try:
        # 基础字段检查
        required_fields = ['server', 'port', 'name', 'type']
        if not all(field in node for field in required_fields):
            log(f"⚠️ Node {node.get('name')} missing required fields")
            return None
            
        # TCP连接测试
        latency = tcp_ping(node['server'], node['port'])
        if latency is None:
            return None
            
        # 协议验证
        if not validate_proxy(node):
            return None
            
        return {
            'node': node,
            'latency': latency
        }
    except Exception as e:
        log(f"Test error: {str(e)}")
        return None

def main():
    urls = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@refs/heads/main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@refs/heads/main/trial.yaml"
    ]

    # 获取并合并节点
    all_nodes = []
    for url in urls:
        log(f"\n🔗 Processing {url}...")
        data = fetch_yaml(url)
        if data and 'proxies' in data:
            all_nodes.extend(data['proxies'])
            log(f"Found {len(data['proxies'])} nodes")
        else:
            log("No valid nodes found in this source")
    
    # 去重（根据服务器+端口）
    unique_nodes = []
    seen = set()
    for node in all_nodes:
        key = f"{node['server']}:{node['port']}"
        if key not in seen:
            seen.add(key)
            unique_nodes.append(node)
    log(f"\n🎯 Total {len(unique_nodes)} unique nodes after deduplication")

    # 并发测试节点
    valid_nodes = []
    log("\n🚦 Starting node testing...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(test_node, node): node for node in unique_nodes}
        
        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            try:
                result = future.result()
                if result:
                    valid_nodes.append(result)
                    log(f"🏁 Valid node: {result['node']['name']} ({result['latency']:.2f}ms)")
                else:
                    log(f"💀 Invalid node: {node.get('name')}")
            except Exception as e:
                log(f"⚠️ Error testing node: {str(e)}")

    # 按延迟排序
    sorted_nodes = sorted(valid_nodes, key=lambda x: x['latency'])
    top_50 = sorted_nodes[:50]

    # 生成nodes.yml
    output_proxies = [item['node'] for item in top_50]
    with open('nodes.yml', 'w', encoding='utf-8') as f:
        yaml.dump({'proxies': output_proxies}, f, 
                 allow_unicode=True, 
                 sort_keys=False,
                 default_flow_style=False,
                 indent=2)

    # 生成speed.txt
    with open('speed.txt', 'w', encoding='utf-8') as f:
        f.write("Top 50 Nodes Speed Test Results:\n")
        f.write("="*50 + "\n")
        for idx, item in enumerate(top_50, 1):
            f.write(f"{idx:2d}. {item['node']['name']:40} {item['latency']:.2f}ms\n")

    log(f"\n✅ Successfully generated:")
    log(f"   - nodes.yml with {len(top_50)} valid nodes")
    log(f"   - speed.txt with latency records")

if __name__ == '__main__':
    main()
