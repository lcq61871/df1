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
XRAY_BIN = "/usr/local/bin/xray"
HYSTERIA_BIN = "/usr/local/bin/hysteria"

def log(message):
    if DEBUG:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

# ----------------- Xray 配置文件生成 -----------------
def generate_xray_config(node, protocol):
    """生成 Xray 配置文件"""
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "port": 1080,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True}
            }
        ],
        "outbounds": [
            {
                "protocol": protocol,
                "settings": {},
                "tag": "proxy"
            },
            {
                "protocol": "freedom",
                "settings": {},
                "tag": "direct"
            }
        ],
        "routing": {
            "rules": [
                {"type": "field", "outboundTag": "proxy", "domain": ["geosite:google"]}
            ]
        }
    }

    if protocol == "vmess":
        config["outbounds"][0]["settings"] = {
            "vnext": [
                {
                    "address": node["server"],
                    "port": int(node["port"]),
                    "users": [{"id": node["uuid"], "alterId": node.get("alterId", 0)}]
                }
            ]
        }
        if node.get("network") == "ws":
            config["outbounds"][0]["streamSettings"] = {
                "network": "ws",
                "wsSettings": {"path": node.get("ws-opts", {}).get("path", "/")}
            }

    elif protocol == "vless":
        config["outbounds"][0]["settings"] = {
            "vnext": [
                {
                    "address": node["server"],
                    "port": int(node["port"]),
                    "users": [{"id": node["uuid"], "encryption": "none"}]
                }
            ]
        }
        if node.get("network") == "grpc":
            config["outbounds"][0]["streamSettings"] = {
                "network": "grpc",
                "grpcSettings": {"serviceName": node.get("grpc-opts", {}).get("serviceName", "")}
            }

    elif protocol == "trojan":
        config["outbounds"][0]["settings"] = {
            "servers": [
                {
                    "address": node["server"],
                    "port": int(node["port"]),
                    "password": node["password"]
                }
            ]
        }

    elif protocol == "shadowsocks":
        config["outbounds"][0]["settings"] = {
            "servers": [
                {
                    "address": node["server"],
                    "port": int(node["port"]),
                    "method": node["cipher"],
                    "password": node["password"]
                }
            ]
        }

    return config

# ----------------- 协议测试函数 -----------------
def test_with_xray(node, protocol):
    """使用 Xray 测试代理节点"""
    try:
        config = generate_xray_config(node, protocol)
        with NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(config, f, indent=2)
            config_path = f.name

        # 启动 Xray
        xray_proc = subprocess.Popen(
            [XRAY_BIN, "run", "-c", config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # 等待 Xray 启动
        time.sleep(1)

        # 测试连接
        start = time.time()
        cmd = [
            "curl",
            "-sS",
            "--connect-timeout",
            "10",
            "--proxy",
            "socks5h://127.0.0.1:1080",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            TEST_URL
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        latency = (time.time() - start) * 1000  # 毫秒

        # 清理 Xray 进程
        xray_proc.terminate()
        try:
            xray_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            xray_proc.kill()

        # 删除临时配置文件
        os.unlink(config_path)

        if result.stdout.strip() == "204":
            return latency
        return None
    except Exception as e:
        log(f"{protocol.upper()}测试失败 {node.get('name')}: {str(e)}")
        return None

def test_hysteria2(node):
    """测试 Hysteria2 协议"""
    try:
        config = {
            "server": f"{node['server']}:{node['port']}",
            "auth": node.get("password", ""),
            "tls": {"insecure": node.get("allowInsecure", False)}
        }
        with NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(config, f)
            config_path = f.name

        # 启动 Hysteria2
        hysteria_proc = subprocess.Popen(
            [HYSTERIA_BIN, "client", "-c", config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # 等待启动
        time.sleep(1)

        # 测试连接
        start = time.time()
        cmd = [
            "curl",
            "-sS",
            "--connect-timeout",
            "10",
            "--proxy",
            "socks5h://127.0.0.1:1080",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            TEST_URL
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        latency = (time.time() - start) * 1000

        # 清理进程
        hysteria_proc.terminate()
        try:
            hysteria_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            hysteria_proc.kill()

        # 删除临时配置文件
        os.unlink(config_path)

        if result.stdout.strip() == "204":
            return latency
        return None
    except Exception as e:
        log(f"Hysteria2测试失败 {node.get('name')}: {str(e)}")
        return None

def test_proxy(node):
    """协议测试分发器"""
    protocol_handlers = {
        "ss": lambda n: test_with_xray(n, "shadowsocks"),
        "vmess": lambda n: test_with_xray(n, "vmess"),
        "vless": lambda n: test_with_xray(n, "vless"),
        "trojan": lambda n: test_with_xray(n, "trojan"),
        "hysteria2": test_hysteria2,
    }

    proto = node.get("type", "").lower()
    if proto not in protocol_handlers:
        log(f"⚠️ 不支持的协议类型: {proto}")
        return None

    # 必要字段验证
    required_fields = {
        "ss": ["server", "port", "cipher", "password"],
        "vmess": ["server", "port", "uuid"],
        "vless": ["server", "port", "uuid"],
        "trojan": ["server", "port", "password"],
        "hysteria2": ["server", "port", "password"]
    }.get(proto, [])

    if any(field not in node for field in required_fields):
        log(f"❌ 缺失必要字段: {node.get('name')}")
        return None

    return protocol_handlers[proto](node)

# ----------------- 主逻辑 -----------------
def main():
    sources = [
        "https://cdn.jsdelivr.net/gh/0xJins/x.sub@refs/heads/main/trials_providers/TW.yaml",
        "https://cdn.jsdelivr.net/gh/1wyy/tg_mfbpn_sub@refs/heads/main/trial.yaml"
    ]

    all_nodes = []
    for url in sources:
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = yaml.safe_load(resp.text)
            nodes = data.get("proxies", [])
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(test_proxy, node): node for node in unique_nodes}

        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            try:
                result = future.result()
                if result:
                    valid_results.append({"node": node, "latency": result})
            except Exception as e:
                log(f"⚠️ 测试异常 {node.get('name')}: {str(e)}")

    # 生成结果文件
    if valid_results:
        sorted_nodes = sorted(valid_results, key=lambda x: x["latency"])[:50]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open("nodes.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {"proxies": [n["node"] for n in sorted_nodes]},
                f,
                default_flow_style=False,
                allow_unicode=True
            )

        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write(f"最后更新: {timestamp}\n")
            f.write("节点总数: {}\n\n".format(len(sorted_nodes)))
            for idx, item in enumerate(sorted_nodes, 1):
                node = item["node"]
                f.write(
                    f"{idx:2d}. {node['name']} ({node['type'].upper()})\n"
                    f"    服务器: {node['server']}:{node['port']}\n"
                    f"    延迟: {item['latency']:.2f}ms\n\n"
                )

        log(f"🎉 生成 {len(sorted_nodes)} 个有效节点")
    else:
        log("❌ 未找到有效节点")
        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("未找到有效节点\n")

if __name__ == "__main__":
    main()
