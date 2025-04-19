import os
import yaml
import time
import subprocess
import concurrent.futures
import socket
from urllib.parse import urlparse

DEBUG = True
TIMEOUT = 20  # 增加超时时间
TEST_URL = "https://www.gstatic.com/generate_204"
SPEED_TEST_URL = "https://speed.cloudflare.com/__down?bytes=1000000"  # 1MB测试文件
MAX_WORKERS = 20
TOP_NODES = 50

def log(message):
    """增强日志功能"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open("sub.log", "a", encoding='utf-8') as f:
        f.write(log_msg + "\n")

def is_port_open(server, port, timeout=5):
    """检查端口是否真正开放"""
    try:
        with socket.create_connection((server, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False
    except Exception as e:
        log(f"端口检查异常 {server}:{port} - {str(e)}")
        return False

def test_real_connection(cmd, node_name):
    """测试真实数据传输"""
    try:
        start_time = time.time()
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT
        )
        
        if result.returncode == 0:
            speed = len(result.stdout) / (time.time() - start_time)  # bytes/sec
            return speed
        log(f"数据传输测试失败 {node_name}: {result.stderr[:100]}")
    except subprocess.TimeoutExpired:
        log(f"数据传输超时 {node_name}")
    except Exception as e:
        log(f"数据传输异常 {node_name}: {str(e)}")
    return 0

def test_ss(node):
    """增强版SS测试"""
    try:
        # 1. 先检查端口可用性
        if not is_port_open(node['server'], node['port']):
            log(f"⛔ SS端口不可达 {node['name']}")
            return None, None
        
        # 2. 测试基础连接
        curl_cmd = [
            'curl', '-sS',
            '--connect-timeout', '10',
            '--max-time', '15',
            '--socks5-hostname', f"{node['server']}:{node['port']}",
            '--proxy-user', f"{node['cipher']}:{node['password']}",
            '-o', '/dev/null',
            '-w', '%{http_code} %{time_total}',
            TEST_URL
        ]
        
        result = subprocess.run(
            curl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT
        )
        
        if result.returncode != 0 or '204' not in result.stdout:
            log(f"SS连接测试失败 {node['name']}: {result.stderr[:100]}")
            return None, None
        
        latency = float(result.stdout.split()[1]) * 1000
        
        # 3. 测试真实传输速度
        speed_cmd = [
            'curl', '-sS',
            '--connect-timeout', '10',
            '--max-time', '20',
            '--socks5-hostname', f"{node['server']}:{node['port']}",
            '--proxy-user', f"{node['cipher']}:{node['password']}",
            SPEED_TEST_URL
        ]
        
        speed = test_real_connection(speed_cmd, node['name'])
        
        if speed <= 0:
            return None, None
            
        log(f"✅ SS验证通过 {node['name']} | 延迟: {latency:.2f}ms | 速度: {speed/1024:.2f} KB/s")
        return latency, speed
        
    except Exception as e:
        log(f"SS测试异常 {node['name']}: {str(e)}")
        return None, None

def test_vmess(node):
    """VMess真实连接测试"""
    try:
        # 需要xray-core进行真实协议测试
        config = {
            "inbounds": [{"port": 1080, "protocol": "socks", "listen": "127.0.0.1"}],
            "outbounds": [{
                "protocol": "vmess",
                "settings": {"vnext": [{
                    "address": node['server'],
                    "port": node['port'],
                    "users": [{"id": node['uuid']}]
                }]},
                "streamSettings": node.get('streamSettings', {})
            }]
        }
        
        with open("temp_config.json", "w") as f:
            json.dump(config, f)
            
        xray_proc = subprocess.Popen(['xray', 'run', '-c', 'temp_config.json'], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(2)  # 等待xray启动
        
        try:
            # 测试基础连接
            test_cmd = [
                'curl', '-sS',
                '--connect-timeout', '10',
                '--max-time', '15',
                '--socks5-hostname', '127.0.0.1:1080',
                '-o', '/dev/null',
                '-w', '%{http_code} %{time_total}',
                TEST_URL
            ]
            
            result = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0 or '204' not in result.stdout:
                return None, None
                
            latency = float(result.stdout.split()[1]) * 1000
            
            # 测试下载速度
            speed_cmd = [
                'curl', '-sS',
                '--connect-timeout', '10',
                '--max-time', '20',
                '--socks5-hostname', '127.0.0.1:1080',
                SPEED_TEST_URL
            ]
            
            speed = test_real_connection(speed_cmd, node['name'])
            if speed <= 0:
                return None, None
                
            log(f"✅ VMess验证通过 {node['name']} | 延迟: {latency:.2f}ms | 速度: {speed/1024:.2f} KB/s")
            return latency, speed
            
        finally:
            xray_proc.terminate()
            os.remove("temp_config.json")
            
    except Exception as e:
        log(f"VMess测试异常 {node['name']}: {str(e)}")
        return None, None

def test_node(node):
    """增强版节点测试"""
    protocol_testers = {
        'ss': test_ss,
        'vmess': test_vmess,
        'trojan': lambda n: test_vmess(n)  # 类似VMess测试方式
    }
    
    if node['type'] not in protocol_testers:
        log(f"⚠️ 跳过不支持协议: {node['type']}")
        return None
        
    required_fields = {
        'ss': ['server', 'port', 'name', 'cipher', 'password'],
        'vmess': ['server', 'port', 'name', 'uuid'],
        'trojan': ['server', 'port', 'name', 'password']
    }
    
    missing = [f for f in required_fields.get(node['type'], []) if f not in node]
    if missing:
        log(f"⚠️ 节点字段缺失 {node.get('name')}: {missing}")
        return None
        
    try:
        latency, speed = protocol_testers[node['type']](node)
        if latency and speed:
            return {
                'node': node,
                'latency': latency,
                'speed': speed,  # bytes/sec
                'score': calculate_score(latency, speed)
            }
        return None
    except Exception as e:
        log(f"测试异常 {node.get('name')}: {str(e)}")
        return None

def calculate_score(latency, speed):
    """综合评分算法 (延迟占比30%，速度占比70%)"""
    normalized_latency = max(0, 1 - latency / 1000)  # 假设1秒为最大可接受延迟
    normalized_speed = min(1, speed / (1024 * 1024))  # 1MB/s为满分
    return 0.3 * normalized_latency + 0.7 * normalized_speed

def main():
    log("=== 开始增强版节点测试 ===")
    
    # 加载节点源
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

    # 节点去重
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node.get('type')}_{node.get('server')}_{node.get('port')}"
        if key not in seen and node.get('type') in ['ss', 'vmess', 'trojan']:
            seen.add(key)
            unique_nodes.append(node)
    log(f"🔍 去重后待测节点: {len(unique_nodes)}")

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
                log(f"并发测试异常: {str(e)}")

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
                f"{node['score']:.4f}\n"
            )
    
    log(f"🎉 测试完成! 有效节点: {len(valid_nodes)}/{len(unique_nodes)}")
    log(f"🏆 最佳节点已保存到 output/ 目录")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f"!!! 主程序异常: {str(e)}")
        raise
