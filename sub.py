import os
import yaml
import time
import json
import subprocess
import concurrent.futures
from tempfile import NamedTemporaryFile
from datetime import datetime

DEBUG = True
TIMEOUT = 20  # 总超时时间(秒)
TEST_URL = "https://www.gstatic.com/generate_204"

def log(message):
    if DEBUG:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

# ----------- 协议测试核心函数 -----------
def test_ss(node):
    """Shadowsocks 完整测试"""
    try:
        cmd = [
            'curl', '-sS', '--connect-timeout', '10',
            '--socks5-hostname', f"{node['server']}:{node['port']}",
            '--proxy-user', f"{node['cipher']}:{node['password']}",
            '-o', '/dev/null', '-w', '%{http_code} %{time_total}',
            TEST_URL
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and '204' in result.stdout:
            latency = float(result.stdout.split()[1]) * 1000
            return latency
        return None
    except Exception as e:
        log(f"SS测试异常: {str(e)}")
        return None

def test_vmess(node):
    """VMess 深度验证"""
    try:
        # TCP端口检查
        nc_cmd = ['nc', '-zvw5', node['server'], str(node['port'])]
        if subprocess.run(nc_cmd).returncode != 0:
            return None
            
        # TLS证书验证（如果启用）
        if node.get('tls'):
            openssl_cmd = [
                'openssl', 's_client', '-connect',
                f"{node['server']}:{node['port']}", '-servername', node.get('sni', '')
            ]
            openssl_result = subprocess.run(openssl_cmd, capture_output=True, text=True)
            if 'Verify return code: 0' not in openssl_result.stderr:
                log(f"TLS验证失败: {node['name']}")
                return None
                
        return test_tcp(node)  # 返回基础TCP延迟
    except Exception as e:
        log(f"VMess异常: {str(e)}")
        return None

def test_hysteria2(node):
    """Hysteria2 性能测试"""
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        os.unlink(config_file)
        
        # 解析输出
        if 'speed=' in result.stdout:
            latency = float(result.stdout.split('latency=')[1].split()[0])
            return latency
        return None
    except Exception as e:
        log(f"Hysteria2异常: {str(e)}")
        return None

def test_vless(node):
    """VLESS 完整链路验证"""
    try:
        # 生成Xray配置
        config = {
            "inbounds": [{"port": 1080, "protocol": "socks"}],
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
            
        # 启动Xray
        xray_proc = subprocess.Popen(
            ['xray', 'run', '-c', config_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        time.sleep(3)  # 等待启动
        
        # 发起测试请求
        curl_cmd = [
            'curl', '-sS', '--socks5-hostname', '127.0.0.1:1080',
            '-o', '/dev/null', '-w', '%{time_total}', TEST_URL
        ]
        result = subprocess.run(curl_cmd, capture_output=True, text=True)
        
        xray_proc.terminate()
        os.unlink(config_file)
        
        if result.returncode == 0:
            return float(result.stdout) * 1000
        return None
    except Exception as e:
        log(f"VLESS异常: {str(e)}")
        return None

# ----------- 主逻辑 -----------
def test_proxy(node):
    """协议分发处理器"""
    protocol_map = {
        'ss': test_ss,
        'vmess': test_vmess,
        'hysteria2': test_hysteria2,
        'vless': test_vless
    }
    
    handler = protocol_map.get(node.get('type', '').lower())
    if not handler:
        log(f"⏭️ 跳过不支持的协议: {node.get('type')}")
        return None
        
    # 必要字段检查
    required = {
        'ss': ['server', 'port', 'cipher', 'password'],
        'vmess': ['server', 'port', 'uuid'],
        'hysteria2': ['server', 'port', 'auth_str'],
        'vless': ['server', 'port', 'uuid']
    }.get(node['type'], [])
    
    if any(field not in node for field in required):
        log(f"❌ 缺失必要字段: {node.get('name')}")
        return None
        
    return handler(node)

# ... [保持原有main函数不变] ...
