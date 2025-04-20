#!/usr/bin/env python3
import os
import yaml
import time
import subprocess
import concurrent.futures
import json
import base64
from urllib.parse import urlparse

DEBUG = True
TIMEOUT = 30  # 总超时时间
TEST_URL = "https://www.gstatic.com/generate_204"  # 基础连通性测试
SPEED_TEST_URL = "https://speed.cloudflare.com/__down?bytes=5000000"  # 5MB测试文件
MAX_WORKERS = 8  # 保守并发数避免带宽争抢
TOP_NODES = 50

def log(message):
    """增强型日志记录"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open("sub.log", "a", encoding='utf-8') as f:
        f.write(log_msg + "\n")

def measure_speed(cmd, node_name):
    """精确测量下载速度"""
    try:
        start_time = time.time()
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TIMEOUT
        )
        if result.returncode == 0:
            elapsed = time.time() - start_time
            speed = len(result.stdout) / elapsed  # bytes/sec
            return speed
        return 0
    except Exception as e:
        log(f"速度测试失败 {node_name}: {str(e)}")
        return 0

def test_ss(node):
    """SS节点真实速度测试"""
    try:
        # 基础连通性测试
        base_cmd = [
            'curl', '-sS',
            '--connect-timeout', '10',
            '--max-time', '15',
            '--socks5-hostname', f"{node['server']}:{node['port']}",
            '--proxy-user', f"{node['cipher']}:{node['password']}",
            '-o', '/dev/null',
            '-w', '%{http_code} %{time_total}',
            TEST_URL
        ]
        
        # 执行基础测试
        base_result = subprocess.run(
            base_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if base_result.returncode != 0 or '204' not in base_result.stdout:
            log(f"❌ SS基础测试失败 {node['name']}")
            return None, None
        
        latency = float(base_result.stdout.split()[1]) * 1000
        
        # 真实速度测试
        speed_cmd = [
            'curl', '-s',
            '--connect-timeout', '10',
            '--max-time', '25',
            '--socks5-hostname', f"{node['server']}:{node['port']}",
            '--proxy-user', f"{node['cipher']}:{node['password']}",
            SPEED_TEST_URL
        ]
        
        speed = measure_speed(speed_cmd, node['name'])
        if speed == 0:
            return None, None
            
        log(f"✅ SS验证成功 {node['name']} | 延迟: {latency:.2f}ms | 速度: {speed/1024:.2f} KB/s")
        return latency, speed
        
    except Exception as e:
        log(f"SS测试异常 {node['name']}: {str(e)}")
        return None, None

def test_vmess(node):
    """VMess真实速度测试"""
    try:
        # 生成VMess代理链接
        vmess_config = {
            "v": "2", "ps": node['name'],
            "add": node['server'], "port": node['port'],
            "id": node['uuid'], "aid": node.get('alterId', 0),
            "scy": node.get('security', 'auto'),
            "net": node.get('network', 'tcp')
        }
        vmess_url = "vmess://" + base64.b64encode(json.dumps(vmess_config).encode()).decode()
        
        # 基础连通性测试
        base_cmd = [
            'curl', '-sS',
            '--connect-timeout', '10',
            '--max-time', '15',
            '--proxy', vmess_url,
            '-o', '/dev/null',
            TEST_URL
        ]
        
        base_result = subprocess.run(
            base_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if base_result.returncode != 0:
            log(f"❌ VMess基础测试失败 {node['name']}")
            return None, None
        
        latency = float(base_result.stdout.split()[1]) * 1000
        
        # 真实速度测试
        speed_cmd = [
            'curl', '-s',
            '--connect-timeout', '10',
            '--max-time', '25',
            '--proxy', vmess_url,
            SPEED_TEST_URL
        ]
        
        speed = measure_speed(speed_cmd, node['name'])
        if speed == 0:
            return None, None
            
        log(f"✅ VMess验证成功 {node['name']} | 延迟: {latency:.2f}ms | 速度: {speed/1024:.2f} KB/s")
        return latency, speed
        
    except Exception as e:
        log(f"VMess测试异常 {node['name']}: {str(e)}")
        return None, None

def test_node(node):
    """综合性能评估"""
    protocol_testers = {
        'ss': test_ss,
        'vmess': test_vmess,
        'trojan': lambda n: test_ss(n)  # Trojan复用SS测试
    }
    
    if node.get('type') not in protocol_testers:
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
        latency, speed = protocol_testers[node['type']](node)
        if latency and speed:
            # 综合评分算法（延迟占40%，速度占60%）
            score = ( (1000/(latency+1)) * 0.4 + (speed/1024) * 0.6 )
            return {'node': node, 'latency': latency, 'speed': speed, 'score': score}
        return None
    except Exception as e:
        log(f"全局异常 {node.get('name')}: {str(e)}")
        return None

def main():
    log("=== 真实速度测试开始 ===")
    
    # 加载节点源（需替换为实际订阅链接）
    sources = [
        "https://your.actual.subscription/link1.yaml",
        "https://your.actual.subscription/link2.yaml"
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

    # 去重处理
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node.get('type')}_{node.get('server')}_{node.get('port')}"
        if key not in seen:
            seen.add(key)
            unique_nodes.append(node)
    log(f"🔍 去重后节点数: {len(unique_nodes)}")

    # 并发测试
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

    # 按综合评分排序
    valid_nodes.sort(key=lambda x: -x['score'])
    best_nodes = valid_nodes[:TOP_NODES]
    
    # 生成结果文件
    os.makedirs("output", exist_ok=True)
    
    with open("output/nodes.yml", "w", encoding='utf-8') as f:
        yaml.safe_dump(
            {"proxies": [n['node'] for n in best_nodes]},
            f,
            default_flow_style=False,
            allow_unicode=True
        )
    
    with open("output/speed.txt", "w", encoding='utf-8') as f:
        f.write("排名 | 节点名称 | 延迟(ms) | 速度(KB/s) | 综合评分\n")
        f.write("-"*80 + "\n")
        for idx, node in enumerate(best_nodes, 1):
            info = node['node']
            f.write(
                f"{idx:2d}. {info['name']} | "
                f"{node['latency']:7.2f} | "
                f"{node['speed']/1024:9.2f} | "
                f"{node['score']:.2f}\n"
            )
    
    log(f"🎉 测试完成！有效节点: {len(best_nodes)}/{len(unique_nodes)}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f"!!! 致命错误: {str(e)}")
