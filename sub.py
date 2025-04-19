import requests
import yaml
import socket
import concurrent.futures
import time
from collections import OrderedDict

def fetch_yaml(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = yaml.safe_load(resp.content)
        return data.get('proxies', [])
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return []

def tcp_ping(server, port, timeout=5):
    try:
        start = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((server, port))
            return (time.time() - start) * 1000  # 返回毫秒
    except Exception as e:
        return None

def test_node(node):
    try:
        if not all(key in node for key in ['server', 'port', 'name']):
            return None
            
        latency = tcp_ping(node['server'], node['port'])
        if latency is None:
            return None
            
        return {
            'node': node,
            'latency': latency
        }
    except Exception as e:
        return None

def main():
    urls = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@refs/heads/main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@refs/heads/main/trial.yaml"
    ]

    # 获取并合并节点
    all_nodes = []
    for url in urls:
        print(f"Processing {url}...")
        nodes = fetch_yaml(url)
        all_nodes.extend(nodes)
    
    # 去重（根据节点名称）
    unique_nodes = list(OrderedDict(((n['name'], n) for n in all_nodes)).values())
    print(f"Total {len(unique_nodes)} unique nodes found")

    # 并发测试节点
    valid_nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(test_node, node) for node in unique_nodes]
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                valid_nodes.append(result)
                print(f"Valid node: {result['node']['name']} ({result['latency']:.2f}ms)")

    # 按延迟排序
    sorted_nodes = sorted(valid_nodes, key=lambda x: x['latency'])
    top_50 = sorted_nodes[:50]

    # 生成nodes.yml
    output_proxies = [item['node'] for item in top_50]
    with open('nodes.yml', 'w', encoding='utf-8') as f:
        yaml.dump({'proxies': output_proxies}, f, allow_unicode=True, sort_keys=False)

    # 生成speed.txt
    with open('speed.txt', 'w', encoding='utf-8') as f:
        for item in top_50:
            f.write(f"{item['node']['name']}: {item['latency']:.2f}ms\n")

    print(f"Successfully generated nodes.yml with {len(top_50)} nodes")
    print(f"Speed results saved to speed.txt")

if __name__ == '__main__':
    main()
