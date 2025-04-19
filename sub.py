import os
import yaml
import time
import json
import requests
import subprocess
import concurrent.futures
from datetime import datetime
from tempfile import NamedTemporaryFile
import signal

DEBUG = True
TIMEOUT = 8  # 超时时间 8 秒
TEST_URLS = [
    "http://cp.cloudflare.com/generate_204"
]
XRAY_BIN = "/usr/local/bin/xray"
HYSTERIA_BIN = "/usr/local/bin/hysteria"
MAX_NODES = 800  # 限制测试节点数
MAX_THREADS = 5  # 增加到 5 线程

def log(message):
    if DEBUG:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def kill_process(proc):
    """强制终止进程"""
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
    except Exception:
        pass

# ----------------- Xray 配置文件生成 -----------------
def generate_xray_config(node, protocol):
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{"port": 1080, "protocol": "socks", "settings": {"auth": "noauth", "udp": True}}],
        "outbounds": [
            {"protocol": protocol, "settings": {}, "tag": "proxy"},
            {"protocol": "freedom", "settings": {}, "tag": "direct"}
        ],
        "routing": {"rules": [{"type": "field", "outboundTag": "proxy", "domain": ["geosite:google"]}]}
    }

    if protocol == "vmess":
        config["outbounds"][0]["settings"] = {
            "vnext": [{"address": node["server"], "port": int(node["port"]), "users": [{"id": node["uuid"], "alterId": node.get("alterId", 0)}]}]
        }
        if node.get("network") == "ws":
            config["outbounds"][0]["streamSettings"] = {
                "network": "ws",
                "wsSettings": {"path": node.get("ws-opts", {}).get("path", "/")}
            }
    elif protocol == "vless":
        config["outbounds"][0]["settings"] = {
            "vnext": [{"address": node["server"], "port": int(node["port"]), "users": [{"id": node["uuid"], "encryption": "none"}]}]
        }
        if node.get("network") == "grpc":
            config["outbounds"][0]["streamSettings"] = {
                "network": "grpc",
                "grpcSettings": {"serviceName": node.get("grpc-opts", {}).get("serviceName", "")}
            }
    elif protocol == "trojan":
        config["outbounds"][0]["settings"] = {
            "servers": [{"address": node["server"], "port": int(node["port"]), "password": node["password"]}]
        }
    elif protocol == "shadowsocks":
        config["outbounds"][0]["settings"] = {
            "servers": [{"address": node["server"], "port": int(node["port"]), "method": node["cipher"], "password": node["password"]}]
        }
    return config

