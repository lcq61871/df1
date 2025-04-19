# sub.py
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
            return (time.time() - start) * 1000
        return None
    except Exception as e:
        log(f"SS测试失败 {node.get('name')}: {str(e)}")
        return None

def test_vmess(node):
    """测试VMess协议"""
    try:
        start = time.time()
        cmd = ['nc', '-zvw5', node['server'], str(node['port'])]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            return (time.time() - start) * 1000
        return None
    except Exception as e:
        log(f"VMess测试失败 {node.get('name')}: {str(e)}")
        return None

def test_hysteria2(node):
    """测试Hysteria2协议"""
    try:
        config = {
            "server": f"{node['server']}:{node['port']}",
            "auth_str": node['auth_str'],
            "tls": {"insecure": node.get('insecure', False)}
        }
        
        with NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(config, f)
            config_file = f.name
            
        cmd = [
            'hysteria', 'client', '--config', config_file,
            'test', '--duration', '5', TEST_URL
        ]
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.unlink(config_file)
        
        if result.returncode != 0:
            return None
            
        for line in result.stdout.split('\n'):
            if 'avg_rtt' in line:
                return float(line.split('=')[1].replace('ms', '').strip())
        return None
    except Exception as e:
        log(f"Hysteria2测试失败 {node.get('name')}: {str(e)}")
        return None

def test_vless(node):
    """测试VLESS协议"""
    try:
        config = {
            "inbounds": [{
                "port": 1080,
                "protocol": "socks",
                "settings": {"auth": "noauth"}
            }],
            "outbounds": [{
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": node['server'],
                        "port": node['port'],
                        "users": [{"id": node['uuid']}]
                    }]
                },
                "streamSettings": node.get('streamSettings', {})
            }]
        }
        
        with NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(config, f)
            config_file = f.name
            
        xray_proc = subprocess.Popen(
            ['xray', 'run', '-c', config_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        time.sleep(2)
        
        cmd = [
            'curl', '-sS', '--socks5-hostname', '127.0.0.1:1080',
            '-o', '/dev/null', '-w', '%{time_total}', TEST_URL
        ]
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        xray_proc.terminate()
        os.unlink(config_file)
        
        if result.returncode == 0:
            return float(result.stdout) * 1000
        return None
    except Exception as e:
        log(f"VLESS测试失败 {node.get('name')}: {str(e)}")
        return None

def test_proxy(node):
    """协议测试分发器"""
    protocol_handlers = {
        'ss': test_ss,
        'vmess': test_vmess,
        'hysteria2': test_hysteria2,
        'vless': test_vless
    }
    
    proto = node.get('type', '').lower()
    if proto not in protocol_handlers:
        log(f"⚠️ 不支持的协议类型: {proto}")
        return None
        
    required_fields = {
        'ss': ['server', 'port', 'cipher', 'password'],
        'vmess': ['server', 'port', 'uuid'],
        'hysteria2': ['server', 'port', 'auth_str'],
        'vless': ['server', 'port', 'uuid']
    }.get(proto, [])
    
    if any(field not in node for field in required_fields):
        log(f"❌ 缺失必要字段: {node.get('name')}")
        return None
        
    return protocol_handlers[proto](node)

# ----------------- 主逻辑 -----------------
def main():
    sources = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@main/trial.yaml"
    ]
    
    all_nodes = []
    for url in sources:
        try:
            resp = requests.get(url, timeout=15)
            data = yaml.safe_load(resp.text)
            nodes = data.get('proxies', [])
            all_nodes.extend(nodes)
            log(f"✅ 成功加载 {len(nodes)} 节点 from {url}")
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
                latency = future.result()
                if latency:
                    valid_results.append({
                        'node': node,
                        'latency': latency
                    })
                    log(f"✅ 有效节点: {node['name']} ({latency:.2f}ms)")
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
            f.write("="*40 + "\n")
            for idx, item in enumerate(sorted_nodes, 1):
                f.write(f"{idx:2d}. {item['node']['name']:30} {item['latency']:.2f}ms\n")
        
        log(f"🎉 生成 {len(sorted_nodes)} 个有效节点")
    else:
        log("❌ 未找到有效节点")

if __name__ == '__main__':
    main()
