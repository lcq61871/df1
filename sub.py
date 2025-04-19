import os
import yaml
import time
import json
import subprocess
import concurrent.futures
from tempfile import NamedTemporaryFile

DEBUG = True
TIMEOUT = 20  # 总超时时间(秒)
TEST_URL = "https://www.gstatic.com/generate_204"

def log(message):
    if DEBUG:
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

def test_hysteria2(node):
    """测试 Hysteria2 节点"""
    try:
        # 生成临时配置文件
        config = {
            "server": f"{node['server']}:{node['port']}",
            "protocol": "udp",
            "up_mbps": 100,
            "down_mbps": 100,
            "auth_str": node.get('auth_str', ''),
            "insecure": node.get('skip-cert-verify', False),
            "socks5": {"listen": "127.0.0.1:0"}
        }

        with NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(config, f)
            config_path = f.name

        # 运行速度测试
        start_time = time.time()
        cmd = [
            'hysteria', 'client',
            '--config', config_path,
            'test',
            '--duration', '5'  # 5秒测试时长
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT
        )
        os.unlink(config_path)

        if result.returncode != 0:
            log(f"Hysteria2 测试失败 {node['name']}: {result.stderr[:100]}")
            return None

        # 解析输出结果
        for line in result.stdout.split('\n'):
            if 'avg_rtt' in line:
                latency = float(line.split('=')[1].strip().replace('ms', ''))
                return latency
        return None

    except Exception as e:
        log(f"Hysteria2 异常 {node['name']}: {str(e)}")
        return None

def test_vless(node):
    """测试 VLESS 节点"""
    try:
        # 生成 Xray 配置
        config = {
            "inbounds": [{
                "port": 1080,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"auth": "noauth"}
            }],
            "outbounds": [{
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": node['server'],
                        "port": node['port'],
                        "users": [{
                            "id": node['uuid'],
                            "encryption": node.get('encryption', 'none')
                        }]
                    }]
                },
                "streamSettings": node.get('streamSettings', {})
            }]
        }

        with NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(config, f)
            config_path = f.name

        # 启动 Xray 并测试
        start_time = time.time()
        with subprocess.Popen(
            ['xray', 'run', '-c', config_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        ) as proc:
            time.sleep(2)  # 等待启动
            
            test_cmd = [
                'curl', '-sS',
                '--connect-timeout', '10',
                '--socks5-hostname', '127.0.0.1:1080',
                '-o', '/dev/null',
                '-w', '%{time_total}',
                TEST_URL
            ]
            
            result = subprocess.run(
                test_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=TIMEOUT
            )
            
            proc.terminate()
            os.unlink(config_path)

        if result.returncode == 0:
            return float(result.stdout) * 1000  # 转为毫秒
        log(f"VLESS 测试失败 {node['name']}: {result.stderr[:100]}")
        return None

    except Exception as e:
        log(f"VLESS 异常 {node['name']}: {str(e)}")
        return None

def test_proxy(node):
    """协议测试分发"""
    protocol_handlers = {
        'ss': test_ss,          # 原有SS测试函数
        'vmess': test_vmess,    # 原有VMess测试函数
        'hysteria2': test_hysteria2,
        'vless': test_vless
    }
    
    proto = node.get('type', '').lower()
    
    if proto not in protocol_handlers:
        log(f"⚠️ 未知协议类型: {proto}")
        return None
        
    # 必要字段验证
    required_fields = {
        'hysteria2': ['server', 'port', 'auth_str'],
        'vless': ['server', 'port', 'uuid']
    }.get(proto, [])
    
    for field in required_fields:
        if field not in node:
            log(f"❌ 缺失字段 {field} in {node.get('name')}")
            return None
    
    start_time = time.time()
    try:
        latency = protocol_handlers[proto](node)
        if latency is not None:
            return {'node': node, 'latency': latency}
    except Exception as e:
        log(f"测试异常 {node['name']}: {str(e)}")
    
    return None

# main函数和其他部分保持不变（需包含原有协议支持）
