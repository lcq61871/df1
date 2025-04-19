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
TIMEOUT = 20
TEST_URL = "https://www.gstatic.com/generate_204"

def log(message):
    if DEBUG:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

# ----------------- 协议测试函数 -----------------
def test_ss(node):
    """测试Shadowsocks协议"""
    try:
        start = time.time()
        cmd = [
            'curl', '-sS', '--connect-timeout', '10',
            '--socks5-hostname', f"{node['server']}:{node['port']}",
            '--proxy-user', f"{node['cipher']}:{node['password']}",
            '-o', '/dev/null', '-w', '%{http_code}', TEST_URL
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout.strip() == "204":
            return (time.time() - start) * 1000  # 返回毫秒
        return None
    except Exception as e:
        log(f"SS测试失败 {node.get('name')}: {str(e)}")
        return None

def test_vmess(node):
    """测试VMess协议"""
    try:
        # 基础TCP连通性测试
        start = time.time()
        cmd = ['nc', '-zvw5', node['server'], str(node['port'])]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            return (time.time() - start) * 1000
        return None
    except Exception as e:
        log(f"VMess测试失败 {node.get('name')}: {str(e)}")
        return None

def test_proxy(node):
    """协议测试分发器"""
    protocol_handlers = {
        'ss': test_ss,
        'vmess': test_vmess,
        # 在此添加其他协议处理函数
    }
    
    proto = node.get('type', '').lower()
    if proto not in protocol_handlers:
        log(f"⚠️ 不支持的协议类型: {proto}")
        return None
        
    # 必要字段验证
    required_fields = {
        'ss': ['server', 'port', 'cipher', 'password'],
        'vmess': ['server', 'port', 'uuid']
    }.get(proto, [])
    
    if any(field not in node for field in required_fields):
        log(f"❌ 缺失必要字段: {node.get('name')}")
        return None
        
    return protocol_handlers[proto](node)

# ----------------- 主逻辑 -----------------
def main():
    sources = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@refs/heads/main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@refs/heads/main/trial.yaml"
    ]
    
    all_nodes = []
    for url in sources:
        try:
            resp = requests.get(url, timeout=15)
            data = yaml.safe_load(resp.text)
            all_nodes.extend(data.get('proxies', []))
            log(f"✅ 成功加载 {len(data['proxies'])} 节点 from {url}")
        except Exception as e:
            log(f"❌ 加载失败 {url}: {str(e)}")

    # 去重处理
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
        futures = {executor.submit(test_proxy, node): node for node in unique_nodes}
        
        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            try:
                result = future.result()
                if result:
                    valid_results.append({
                        'node': node,
                        'latency': result
                    })
            except Exception as e:
                log(f"⚠️ 测试异常: {str(e)}")

    # 生成结果文件
    if valid_results:
        sorted_nodes = sorted(valid_results, key=lambda x: x['latency'])[:50]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open('nodes.yml', 'w') as f:
            yaml.safe_dump(
                {'proxies': [n['node'] for n in sorted_nodes]},
                f,
                default_flow_style=False,
                allow_unicode=True
            )
            
        with open('speed.txt', 'w') as f:
            f.write(f"最后更新: {timestamp}\n")
            for idx, item in enumerate(sorted_nodes, 1):
                f.write(f"{idx:2d}. {item['node']['name']}: {item['latency']:.2f}ms\n")
        
        log(f"🎉 生成 {len(sorted_nodes)} 个有效节点")
    else:
        log("❌ 未找到有效节点")

if __name__ == '__main__':
    main()
