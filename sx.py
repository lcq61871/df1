import requests
import re
import os
from collections import defaultdict
import concurrent.futures

# ===== 参数配置 =====
target_channels = [
    'CCTV1', 'CCTV2 财经[1920x1080]', 'CCTV13',
    'CCTV世界地理[1920x1080]', 'CCTV央视文化精品[1920x1080]',
    '湖南卫视[1920x1080]', '湖南都市', '深圳都市',
    'EYETV 旅游', '亞洲旅遊', '美食星球',
    '亚洲武侠', 'Now爆谷台', 'Now星影台',
    '龍祥', 'Sun TV HD', 'SUN MUSIC', 'FASHION TV',
    'Playboy Plus', '欧美艺术', '美国家庭'
]
exclude_keywords = ['chinamobile', 'tvgslb', '购物', '理财']
timeout = 5
max_workers = 20

# ===== 删除旧文件 =====
if os.path.exists('filtered_streams.txt'):
    os.remove('filtered_streams.txt')
    print("已删除旧的 filtered_streams.txt 文件")

# ===== 收集源数据 =====
all_lines = []

# 本地文件
try:
    with open('iptv_list.txt', 'r', encoding='utf-8') as f:
        all_lines.extend(f.readlines())
    print("读取本地 iptv_list.txt 完成")
except FileNotFoundError:
    print("本地 iptv_list.txt 未找到")

# 远程源列表
remote_urls = [
    'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt',
    'https://raw.githubusercontent.com/80947108/888/6253b4e896ca08dc0ef16f9cf64f182d9d4116e6/tv/FGlive.m3u',
    'https://raw.githubusercontent.com/kkllllkkkk/kkllllkkkk.github.io/refs/heads/main/1.txt',
    'https://raw.githubusercontent.com/chiang1102/a/refs/heads/main/test1.txt',
    'https://live.iptv365.org/live.txt',
    'https://freetv.fun/test_channels_taiwan.m3u',
    'https://tv.iill.top/m3u/Gather',
    'https://gcore.jsdelivr.net/gh/Guovin/iptv-api@gd/output/result.m3u',
    'http://ttkx.cc:55/lib/kx2024.txt',
    'https://raw.githubusercontent.com/quninainaixi/quninainaixi/refs/heads/main/DSJ2024417.txt',
    'https://raw.githubusercontent.com/sqspot/tac/refs/heads/main/173.txt',
    'https://raw.githubusercontent.com/sqspot/tac/refs/heads/main/167.txt',
    'https://raw.githubusercontent.com/sqspot/tac/refs/heads/main/108.txt',
    'https://raw.githubusercontent.com/lcq61871/df1/refs/heads/main/iptv_list.txt',
    'https://raw.githubusercontent.com/lcq61871/iptvz/refs/heads/main/maotv.txt'
]

# 解析远程内容
for url in remote_urls:
    try:
        print(f"获取中: {url}")
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            print(f"请求失败 {r.status_code}")
            continue
        lines = r.text.splitlines()
        if url.endswith('.m3u'):
            for i in range(len(lines) - 1):
                if lines[i].startswith('#EXTINF') and lines[i + 1].startswith('http'):
                    match = re.search(r',(.+)', lines[i])
                    if match:
                        all_lines.append(f"{match.group(1).strip()} {lines[i + 1].strip()}")
        else:
            for line in lines[2:]:  # skip header
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) == 2:
                        channel, stream = parts
                        all_lines.append(f"{channel.strip()} {stream.strip()}")
    except Exception as e:
        print(f"获取失败: {e}")

print(f"总共获取 {len(all_lines)} 条原始频道数据")

# ===== 匹配筛选 + 合并 =====
target_set = set(name.lower() for name in target_channels)
grouped_streams = defaultdict(set)

for line in all_lines:
    line = line.strip()
    if not line or 'http' not in line:
        continue

    match = re.match(r'(.+?)\s+(https?://\S+)', line)
    if not match:
        continue

    channel_name = match.group(1).strip()
    stream_url = match.group(2).strip()

    if (
        channel_name.lower() in target_set and
        not any(keyword in channel_name for keyword in exclude_keywords)
    ):
        grouped_streams[channel_name].add(stream_url)

import time

# ===== 并发测速并筛选最快的节目源 =====
def test_stream_speed(url, timeout=10):
    try:
        start = time.time()
        response = requests.get(url, timeout=timeout, stream=True)
        if response.status_code == 200:
            end = time.time()
            return url, end - start
    except:
        pass
    return url, float('inf')

def get_fastest_urls(urls, top_n=5):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(test_stream_speed, url, timeout): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url, duration = future.result()
            if duration != float('inf'):
                results.append((url, duration))
    # 排序保留前 N 个速度最快的链接
    results.sort(key=lambda x: x[1])
    return [url for url, _ in results[:top_n]]


# ===== 过滤掉无效节目源地址 =====
final_streams = defaultdict(list)

for channel, urls in grouped_streams.items():
    print(f"验证 {channel} 的 {len(urls)} 个链接...")
    valid_urls = filter_valid_urls(urls)
    final_streams[channel].extend(valid_urls)

# ===== 写入文件 =====
count = 0
with open('filtered_streams.txt', 'w', encoding='utf-8') as f:
    f.write("abc频道,#genre#\n")
    for channel, urls in sorted(final_streams.items()):
        for url in urls:
            f.write(f"{channel}, {url}\n")
            count += 1

print(f"写入完成，保留有效频道 {len(final_streams)} 个，共 {count} 条链接")
