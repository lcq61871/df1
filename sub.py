import os
import subprocess
import requests
import time
import yaml
import asyncio
import httpx

SUB_URLS = [
    "https://raw.githubusercontent.com/lcq61871/NoMoreWalls/refs/heads/master/snippets/nodes_IEPL.meta.yml",
    "https://raw.githubusercontent.com/lcq61871/NoMoreWalls/refs/heads/master/snippets/nodes_TW.meta.yml"
]

CLASH_CONFIG = "clash_config.yaml"
CLASH_BIN = "./mihomo"
PROXY = "http://127.0.0.1:7890"
TEST_URL = "https://www.google.com/generate_204"
TIMEOUT = 10
TOP_N = 50

def merge_yaml_subs(urls):
    all_nodes = []
    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            data = yaml.safe_load(r.text)
            if "proxies" in data:
                all_nodes.extend(data["proxies"])
        except Exception as e:
            print(f"❌ Failed to fetch {url}: {e}")
    return all_nodes

def write_clash_config(proxies):
    config = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "silent",
        "proxies": proxies,
        "proxy-groups": [{
            "name": "auto",
            "type": "url-test",
            "url": TEST_URL,
            "interval": 300,
            "proxies": [p["name"] for p in proxies]
        }],
        "rules": ["MATCH,auto"]
    }
    with open(CLASH_CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

def start_clash():
    return subprocess.Popen([CLASH_BIN, "-f", CLASH_CONFIG])

async def test_speed(name):
    proxy = PROXY
    headers = {"Proxy-Connection": "keep-alive"}
    try:
        start = time.time()
        async with httpx.AsyncClient(proxies=proxy, timeout=TIMEOUT, headers=headers) as client:
            r = await client.get(TEST_URL)
            if r.status_code == 204:
                delay = round((time.time() - start) * 1000, 2)
                print(f"[✓] {name}: {delay} ms")
                return name, delay
    except:
        pass
    print(f"[✗] {name}: Failed")
    return name, None

async def run_tests(names):
    return await asyncio.gather(*[test_speed(name) for name in names])

def cleanup():
    for f in ["nodes.yml", "speed.txt", CLASH_CONFIG]:
        if os.path.exists(f):
            os.remove(f)

def main():
    cleanup()
    proxies = merge_yaml_subs(SUB_URLS)
    print(f"✅ Total fetched: {len(proxies)} nodes")

    if not proxies:
        print("❌ No nodes fetched. Exiting.")
        return

    write_clash_config(proxies)
    clash = start_clash()
    print("🚀 Clash.meta started, wait 5s...")
    time.sleep(5)

    names = [p["name"] for p in proxies]
    results = asyncio.run(run_tests(names))

    clash.terminate()
    clash.wait()

    valid = []
    for i, (name, delay) in enumerate(results):
        if delay is not None:
            valid.append((proxies[i], delay))

    valid.sort(key=lambda x: x[1])
    top = valid[:TOP_N]

    with open("nodes.yml", "w", encoding="utf-8") as f:
        yaml.dump({"proxies": [item[0] for item in top]}, f, allow_unicode=True)

    with open("speed.txt", "w", encoding="utf-8") as f:
        for item in top:
            f.write(f"{item[0]['name']}: {item[1]} ms\n")

    print(f"\n🎉 Done! Saved {len(top)} nodes to nodes.yml and speed.txt")

if __name__ == "__main__":
    main()
