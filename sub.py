import os
import yaml
import time
import subprocess
import concurrent.futures
from urllib.parse import urlparse

DEBUG = True
TIMEOUT = 15  # 总超时时间(秒)
TEST_URL = "https://www.gstatic.com/generate_204"

def log(message):
    if DEBUG:
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

def test_ss(node):
    """测试Shadowsocks节点"""
    try:
        start_time = time.time()
        cmd = [
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
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0 and '204' in result.stdout:
            latency = float(result.stdout.split()[1]) * 1000  # 秒转毫秒
            return latency
        log(f"SS测试失败 {node['name']}: {result.stderr[:100]}")
        return None
    except Exception as e:
        log(f"SS异常 {node['name']}: {str(e)}")
        return None

def test_tcp(node):
    """通用TCP端口测试"""
    try:
        start_time = time.time()
        cmd = [
            'nc', '-zv', '-w', '10',
            node['server'], str(node['port'])
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            return (time.time() - start_time) * 1000
        log(f"TCP测试失败 {node['name']}: {result.stderr[:100]}")
        return None
    except Exception as e:
        log(f"TCP异常 {node['name']}: {str(e)}")
        return None

def test_node(node):
    """节点测试分发"""
    protocol_testers = {
        'ss': test_ss,
        'vmess': test_tcp,  # VMess需要TCP基础验证
        'trojan': test_tcp,
        'http': lambda n: test_tcp(n)  # HTTP端口验证
    }
    
    if node['type'] not in protocol_testers:
        log(f"⚠️ 跳过不支持协议: {node['type']}")
        return None
        
    if not all(k in node for k in ['server', 'port', 'name']):
        log(f"⚠️ 节点字段缺失: {node.get('name')}")
        return None
        
    try:
        latency = protocol_testers[node['type']](node)
        if latency:
            log(f"✅ {node['name']} 有效 ({latency:.2f}ms)")
            return {'node': node, 'latency': latency}
        return None
    except Exception as e:
        log(f"全局异常: {str(e)}")
        return None

def main():
    # 加载节点源
    sources = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@main/trial.yaml"
    ]
    
    all_nodes = []
    for url in sources:
        try:
            result = subprocess.run(
                ['curl', '-sSL', url],
                stdout=subprocess.PIPE,
                check=True
            )
            data = yaml.safe_load(result.stdout)
            valid_nodes = [n for n in data.get('proxies', []) if 'type' in n]
            all_nodes.extend(valid_nodes)
            log(f"📥 加载 {len(valid_nodes)} 节点 from {url}")
        except Exception as e:
            log(f"❌ 加载失败 {url}: {str(e)}")

    # 节点去重 (服务器+端口+类型)
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node['type']}_{node['server']}_{node['port']}"
        if key not in seen:
            seen.add(key)
            unique_nodes.append(node)
    log(f"🔍 去重后节点数: {len(unique_nodes)}")

    # 并发测试 (限制20线程)
    valid_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_node, n): n for n in unique_nodes}
        
        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            try:
                result = future.result()
                if result:
                    valid_results.append(result)
            except Exception as e:
                log(f"⚠️ 并发错误: {str(e)}")

    # 生成结果文件
    if valid_results:
        sorted_nodes = sorted(valid_results, key=lambda x: x['latency'])[:50]
        
        with open('nodes.yml', 'w') as f:
            yaml.safe_dump(
                {'proxies': [n['node'] for n in sorted_nodes]},
                f,
                default_flow_style=False,
                allow_unicode=True
            )
            
        with open('speed.txt', 'w') as f:
            f.write("排名 | 节点名称 | 延迟(ms)\n")
            f.write("-"*40 + "\n")
            for idx, item in enumerate(sorted_nodes, 1):
                f.write(f"{idx:2d}. {item['node']['name']} | {item['latency']:.2f}\n")
        
        log(f"🎉 生成 {len(sorted_nodes)} 个有效节点")
    else:
        log("❌ 未找到有效节点")

if __name__ == '__main__':
    main()
