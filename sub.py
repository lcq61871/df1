import requests
import yaml
import subprocess
import httpx
import asyncio
import time
import json
import os
from typing import List, Tuple

URLS = [
    "https://raw.githubusercontent.com/mfbpn/tg_mfbpn_sub/refs/heads/main/trial.yaml",
    "https://raw.githubusercontent.com/lcq61871/NoMoreWalls/refs/heads/master/snippets/nodes.meta.yml"
]

TOP_N = 50
PROXY_ADDR = "127.0.0.1"
PROXY_PORT = 2080
SINGBOX_BIN = "./sing-box"
CONFIG_FILE = "singbox_config.json"
TEST_URL = "https://www.google.com/generate_204"
TIMEOUT = 10

# 删除旧文件
def cleanup():
    for file in ["nodes.yml", "speed.txt", CONFIG_FILE]:
        if os.path.exists(file):
            os.remove(file)
            print(f"🗑️ Removed old {file}")

def fetch_yaml(url: str):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return yaml.safe_load(r.text)
    except Exception as e:
        print(f"❌ Failed to fetch {url} -> {e}")
        return {}

def extract_proxies(yaml_dict: dict):
    return yaml_dict.get("proxies", [])

def generate_singbox_config(proxies: List[dict]):
    outbounds = []
    for idx, proxy in enumerate(proxies):
        proxy_type = proxy.get("type")
        tag = f"node_{idx}"
        config = {
            "type": proxy_type,
            "tag": tag,
            "server": proxy.get("server"),
            "port": proxy.get("port"),
            "uuid": proxy.get("uuid"),
            "alterId": proxy.get("alterId", 0),
            "cipher": proxy.get("cipher", "auto"),
            "password": proxy.get("password"),
            "tls": proxy.get("tls", False),
            "network": proxy.get("network", "tcp"),
            "sni": proxy.get("sni"),
            "skip-cert-verify": True,
            "username": proxy.get("username"),
            "plugin": proxy.get("plugin"),
            "plugin-opts": proxy.get("plugin-opts")
        }
        config = {k: v for k, v in config.items() if v is not None}
        outbounds.append(config)

    config = {
        "log": {"level": "error"},
        "dns": {"servers": ["https://8.8.8.8/dns-query"]},
        "outbounds": [
            {
                "type": "selector",
                "tag": "auto",
                "outbounds": [f"node_{i}" for i in range(len(proxies))]
            },
            *outbounds
        ],
        "inbounds": [{
            "type": "http",
            "listen": PROXY_ADDR,
            "listen_port": PROXY_PORT,
            "tag": "http-in"
        }],
        "route": {
            "rules": [{"inbound": ["http-in"], "outbound": "auto"}]
        }
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def start_singbox():
    return subprocess.Popen([SINGBOX_BIN, "run", "-c", CONFIG_FILE])

async def test_speed(name: str):
    proxy = f"http://{PROXY_ADDR}:{PROXY_PORT}"
    try:
        start = time.time()
        async with httpx.AsyncClient(proxies=proxy, timeout=TIMEOUT) as client:
            r = await client.get(TEST_URL)
            if r.status_code == 204:
                delay = round((time.time() - start) * 1000, 2)
                print(f"[✓] {name}: {delay} ms")
                return name, delay
    except:
        pass
    print(f"[✗] {name}: Failed")
    return name, None

async def run_speed_tests(names: List[str]):
    tasks = [test_speed(name) for name in names]
    results = await asyncio.gather(*tasks)
    return results

def main():
    cleanup()
    all_proxies = []
    for url in URLS:
        y = fetch_yaml(url)
        all_proxies += extract_proxies(y)

    print(f"Fetched {len(all_proxies)} nodes")
    if not all_proxies:
        print("❌ No nodes fetched. Exiting.")
        return

    generate_singbox_config(all_proxies)
    singbox = start_singbox()
    time.sleep(3)  # wait for sing-box to start

    node_names = [p.get("name", f"node_{i}") for i, p in enumerate(all_proxies)]
    speeds = asyncio.run(run_speed_tests(node_names))

    singbox.terminate()
    singbox.wait()
    os.remove(CONFIG_FILE)

    # 配对节点与测速
    results = []
    for i, (name, delay) in enumerate(speeds):
        if delay:
            results.append((all_proxies[i], delay))

    results.sort(key=lambda x: x[1])
    top = results[:TOP_N]

    with open("nodes.yml", "w", encoding="utf-8") as f:
        yaml.dump({"proxies": [r[0] for r in top]}, f, allow_unicode=True)

    with open("speed.txt", "w", encoding="utf-8") as f:
        for item in top:
            name = item[0].get("name", "unknown")
            delay = item[1]
            f.write(f"{name}: {delay} ms\n")

    print(f"\n✅ Done! {len(top)} fastest nodes saved to nodes.yml and speed.txt")

if __name__ == "__main__":
    main()
