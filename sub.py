# sub.py
import requests
import yaml
import socket
import concurrent.futures
import time

# 下载 YAML 节点列表
URLS = [
    "https://raw.githubusercontent.com/lcq61871/NoMoreWalls/refs/heads/master/snippets/nodes_IEPL.meta.yml",
    "https://raw.githubusercontent.com/lcq61871/NoMoreWalls/refs/heads/master/snippets/nodes_TW.meta.yml"
]

def download_yaml(url):
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return yaml.safe_load(res.text)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return {}

def test_node(node):
    name = node.get("name", "unknown")
    server = node.get("server")
    port = node.get("port", 443)
    if not server:
        return None

    start = time.time()
    try:
        with socket.create_connection((server, port), timeout=3) as s:
            latency = round((time.time() - start) * 1000, 2)
            return (node, latency)
    except:
        return None

def main():
    all_nodes = []
    for url in URLS:
        data = download_yaml(url)
        if data and 'proxies' in data:
            all_nodes.extend(data['proxies'])

    print(f"Total nodes fetched: {len(all_nodes)}")

    valid_nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(test_node, node) for node in all_nodes]
        for f in concurrent.futures.as_completed(futures):
            result = f.result()
            if result:
                valid_nodes.append(result)

    # 按延迟排序并选前 50 个
    valid_nodes.sort(key=lambda x: x[1])
    top_nodes = valid_nodes[:50]

    # 写入 nodes.yml
    nodes_yml = {
        "proxies": [node for node, _ in top_nodes]
    }
    with open("nodes.yml", "w", encoding='utf-8') as f:
        yaml.dump(nodes_yml, f, allow_unicode=True)

    # 写入 speed.txt
    with open("speed.txt", "w", encoding='utf-8') as f:
        for node, delay in top_nodes:
            f.write(f"{node['name']} - {node['server']}:{node['port']} - {delay}ms\n")

    print("nodes.yml and speed.txt generated.")

if __name__ == "__main__":
    main()
