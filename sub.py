import os
import yaml
import time
import subprocess
import concurrent.futures
import traceback
from urllib.parse import urlparse

DEBUG = True
TIMEOUT = 15  # 总超时时间(秒)
TEST_URL = "https://www.gstatic.com/generate_204"

def log(message):
    """增强的日志函数，同时打印到控制台和日志文件"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    if DEBUG:
        print(log_msg)
    
    # 确保日志目录存在
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # 写入日志文件
    try:
        with open(os.path.join(log_dir, "sub.log"), "a", encoding='utf-8') as f:
            f.write(log_msg + "\n")
    except Exception as e:
        print(f"!!! 无法写入日志文件: {str(e)}")

def test_ss(node):
    """测试Shadowsocks节点"""
    try:
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
            text=True,
            timeout=TIMEOUT
        )
        
        if result.returncode == 0 and '204' in result.stdout:
            return float(result.stdout.split()[1]) * 1000  # 秒转毫秒
        log(f"SS测试失败 {node.get('name', '未知节点')}: {result.stderr[:100]}")
    except subprocess.TimeoutExpired:
        log(f"SS测试超时 {node.get('name', '未知节点')}")
    except Exception as e:
        log(f"SS异常 {node.get('name', '未知节点')}: {str(e)}")
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
            text=True,
            timeout=TIMEOUT
        )
        
        if result.returncode == 0:
            return (time.time() - start_time) * 1000
        log(f"TCP测试失败 {node.get('name', '未知节点')}: {result.stderr[:100]}")
    except subprocess.TimeoutExpired:
        log(f"TCP测试超时 {node.get('name', '未知节点')}")
    except Exception as e:
        log(f"TCP异常 {node.get('name', '未知节点')}: {str(e)}")
    return None

def test_node(node):
    """节点测试分发"""
    protocol_testers = {
        'ss': test_ss,
        'vmess': test_tcp,
        'trojan': test_tcp,
        'http': test_tcp
    }
    
    if node.get('type') not in protocol_testers:
        log(f"⚠️ 跳过不支持协议: {node.get('type', '未知类型')}")
        return None
        
    required_fields = ['server', 'port', 'name']
    if not all(k in node for k in required_fields):
        missing = [k for k in required_fields if k not in node]
        log(f"⚠️ 节点字段缺失({missing}): {node.get('name', '未知节点')}")
        return None
        
    try:
        latency = protocol_testers[node['type']](node)
        if latency is not None:
            log(f"✅ {node['name']} 有效 ({latency:.2f}ms)")
            return {'node': node, 'latency': latency}
    except Exception as e:
        log(f"测试异常 {node.get('name', '未知节点')}: {str(e)}")
        log(traceback.format_exc())
    return None

def ensure_output_directory():
    """确保输出目录存在并可写"""
    output_dir = "output"
    try:
        os.makedirs(output_dir, exist_ok=True)
        # 测试写入权限
        test_file = os.path.join(output_dir, '.permission_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return output_dir
    except Exception as e:
        log(f"❌ 输出目录不可写: {str(e)}")
        raise

def load_nodes(sources):
    """加载节点源"""
    all_nodes = []
    for url in sources:
        try:
            log(f"正在加载节点源: {url}")
            result = subprocess.run(
                ['curl', '-sSL', url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=True
            )
            data = yaml.safe_load(result.stdout)
            if not data:
                raise ValueError("空YAML数据")
                
            valid_nodes = [n for n in data.get('proxies', []) if isinstance(n, dict) and 'type' in n]
            all_nodes.extend(valid_nodes)
            log(f"📥 加载 {len(valid_nodes)} 节点 from {url}")
        except Exception as e:
            log(f"❌ 加载失败 {url}: {str(e)}")
            if hasattr(e, 'stderr') and e.stderr:
                log(f"错误详情: {e.stderr.decode()[:200]}")
    return all_nodes

def write_results(output_dir, results):
    """写入结果文件"""
    # 确保结果按延迟排序
    sorted_nodes = sorted(results, key=lambda x: x['latency'])[:50]
    
    # 写入YAML文件
    yaml_file = os.path.join(output_dir, 'nodes.yml')
    try:
        with open(yaml_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(
                {'proxies': [n['node'] for n in sorted_nodes]},
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False
            )
        log(f"✅ 节点文件已写入: {yaml_file} ({os.path.getsize(yaml_file)} 字节)")
    except Exception as e:
        log(f"❌ 写入nodes.yml失败: {str(e)}")
        raise
    
    # 写入速度测试文件
    speed_file = os.path.join(output_dir, 'speed.txt')
    try:
        with open(speed_file, 'w', encoding='utf-8') as f:
            f.write("排名 | 节点名称 | 延迟(ms)\n")
            f.write("-"*40 + "\n")
            for idx, item in enumerate(sorted_nodes, 1):
                f.write(f"{idx:2d}. {item['node']['name']} | {item['latency']:.2f}\n")
            f.flush()  # 确保立即写入
            os.fsync(f.fileno())  # 强制同步到磁盘
        
        log(f"✅ 速度文件已写入: {speed_file} ({os.path.getsize(speed_file)} 字节)")
        # 验证文件内容
        with open(speed_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            log(f"文件验证: 共 {len(lines)} 行，示例: {lines[:3] if lines else '空文件'}")
    except Exception as e:
        log(f"❌ 写入speed.txt失败: {str(e)}")
        raise

def main():
    log("=== 开始节点测试 ===")
    log(f"当前工作目录: {os.getcwd()}")
    log(f"Python版本: {sys.version}")
    
    try:
        # 加载节点源
        sources = [
            "https://cdn.jsdelivr.net/gh/lcq61871/NoMoreWalls@refs/heads/master/snippets/nodes_TW.meta.yml",
            "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@main/trial.yaml"
        ]
        all_nodes = load_nodes(sources)
        
        # 节点去重
        seen = set()
        unique_nodes = []
        for node in all_nodes:
            key = f"{node.get('type')}_{node.get('server')}_{node.get('port')}"
            if key not in seen:
                seen.add(key)
                unique_nodes.append(node)
        log(f"🔍 去重后节点数: {len(unique_nodes)}")
        
        # 并发测试
        valid_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(test_node, n): n for n in unique_nodes}
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        valid_results.append(result)
                except Exception as e:
                    log(f"⚠️ 并发任务异常: {str(e)}")
        
        # 输出结果
        output_dir = ensure_output_directory()
        if valid_results:
            write_results(output_dir, valid_results)
            log(f"🎉 完成! 共 {len(valid_results)} 个有效节点")
        else:
            log("❌ 未找到有效节点")
            # 创建空文件确保GitHub Actions能提交
            open(os.path.join(output_dir, 'speed.txt'), 'w').close()
            open(os.path.join(output_dir, 'nodes.yml'), 'w').close()
            
    except Exception as e:
        log(f"!!! 主程序异常: {str(e)}")
        log(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    import sys
    main()
