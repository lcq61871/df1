import requests
import re
import os
from collections import defaultdict

# 需要保留的频道关键词（精确匹配）
target_channels = [
    'CCTV1', 'CCTV2', 'CCTV13',
    'CCTV世界地理[1920x1080]',
    'CCTV央视文化精品[1920x1080]',
    'CCTV高尔夫·网球[1920x1080]',
    'CCTV风云足球[1920x1080]',
    '湖南都市', '湖南卫视', 'TVB星河台'
]

# 要排除的关键词（模糊匹配）
exclude_keywords = ['chinamobile', 'tvgslb', '购物', '理财']

# 保存所有 IPTV 数据行
all_lines = []

# 删除旧的 filtered_streams.txt 文件
output_file = 'filtered_streams.txt'
if os.path.exists(output_file):
    os.remove(output_file)
    print("已删除旧的 filtered_streams.txt 文件")

# 读取本地文件
try:
    with open('iptv_list.txt', 'r', encoding='utf-8') as f:
        all_lines.extend(f.readlines())
    print("成功读取本地 iptv_list.txt 文件")
except FileNotFoundError:
    print("本地 iptv_list.txt 文件未找到，将仅使用远程源")

# 远程源列表
urls = [
    'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt',
    'https://raw.githubusercontent.com/lcq61871/iptvz/refs/heads/main/live_ipv4.txt'
]

# 获取远程源数据
for url in urls:
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            all_lines.extend(response.text.splitlines())
            print(f"成功获取远程源: {url}，数据行数：{len(response.text.splitlines())}")
        else:
            print(f"远程源访问失败: {url} - 状态码: {response.status_code}")
    except Exception as e:
        print(f"获取远程源失败 {url}: {e}")

# 显示获取到的所有数据行数
print(f"总共获取到 {len(all_lines)} 行数据")

# 精确匹配目标频道
target_set = set(name.lower() for name in target_channels)
target_streams = defaultdict(list)

for line in all_lines:
    line = line.strip()
    if not line or 'http' not in line:
        continue

    # 使用正则匹配频道名称和 URL
    match = re.match(r'(.+?)\s+(https?://\S+)', line)
    if not match:
        continue

    channel_name = match.group(1).strip()
    stream_url = match.group(2).strip()

    # 筛选匹配的频道
    if (
        channel_name.lower() in target_set and
        not any(bad in channel_name for bad in exclude_keywords)
    ):
        target_streams[channel_name].append(stream_url)

# 显示匹配到的频道数量
print(f"匹配到 {len(target_streams)} 个频道")

# 写入输出文件
if target_streams:
    with open(output_file, 'w', encoding='utf-8') as out_file:
        out_file.write("abc频道,#genre#\n")
        # 遍历并按频道名称写入所有匹配的流
        for channel, urls in target_streams.items():
            for url in urls:
                out_file.write(f"{channel}, {url}\n")
    print(f"筛选完成，已写入 {output_file}")
else:
    print("未找到符合条件的频道")
