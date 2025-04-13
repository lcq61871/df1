import os
import requests
import re
from collections import defaultdict

# 运行前删除旧的输出文件
output_file = 'filtered_streams.txt'
if os.path.exists(output_file):
    os.remove(output_file)

# 精确匹配频道列表（不区分大小写）
target_channels = [
    'CCTV1', 'CCTV2', 'CCTV13',
    'CCTV世界地理[1920x1080]',
    'CCTV央视文化精品[1920x1080]',
    'CCTV高尔夫·网球[1920x1080]',
    'CCTV风云足球[1920x1080]',
    '湖南都市', '湖南卫视', 'TVB星河台'
]

# 排除关键词（模糊匹配）
exclude_keywords = ['chinamobile', 'tvgslb', '购物', '理财']

# 保存所有 IPTV 行
all_lines = []

# 读取本地 iptv_list.txt 文件
try:
    with open('iptv_list.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        all_lines.extend([line.strip() for line in lines if line.strip()])
        print(f"读取本地 iptv_list.txt，共 {len(lines)} 行")
except FileNotFoundError:
    print("本地 iptv_list.txt 文件未找到，将跳过本地内容")

# 远程源（m3u 格式）
remote_urls = [
    'https://raw.githubusercontent.com/80947108/888/6253b4e896ca08dc0ef16f9cf64f182d9d4116e6/tv/FGlive.m3u',
    'https://raw.githubusercontent.com/peterHchina/iptv/refs/heads/main/CCTV-V4.m3u',
    'https://raw.githubusercontent.com/ngdikman/hksar/refs/heads/main/GDIPTV.m3u',
    'https://raw.githubusercontent.com/alenin-zhang/IPTV/refs/heads/main/LITV.txt'
]

for url in remote_urls:
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            lines = response.text.splitlines()
            for i in range(len(lines) - 1):
                if lines[i].startswith('#EXTINF') and lines[i + 1].startswith('http'):
                    match = re.search(r',(.+)', lines[i])
                    if match:
                        channel = match.group(1).strip()
                        stream = lines[i + 1].strip()
                        all_lines.append(f'{channel} {stream}')
            print(f"获取远程源成功: {url} 共采集行数: {len(lines)}")
        else:
            print(f"远程源访问失败 {url}: 状态码 {response.status_code}")
    except Exception as e:
        print(f"获取远程源失败 {url}: {e}")

# 频道归类容器
channel_map = defaultdict(list)
target_set = set(name.lower() for name in target_channels)

# 筛选与归类
for line in all_lines:
    match = re.match(r'(.+?)\s+(https?://\S+)', line)
    if not match:
        continue
    channel_name = match.group(1).strip()
    stream_url = match.group(2).strip()
    if (
        channel_name.lower() in target_set and
        not any(ex in channel_name for ex in exclude_keywords)
    ):
        channel_map[channel_name].append(stream_url)

# 写入输出文件
if channel_map:
    with open(output_file, 'w', encoding='utf-8') as f:
        for channel, urls in channel_map.items():
            f.write(f"{channel},#genre#\n")
            for url in urls:
                f.write(f"{channel},{url}\n")
    print(f"共匹配到 {len(channel_map)} 个频道，结果已写入 {output_file}")
else:
    print("未匹配到任何频道")
