import requests
import yaml
import base64
import subprocess
import os

# 订阅链接
SUB_URL = "https://raw.githubusercontent.com/mfbpn/tg_mfbpn_sub/refs/heads/main/trial.yaml"

# 输出文件名
OUTPUT_FILE = "sub-new.yaml"

# 测试网站列表
TEST_SITES = ["https://www.google.com", "https://www.youtube.com", "https://www.netflix.com"]

def fetch_subscription(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def parse_nodes(content):
    # 解析 YAML 内容，提取节点信息
    data = yaml.safe_load(content)
    nodes = data.get('proxies', [])
    return nodes

def test_node_connectivity(node):
    # 使用 Clash 或其他方式测试节点连通性
    # 这里只是示例，实际应根据您的测试方法实现
    for site in TEST_SITES:
        try:
            response = requests.get(site, timeout=5)
            if response.status_code != 200:
                return False
        except:
            return False
    return True

def filter_nodes(nodes):
    # 筛选可用节点
    available_nodes = []
    for node in nodes:
        if test_node_connectivity(node):
            available_nodes.append(node)
    return available_nodes

def generate_clash_yaml(nodes):
    # 生成 Clash YAML 配置
    config = {
        "proxies": nodes,
        "proxy-groups": [],
        "rules": []
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)

def main():
    content = fetch_subscription(SUB_URL)
    nodes = parse_nodes(content)
    available_nodes = filter_nodes(nodes)
    generate_clash_yaml(available_nodes)

if __name__ == "__main__":
    main()
