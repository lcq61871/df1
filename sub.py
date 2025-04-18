import os
import subprocess
import requests
import time
import yaml
import asyncio
import httpx

SUB_URLS = [
    "https://raw.githubusercontent.com/mfbpn/tg_mfbpn_sub/refs/heads/main/trial.yaml"
]

CLASH_CONFIG = "clash_config.yaml"
CLASH_BIN = "./clash-meta"
PROXY = "http://127.0.0.1:7890"
TEST_URLS = ["http://httpbin.org/status/200", "http://ipinfo.io/json", "http://1.1.1.1"]  # 备用测试 URL
TIMEOUT = 40
TOP_N = 50

def merge_yaml_subs(urls):
    all_nodes = []
    for url in urls:
        try:
            print(f"正在获取 {url}...")
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = yaml.safe_load(r.text)
            if "proxies" in data and data["proxies"]:
                print(f"在 {url} 中找到 {len(data['proxies'])} 个代理")
                all_nodes.extend(data["proxies"])
            else:
                print(f"⚠️ {url} 中没有找到代理")
        except Exception as e:
            print(f"❌ 获取 {url} 失败: {e}")
    return all_nodes

def write_clash_config(proxies):
    config = {
        "mixed-port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "debug",
        "external-controller": "127.0.0.1:9090",
        "proxies": proxies,
        "proxy-groups": [{
            "name": "auto",
            "type": "url-test",
            "url": TEST_URLS[0],
            "interval": 300,
            "proxies": [p["name"] for p in proxies]
        }],
        "rules": ["MATCH,auto"]
    }
    with open(CLASH_CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    print(f"已生成 {CLASH_CONFIG}，包含 {len(proxies)} 个代理")

def start_clash():
    with open("clash.log", "w") as log:
        proc = subprocess.Popen([CLASH_BIN, "-f", CLASH_CONFIG], stdout=log, stderr=log)
    print("🚀 Clash.meta 已启动，正在检查状态...")
    for _ in range(20):
        try:
            requests.get("http://127.0.0.1:9090", timeout=2)
            print("✅ Clash.meta 运行正常")
            return proc
        except:
            time.sleep(1)
    print("❌ Clash.meta 启动失败")
    with open("clash.log", "r") as log:
        print("Clash 日志:", log.read())
    proc.terminate()
    return None

async def test_speed(name, test_url):
    headers = {"Proxy-Connection": "keep-alive"}
    print(f"正在测试 {name} 使用 {test_url}...")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            # 设置代理通过 HTTP CONNECT
            r = await client.get(test_url, proxies={"http://": PROXY, "https://": PROXY})
            if r.status_code in [200, 204]:
                delay = round(r.elapsed.total_seconds() * 1000, 2)
                print(f"[✓] {name}: {delay} ms")
                return name, delay
    except Exception as e:
        print(f"[✗] {name}: 测试失败 ({str(e)})")
    return name, None

async def run_tests(names, test_url):
    return await asyncio.gather(*[test_speed(name, test_url) for name in names])

def cleanup():
    for f in ["nodes.yml", "speed.txt", CLASH_CONFIG, "clash.log"]:
        if os.path.exists(f):
            os.remove(f)
    print("已清理旧文件")

def main():
    cleanup()
    proxies = merge_yaml_subs(SUB_URLS)
    print(f"✅ 共获取: {len(proxies)} 个节点")

    if not proxies:
        print("❌ 未获取到节点，退出")
        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write("未获取到节点\n")
        return

    write_clash_config(proxies)
    clash = start_clash()
    if not clash:
        print("❌ Clash.meta 启动失败，中止")
        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write("Clash.meta 启动失败\n")
        return

    names = [p["name"] for p in proxies]
    print(f"正在测试 {len(names)} 个代理...")
    
    valid = []
    for test_url in TEST_URLS:
        print(f"\n使用测试 URL: {test_url}")
        results = asyncio.run(run_tests(names, test_url))
        for i, (name, delay) in enumerate(results):
            if delay is not None:
                valid.append((proxies[i], delay))
        if valid:
            break

    clash.terminate()
    clash.wait()

    print(f"找到 {len(valid)} 个有效节点")
    valid.sort(key=lambda x: x[1])
    top = valid[:TOP_N]

    if not top:
        print("❌ 未找到有效节点")
        with open("speed.txt", "w", encoding="utf-8") as f:
            f.write("未找到有效节点\n")
        return

    with open("nodes.yml", "w", encoding="utf-8") as f:
        yaml.dump({"proxies": [item[0] for item in top]}, f, allow_unicode=True)

    with open("speed.txt", "w", encoding="utf-8") as f:
        for item in top:
            f.write(f"{item[0]['name']}: {item[1]} ms\n")

    print(f"\n🎉 完成！保存了 {len(top)} 个节点到 nodes.yml 和 speed.txt")

if __name__ == "__main__":
    main()
