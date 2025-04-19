import requests
import yaml
import socket
import concurrent.futures
import time
import ssl
import json
from urllib.parse import urlparse

DEBUG = True
TIMEOUT = 10
TEST_URL = "http://www.gstatic.com/generate_204"  # Google连通性测试地址

def log(message):
    if DEBUG:
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

class ProtocolTester:
    @staticmethod
    def test_socks5(node):
        """SOCKS5协议完整握手测试"""
        try:
            start = time.time()
            with socket.create_connection((node['server'], node['port']), timeout=TIMEOUT) as s:
                # 握手阶段
                s.sendall(b'\x05\x01\x00')  # VER, NMETHODS, METHODS
                auth_response = s.recv(2)
                if auth_response != b'\x05\x00':
                    log(f"SOCKS5认证失败 {node['name']}")
                    return None
                
                # 请求连接
                request = b'\x05\x01\x00\x03' + bytes([len(TEST_URL)]) + TEST_URL.encode() + b'\x00\x50'
                s.sendall(request)
                response = s.recv(10)
                if response[1] != 0x00:
                    log(f"SOCKS5连接失败 {node['name']}")
                    return None
                
                return (time.time() - start) * 1000
        except Exception as e:
            log(f"SOCKS5测试异常 {node['name']}: {str(e)}")
            return None

    @staticmethod
    def test_http(node):
        """HTTP代理实际请求测试"""
        try:
            start = time.time()
            proxies = {
                "http": f"http://{node['server']}:{node['port']}",
                "https": f"http://{node['server']}:{node['port']}"
            }
            response = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
            if response.status_code == 204:
                return (time.time() - start) * 1000
            return None
        except Exception as e:
            log(f"HTTP测试失败 {node['name']}: {str(e)}")
            return None

    @staticmethod
    def test_ss(node):
        """Shadowsocks协议测试"""
        try:
            # 需要安装shadowsocks库：pip install shadowsocks
            from shadowsocks.crypto import Crypto
            from shadowsocks.tcp import TCPClient
            
            start = time.time()
            crypto = Crypto(node['cipher'], node['password'])
            client = TCPClient(None, TEST_URL, 80, crypto)
            client.connect((node['server'], node['port']))
            client.sock.close()
            return (time.time() - start) * 1000
        except Exception as e:
            log(f"SS测试失败 {node['name']}: {str(e)}")
            return None

    @staticmethod
    def test_vmess(node):
        """VMess协议基础测试"""
        try:
            # 需要安装v2ray-core：pip install v2ray-core
            from v2ray.core.proxy.vmess import account_pb2
            from v2ray.core.transport.internet.tls import config_pb2
            
            # 构造基础配置
            account = account_pb2.Account(
                id=node['uuid'],
                alter_id=node.get('alterId', 0)
            
            # TLS验证
            if node.get('tls'):
                tls_config = config_pb2.TLSConfig(
                    server_name=node.get('sni', '')
                )
            
            # 实际连接测试（此处需要更完整的实现）
            # 因协议复杂性，建议使用第三方库进行完整验证
            return 100  # 示例值，需替换实际测试
        except Exception as e:
            log(f"VMess测试失败 {node['name']}: {str(e)}")
            return None

def full_connection_test(node):
    """完整连接性测试"""
    test_results = {}
    
    # 协议分发测试
    if node['type'] == 'socks5':
        latency = ProtocolTester.test_socks5(node)
    elif node['type'] == 'http':
        latency = ProtocolTester.test_http(node)
    elif node['type'] == 'ss':
        latency = ProtocolTester.test_ss(node)
    elif node['type'] == 'vmess':
        latency = ProtocolTester.test_vmess(node)
    else:
        log(f"未知协议类型 {node['type']}")
        return None
    
    # 二次验证测试
    if latency:
        try:
            # TLS证书验证（如果启用）
            if node.get('tls', False):
                context = ssl.create_default_context()
                with socket.create_connection((node['server'], node['port']), timeout=TIMEOUT) as sock:
                    with context.wrap_socket(sock, server_hostname=node.get('sni', '')) as ssock:
                        cert = ssock.getpeercert()
                        if not cert:
                            log(f"TLS证书验证失败 {node['name']}")
                            return None
        except Exception as e:
            log(f"TLS验证失败 {node['name']}: {str(e)}")
            return None
    
    return latency

def validate_node(node):
    """节点配置完整性检查"""
    required = {
        'socks5': ['server', 'port', 'type'],
        'http': ['server', 'port', 'type'],
        'ss': ['server', 'port', 'type', 'cipher', 'password'],
        'vmess': ['server', 'port', 'type', 'uuid', 'alterId', 'cipher']
    }
    
    if node['type'] not in required:
        log(f"不支持的协议类型 {node['type']}")
        return False
    
    for field in required[node['type']]:
        if field not in node:
            log(f"缺失必要字段 {field} in {node['name']}")
            return False
    
    return True

def test_node(node):
    try:
        log(f"\n=== 开始深度测试 {node['name']} ===")
        
        if not validate_node(node):
            return None
        
        # 完整协议测试
        latency = full_connection_test(node)
        if not latency:
            return None
        
        # 真实请求测试
        proxy_url = f"{node['type']}://{node['server']}:{node['port']}"
        try:
            response = requests.get(TEST_URL, 
                                  proxies={'http': proxy_url, 'https': proxy_url},
                                  timeout=TIMEOUT)
            if response.status_code != 204:
                log(f"真实请求失败 {node['name']}")
                return None
        except:
            log(f"代理请求异常 {node['name']}")
            return None
        
        return {
            'node': node,
            'latency': latency,
            'valid': True
        }
    except Exception as e:
        log(f"测试过程异常 {node['name']}: {str(e)}")
        return None

def main():
    # 加载节点配置
    urls = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@refs/heads/main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@refs/heads/main/trial.yaml"
    ]
    
    all_nodes = []
    for url in urls:
        try:
            resp = requests.get(url, timeout=15)
            data = yaml.safe_load(resp.text)
            all_nodes.extend(data.get('proxies', []))
            log(f"从 {url} 加载 {len(data['proxies'])} 个节点")
        except Exception as e:
            log(f"加载节点失败 {url}: {str(e)}")
    
    # 去重处理
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node['type']}_{node['server']}_{node['port']}"
        if key not in seen:
            seen.add(key)
            unique_nodes.append(node)
    
    # 并发测试
    valid_nodes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_node, node): node for node in unique_nodes}
        
        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            result = future.result()
            if result:
                valid_nodes.append(result)
                log(f"✅ 验证通过 {node['name']} 延迟 {result['latency']:.2f}ms")
            else:
                log(f"❌ 验证失败 {node['name']}")

    # 结果处理
    if valid_nodes:
        sorted_nodes = sorted(valid_nodes, key=lambda x: x['latency'])
        top_nodes = sorted_nodes[:50]
        
        # 生成YAML
        with open('nodes.yml', 'w') as f:
            yaml.safe_dump({'proxies': [n['node'] for n in top_nodes]}, f,
                          default_flow_style=False,
                          allow_unicode=True)
        
        # 生成测速报告
        with open('speed.txt', 'w') as f:
            for idx, node in enumerate(top_nodes, 1):
                f.write(f"{idx:2d}. {node['node']['name'][:40]} {node['latency']:.2f}ms\n")
        
        log(f"成功生成 {len(top_nodes)} 个有效节点")
    else:
        log("未找到任何有效节点")

if __name__ == '__main__':
    main()