# ----------------- 协议测试函数 -----------------
def test_with_xray(node, protocol):
    proc = None
    config_path = None
    try:
        log(f"开始测试 {protocol.upper()} 节点: {node.get('name')} ({node['server']}:{node['port']})")
        config = generate_xray_config(node, protocol)
        with NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(config, f, indent=2)
            config_path = f.name

        proc = subprocess.Popen([XRAY_BIN, "run", "-c", config_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)  # 缩短等待时间

        for test_url in TEST_URLS:
            try:
                start = time.time()
                cmd = ["curl", "-sS", "--connect-timeout", "3", "--proxy", "socks5h://127.0.0.1:1080", "-o", "/dev/null", "-w", "%{http_code}", test_url]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
                latency = (time.time() - start) * 1000

                stderr = result.stderr.strip() if result.stderr else "无错误输出"
                log(f"{protocol.upper()} {node.get('name')} (URL={test_url}): 状态码={result.stdout.strip()}, 延迟={latency:.2f}ms, 错误={stderr}")
                if result.stdout.strip() in ["200", "204", "301", "302", "404"]:
                    return latency
            except subprocess.TimeoutExpired:
                log(f"{protocol.upper()} {node.get('name')} (URL={test_url}): 超时")
                continue
            except Exception as e:
                log(f"{protocol.upper()} {node.get('name')} (URL={test_url}): 错误={str(e)}")
                continue

        log(f"{protocol.upper()} {node.get('name')}: 测试失败")
        return None
    except Exception as e:
        log(f"{protocol.upper()} {node.get('name')}: 异常={str(e)}")
        return None
    finally:
        if proc:
            kill_process(proc)
        if config_path and os.path.exists(config_path):
            os.unlink(config_path)

def test_hysteria2(node):
    proc = None
    config_path = None
    try:
        log(f"开始测试 Hysteria2 节点: {node.get('name')} ({node['server']}:{node['port']})")
        config = {"server": f"{node['server']}:{node['port']}", "auth": node.get("password", ""), "tls": {"insecure": node.get("allowInsecure", False)}}
        with NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(config, f)
            config_path = f.name

        proc = subprocess.Popen([HYSTERIA_BIN, "client", "-c", config_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)

        for test_url in TEST_URLS:
            try:
                start = time.time()
                cmd = ["curl", "-sS", "--connect-timeout", "3", "--proxy", "socks5h://127.0.0.1:1080", "-o", "/dev/null", "-w", "%{http_code}", test_url]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
                latency = (time.time() - start) * 1000

                stderr = result.stderr.strip() if result.stderr else "无错误输出"
                log(f"Hysteria2 {node.get('name')} (URL={test_url}): 状态码={result.stdout.strip()}, 延迟={latency:.2f}ms, 错误={stderr}")
                if result.stdout.strip() in ["200", "204", "301", "302", "404"]:
                    return latency
            except subprocess.TimeoutExpired:
                log(f"Hysteria2 {node.get('name')} (URL={test_url}): 超时")
                continue
            except Exception as e:
                log(f"Hysteria2 {node.get('name')} (URL={test_url}): 错误={str(e)}")
                continue

        log(f"Hysteria2 {node.get('name')}: 测试失败")
        return None
    except Exception as e:
        log(f"Hysteria2 {node.get('name')}: 异常={str(e)}")
        return None
    finally:
        if proc:
            kill_process(proc)
        if config_path and os.path.exists(config_path):
            os.unlink(config_path)

def test_proxy(node):
    protocol_handlers = {
        "ss": lambda n: test_with_xray(n, "shadowsocks"),
        "vmess": lambda n: test_with_xray(n, "vmess"),
        "vless": lambda n: test_with_xray(n, "vless"),
        "trojan": lambda n: test_with_xray(n, "trojan"),
        "hysteria2": test_hysteria2,
    }

    proto = node.get("type", "").lower()
    if proto not in protocol_handlers:
        log(f"⚠️ 不支持协议: {proto} ({node.get('name')})")
        return None

    required_fields = {
        "ss": ["server", "port", "cipher", "password"],
        "vmess": ["server", "port", "uuid"],
        "vless": ["server", "port", "uuid"],
        "trojan": ["server", "port", "password"],
        "hysteria2": ["server", "port", "password"],
    }.get(proto, [])

    if any(field not in node for field in required_fields):
        log(f"❌ 缺失字段: {node.get('name')} {required_fields}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(protocol_handlers[proto], node)
        try:
            return future.result(timeout=TIMEOUT + 2)
        except concurrent.futures.TimeoutError:
            log(f"❌ 超时: {node.get('name')}")
            return None

# ----------------- 主逻辑 -----------------
def main():
    sources = [
        "https://cdn.jsdelivr.net/gh/lcq61871/NoMoreWalls@refs/heads/master/snippets/nodes_TW.meta.yml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@refs/heads/main/trial.yaml"
    ]

    all_nodes = []
    for url in sources:
        log(f"尝试加载节点源: {url}")
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = yaml.safe_load(resp.text)
                nodes = data.get("proxies", [])
                filtered_nodes = [node for node in nodes if node.get("type", "").lower() != "ssr"]
                all_nodes.extend(filtered_nodes)
                log(f"✅ 加载 {len(nodes)} 节点（过滤后 {len(filtered_nodes)}）: {url}")
                protocols = {}
                for node in filtered_nodes:
                    proto = node.get("type", "unknown").lower()
                    protocols[proto] = protocols.get(proto, 0) + 1
                log(f"协议分布: {protocols}")
                break
            except Exception as e:
                log(f"❌ 加载失败 (尝试 {attempt + 1}/3): {url} {str(e)}")
                if attempt == 2:
                    log(f"❌ 放弃加载: {url}")
                time.sleep(2)

    if not all_nodes:
        log("❌ 未加载到任何节点")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("nodes.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"proxies": []}, f, default_flow_style=False, allow_unicode=True)
        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write(f"最后更新: {timestamp}\n无有效节点\n")
        return

    seen = set()
    unique_nodes = []
    for node in all_nodes:
        key = f"{node['type']}-{node['server']}:{node['port']}"
        if key not in seen:
            seen.add(key)
            unique_nodes.append(node)
    log(f"🔍 去重后: {len(unique_nodes)} 节点")

    unique_nodes = unique_nodes[:MAX_NODES]
    log(f"🔍 限制测试: {len(unique_nodes)} 节点")

    valid_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(test_proxy, node): node for node in unique_nodes}
        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            try:
                result = future.result()
                if result:
                    valid_results.append({"node": node, "latency": result})
            except Exception as e:
                log(f"⚠️ 测试异常: {node.get('name')} {str(e)}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if valid_results:
        sorted_nodes = sorted(valid_results, key=lambda x: x["latency"])[:50]
        with open("nodes.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"proxies": [n["node"] for n in sorted_nodes]}, f, default_flow_style=False, allow_unicode=True)
        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write(f"最后更新: {timestamp}\n节点总数: {len(sorted_nodes)}\n\n")
            for idx, item in enumerate(sorted_nodes, 1):
                node = item["node"]
                f.write(f"{idx:2d}. {node['name']} ({node['type'].upper()})\n    服务器: {node['server']}:{node['port']}\n    延迟: {item['latency']:.2f}ms\n\n")
        log(f"🎉 生成 {len(sorted_nodes)} 有效节点")
    else:
        log("❌ 无有效节点")
        with open("nodes.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"proxies": []}, f, default_flow_style=False, allow_unicode=True)
        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write(f"最后更新: {timestamp}\n无有效节点\n")

if __name__ == "__main__":
    main()