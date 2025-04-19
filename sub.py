#!/usr/bin/env python3
import os
import yaml
import time
import subprocess
import concurrent.futures
from urllib.parse import urlparse

DEBUG = True
TIMEOUT = 25  # 总超时时间
TEST_URL = "https://www.gstatic.com/generate_204"
MAX_WORKERS = 15  # 降低并发避免误判
TOP_NODES = 50

def log(message):
    """增强型日志记录"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open("sub.log", "a", encoding='utf-8') as f:
        f.write(log_msg + "\n")

def test_ss(node):
    """精准测试SS节点"""
    try:
        # 直接测试代理可用性（跳过端口检查）
        cmd = [
            'curl', '-sS',
            '--connect-timeout', '15',
            '--max-time', '20',
            '--retry', '2',  # 增加重试
            '--socks5-hostname', f"{node['server']}:{node['port']}",
            '--proxy-user', f"{node['cipher']}:{node['password']}",
            '-o', '/dev/null',
            '-w', '%{http_code} %{time_total}',
            TEST_URL
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT
        )
        
        if result.returncode == 0 and '204' in result.stdout:
            latency = float(result.stdout.split()[1]) * 1000
            log(f"✅ SS验证成功 {node['name']} | 延迟: {latency:.2f}ms")
            return latency
        log(f"❌ SS测试失败 {node['name']}: {result.stderr[:200]}")
        return None
        
    except Exception as e:
        log(f"SS异常 {node['name']}: {str(e)}")
        return None

def test_vmess(node):
    """VMess节点测试（无需Xray-core）"""
    try:
        # 使用v2fly官方测试工具
        test_cmd = [
            'v2ray', 'test',
            '--server', f"{node['server']}:{node['port']}",
            '--uuid', node['uuid'],
            '--alterId', str(node.get('alterId', 0)),
            '--security', node.get('security', 'auto')
        ]
        
        start_time = time.time()
        result = subprocess.run(
            test_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT
        )
        
        if result.returncode == 0:
            latency = (time.time() - start_time) * 1000
            log(f"✅ VMess验证成功 {node['name']} | 延迟: {latency:.2f}ms")
            return latency
        log(f"❌ VMess测试失败 {node['name']}: {result.stderr[:200]}")
        return None
        
    except Exception as e:
        log(f"VMess异常 {node['name']}: {str(e)}")
        return None

def test_node(node):
    """智能节点测试分发"""
    protocol_map = {
        'ss': test_ss,
        'vmess': test_vmess,
        'trojan': lambda n: test_ss(n)  # Trojan复用SS测试逻辑
    }
    
    if node.get('type') not in protocol_map:
        log(f"⚠️ 跳过不支持协议: {node.get('type')}")
        return None
        
    required_fields = {
        'ss': ['server', 'port', 'cipher', 'password'],
        'vmess': ['server', 'port', 'uuid'],
        'trojan': ['server', 'port', 'password']
    }
    
    missing = [f for f in required_fields.get(node['type'], []) if f not in node]
    if missing:
        log(f"⚠️ 节点字段缺失 {node.get('name')}: {missing}")
        return None
        
    try:
        latency = protocol_map[node['type']](node)
        return {'node': node, 'latency': latency} if latency else None
    except Exception as e:
        log(f"全局异常 {node.get('name')}: {str(e)}")
        return None

def main():
    log("=== 节点测试开始 ===")
    
    # 加载节点源（已验证可用源）
    sources = [
        "https://raw.githubusercontent.com/lcq61871/NoMoreWalls/refs/heads/master/snippets/nodes_TW.meta.yml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@main/trial.yaml"
    ]
    
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
            all_nodes.extend([n for n in data.get('proxies', []) if isinstance(n, dict)])
            log(f"📥 从 {url} 加载 {len(data.get('proxies', []))} 节点")
        except Exception as e:
            log(f"❌ 加载失败 {url}: {str(e)}")

    # 智能去重
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node.get('type')}_{node.get('server')}_{node.get('port')}"
        if key not in seen:
            seen.add(key)
            unique_nodes.append(node)
    log(f"🔍 去重后节点数: {len(unique_nodes)}")

    # 稳定测试模式
    valid_nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_node, n): n for n in unique_nodes}
        
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result:
                    valid_nodes.append(result)
            except Exception as e:
                log(f"并发异常: {str(e)}")

    # 结果处理
    valid_nodes.sort(key=lambda x: x['latency'])
    best_nodes = valid_nodes[:TOP_NODES]
    
    # 生成文件
    os.makedirs("output", exist_ok=True)
    
    with open("output/nodes.yml", "w", encoding='utf-8') as f:
        yaml.safe_dump(
            {"proxies": [n['node'] for n in best_nodes]},
            f,
            default_flow_style=False,
            allow_unicode=True
        )
    
    with open("output/speed.txt", "w", encoding='utf-8') as f:
        f.write("排名 | 节点名称 | 延迟(ms)\n")
        f.write("-"*50 + "\n")
        for idx, node in enumerate(best_nodes, 1):
            f.write(f"{idx:2d}. {node['node']['name']} | {node['latency']:.2f}\n")
    
    log(f"🎉 有效节点: {len(best_nodes)}/{len(unique_nodes)}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f"!!! 致命错误: {str(e)}")
