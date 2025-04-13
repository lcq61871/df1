import requests
import re
import os
from collections import defaultdict

# 需要保留的频道关键词（精确匹配）
try:
    with open('moban.txt', 'r', encoding='utf-8') as f:
        target_channels = [line.strip() for line in f.readlines() if line.strip()]
    print("成功读取 moban.txt 文件")
    print("加载的频道关键词:", target_channels)
except FileNotFoundError:
    print("moban.txt 文件未找到")
    target_channels = []

# 要排除的关键词（模糊匹配）
exclude_keywords = ['chinamobile', 'tvgslb', '购物', '理财']

# 保存所有 IPTV 数据行
all_lines = []

# 删除旧的 filtered_streams.txt 文件
if os.path.exists('filtered_streams.txt'):
    os.remove('filtered_streams.txt')
    print("已删除旧的 filtered_streams.txt 文件")

# 读取本地文件
try:
    with open('iptv_list.txt', 'r', encoding='utf-8') as f:
        all_lines.extend(f.readlines())
    print("成功读取本地 iptv_list.txt 文件")
except FileNotFoundError:
    print("本地 iptv_list.txt 文件未找到，将仅使用远程源")

# 远程源列表
remote_urls = [
    'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt',
    'https://raw.githubusercontent.com/peterHchina/iptv/refs/heads/main/CCTV-V4.m3u',
    'https://raw.githubusercontent.com/ngdikman/hksar/refs/heads/main/GDIPTV.m3u',
    'https://raw.githubusercontent.com/alenin-zhang/IPTV/refs/heads/main/LITV.txt'
]

# 拉取并解析远程源
for url in remote_urls:
    try:
        print(f"正在获取远程数据: {url}")
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            lines = response.text.splitlines()
            for i in range(len(lines) - 1):
                if lines[i].startswith('#EXTINF') and lines[i + 1].startswith('http'):
                    match = re.search(r',(.+)', lines[i])
                    if match:
                        channel = match.group(1).strip()
                        stream_url = lines[i + 1].strip()
                        all_lines.append(f'{channel} {stream_url}')
        else:
            print(f"{url} 获取失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"获取 {url} 失败: {e}")

# 调试：检查所有数据
print(f"总共读取到 {len(all_lines)} 条 IPTV 数据")

# 精确匹配并归类
target_set = set(name.lower() for name in target_channels)
grouped_streams = defaultdict(list)

for line in all_lines:
    line = line.strip()
    if not line or 'http' not in line:
        continue

    match = re.match(r'(.+?)\s+(https?://\S+)', line)
    if not match:
        continue

    channel_name = match.group(1).strip()
    stream_url = match.group(2).strip()

    # 调试：输出每个处理的频道
    print(f"正在处理频道: {channel_name}, URL: {stream_url}")

    # 精确匹配需要保留的频道，并排除不需要的关键词
    if (
        channel_name.lower() in target_set and
        not any(keyword in channel_name for keyword in exclude_keywords)
    ):
        grouped_streams[channel_name].append(stream_url)

# 检查筛选结果
if not grouped_streams:
    print("没有符合条件的频道被筛选出来")

# 写入输出文件
if grouped_streams:
    with open('filtered_streams.txt', 'w', encoding='utf-8') as out_file:
        out_file.write("abc频道,#genre#\n")
        for channel in sorted(grouped_streams.keys()):
            for url in grouped_streams[channel]:
                out_file.write(f"{channel}, {url}\n")
    print("筛选完成，已写入 filtered_streams.txt")
else:
    print("未找到符合条件的频道")
