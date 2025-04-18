import requests
import yaml
import asyncio
import httpx
import time

SUB_URL = "https://raw.githubusercontent.com/mfbpn/tg_mfbpn_sub/refs/heads/main/trial.yaml"
TEST_URLS = [
    "https://www.google.com/generate_204",
    "https://www.youtube.com",
    "https://www.bing.com",
    "https://www.cloudflare.com",
    "https://www.baidu.com"
]
TIMEOUT = 10
TOP_N = 50

def fetch_nodes(url):
    try:
        r = requests.get(url, timeout=10)
        raw = yaml.safe_load(r.text)
        return raw.get("proxies", [])
    except Exception as e:
        print("❌ 获取订阅失败：", e)
        return []

async def test_node(proxy):
    name = proxy.get("name")
    type_ = proxy.get("type")
    server = proxy.get("server")
    port = proxy.get("port")
    username = proxy.get("username", "")
    password = proxy.get("password", "")

    # 支持类型
    if type_ != "socks5":
        print(f"跳过 {name}: 暂不支持 {type_}")
        return name, None

    # 构建代理
    proxy_url = f"socks5://{server}:{port}"
    if username and password:
        proxy_url = f"socks5://{username}:{password}@{server}:{port}"

    for test_url in TEST_URLS:
        try:
            start = time.time()
            async with httpx.AsyncClient(proxies=proxy_url, timeout=TIMEOUT) as client:
                res = await client.get(test_url)
                if res.status_code in [200, 204]:
                    delay = round((time.time() - start) * 1000, 2)
                    print(f"✅ {name} 可用：{delay} ms [{test_url}]")
                    return name, delay
        except Exception:
            continue

    print(f"❌ {name} 全部连接失败")
    return name, None

async def test_all(proxies):
    return await asyncio.gather(*[test_node(p) for p in proxies])

def save_results(results, proxies):
    usable = [(proxies[i], d) for i, (n, d) in enumerate(results) if d is not None]
    usable.sort(key=lambda x: x[1])
    top = usable[:TOP_N]

    with open("nodes.yml", "w", encoding="utf-8") as f:
        yaml.dump({"proxies": [item[0] for item in top]}, f, allow_unicode=True)

    with open("speed.txt", "w", encoding="utf-8") as f:
        for item in top:
            f.write(f"{item[0]['name']}: {item[1]} ms\n")

    print(f"✅ 筛选完成，可用节点：{len(top)}")

def main():
    proxies = fetch_nodes(SUB_URL)
    if not proxies:
        return print("❌ 无可用节点")
    print(f"🌐 共获取节点：{len(proxies)}")
    results = asyncio.run(test_all(proxies))
    save_results(results, proxies)

if __name__ == "__main__":
    main()
