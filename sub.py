import socket
import time
import yaml
import requests

def get_subscription_nodes(sub_url):
    try:
        response = requests.get(sub_url, timeout=10)
        response.raise_for_status()
        data = yaml.safe_load(response.text)
        print(f"Raw subscription data from {sub_url}: {data}")
        return data
    except Exception as e:
        print(f"Error fetching subscription from {sub_url}: {e}")
        return None

def test_node_connectivity(node):
    try:
        server = node["server"]
        port = node["port"]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        start_time = time.time()
        sock.connect((server, port))
        latency = (time.time() - start_time) * 1000
        sock.close()
        return latency
    except Exception as e:
        print(f"Error testing node {node['name']}: {e}")
        return float('inf')

def main():
    sources = [
        "https://cdn.jsdelivr.net/gh/lcq61871/NoMoreWalls@refs/heads/master/snippets/nodes_TW.meta.yml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@refs/heads/main/trial.yaml"
    ]
    
    all_nodes = []
    for sub_url in sources:
        nodes = get_subscription_nodes(sub_url)
        if nodes and 'proxies' in nodes:
            all_nodes.extend(nodes['proxies'])
        else:
            print(f"No nodes found in {sub_url}")

    if not all_nodes:
        print("No nodes found from any source.")
        return

    print(f"Found {len(all_nodes)} nodes to test.")
    results = []
    for node in all_nodes:
        latency = test_node_connectivity(node)
        if latency != float('inf'):
            results.append({'node': node, 'latency': latency})
        print(f"Node {node['name']} - Latency: {latency}ms")

    sorted_results = sorted(results, key=lambda x: x['latency'])
    
    with open('sorted_nodes.yml', 'w') as f:
        yaml.dump({'proxies': [result['node'] for result in sorted_results] or []}, f)
    print(f"Saved {len(sorted_results)} nodes to sorted_nodes.yml")

if __name__ == "__main__":
    main()