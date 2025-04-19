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
TIMEOUT = 30  # 超时时间 30 秒
TEST_URLS = [
    "https://www.gstatic.com/generate_204",
    "https://www.google.com/generate_204",
    "http://detectportal.firefox.com/success.txt",
    "http://cp.cloudflare.com/generate_204"
]
XRAY_BIN = "/usr/local/bin/xray"
HYSTERIA_BIN = "/usr/local/bin/hysteria"
MAX_NODES = 100  # 限制测试节点数量

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

        # 尝试多个测试 URL
        for test_url in TEST_URLS:
            try:
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
                    test_url
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
                latency = (time.time() - start) * 1000  # 毫秒

                # 捕获 Xray 日志
                stderr = xray_proc.stderr.read().decode('utf-8', errors='ignore') if xray_proc.stderr else ""
                log(f"{protocol.upper()} 测试 {node.get('name')} (URL={test_url}): HTTP 状态码={result.stdout.strip()}, 延迟={latency:.2f}ms, Xray 日志={stderr}")

                if result.stdout.strip() in ["200", "204", "301"]:  # 放宽状态码
                    # 清理 Xray 进程
                    xray_proc.terminate()
                    try:
                        xray_proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        xray_proc.kill()
                    os.unlink(config_path)
                    return latency
            except subprocess.TimeoutExpired:
                log(f"{protocol.upper()} 测试 {node.get('name')} (URL={test_url}): 连接超时")
                continue
            except Exception as e:
                log(f"{protocol.upper()} 测试 {node.get('name')} (URL={test_url}): 错误={str(e)}")
                continue

        # 清理 Xray 进程
        xray_proc.terminate()
        try:
            xray_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            xray_proc.kill()

        # 删除临时配置文件
        os.unlink(config_path)

        log(f"{protocol.upper()} 测试失败 {node.get('name')}: 所有测试 URL 均未通过")
        return None
    except Exception as e:
        log(f"{protocol.upper()} 测试失败 {node.get('name')}: {str(e)}")
        return None
    finally:
        # 确保进程被杀死
        if 'xray_proc' in locals():
            xray_proc.terminate()
            try:
                xray_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                xray_proc.kill()

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

        # 尝试多个测试 URL
        for test_url in TEST_URLS:
            try:
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
                    test_url
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
                latency = (time.time() - start) * 1000

                # 捕获 Hysteria2 日志
                stderr = hysteria_proc.stderr.read().decode('utf-8', errors='ignore') if hysteria_proc.stderr else ""
                log(f"Hysteria2 测试 {node.get('name')} (URL={test_url}): HTTP 状态码={result.stdout.strip()}, 延迟={latency:.2f}ms, Hysteria2 日志={stderr}")

                if result.stdout.strip() in ["200", "204", "301"]:  # 放宽状态码
                    # 清理进程
                    hysteria_proc.terminate()
                    try:
                        hysteria_proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        hysteria_proc.kill()
                    os.unlink(config_path)
                    return latency
            except subprocess.TimeoutExpired:
                log(f"Hysteria2 测试 {node.get('name')} (URL={test_url}): 连接超时")
                continue
            except Exception as e:
                log(f"Hysteria2 测试 {node.get('name')} (URL={test_url}): 错误={str(e)}")
                continue

        # 清理进程
        hysteria_proc.terminate()
        try:
            hysteria_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            hysteria_proc.kill()

        # 删除临时配置文件
        os.unlink(config_path)

        log(f"Hysteria2 测试失败 {node.get('name')}: 所有测试 URL 均未通过")
        return None
    except Exception as e:
        log(f"Hysteria2 测试失败 {node.get('name')}: {str(e)}")
        return None
    finally:
        # 确保进程被杀死
        if 'hysteria_proc' in locals():
            hysteria_proc.terminate()
            try:
                hysteria_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                hysteria_proc.kill()

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
        "hysteria2": ["server", "port", "password"],
    }.get(proto, [])

    if any(field not in node for field in required_fields):
        log(f"❌ 缺失必要字段: {node.get('name')}，缺失字段: {[field for field in required_fields if field not in node]}")
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
            # 过滤 SSR 节点
            filtered_nodes = [node for node in nodes if node.get("type", "").lower() != "ssr"]
            all_nodes.extend(filtered_nodes)
            log(f"✅ 成功加载 {len(nodes)} 节点（过滤后 {len(filtered_nodes)} 个） from {url}")
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

    # 限制测试节点数量
    unique_nodes = unique_nodes[:MAX_NODES]
    log(f"🔍 限制测试节点数: {len(unique_nodes)}")

    # 并发测试
    valid_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:  # 减少并发
        futures = {executor.submit(test_proxy, node): node for node in unique_nodes}

        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            try:
                result = future.result()
                if result:
                    valid_results.append({"node": node, "latency": result})
                else:
                    log(f"⚠️ 节点 {node.get('name')} 测试未通过")
            except Exception as e:
                log(f"⚠️ 测试异常 {node.get('name')}: {str(e)}")

    # 生成结果文件
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if valid_results:
        sorted_nodes = sorted(valid_results, key=lambda x: x["latency"])[:50]
        
        with open("nodes.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {"proxies": [n["node"] for n in sorted_nodes]},
                f,
                default_flow_style=False,
                allow_unicode=True
            )

        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write(f"最后更新: {timestamp}\n")
            f.write(f"节点总数: {len(sorted_nodes)}\n\n")
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
        with open("nodes.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"proxies": []}, f, default_flow_style=False, allow_unicode=True)
        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write(f"最后更新: {timestamp}\n")
            f.write("未找到有效节点\n")

if __name__ == "__main__":
    main()
