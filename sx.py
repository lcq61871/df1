import requests
import re
import os
from collections import defaultdict

# 读取 moban.txt 文件中的需要保留的频道关键词
def load_target_channels(moban_file):
    target_channels = []
    try:
        with open(moban_file, 'r', encoding='utf-8') as f:
            target_channels = [line.strip() for line in f.readlines() if line.strip()]
        print(f"成功从 {moban_file} 文件读取 {len(target_channels)} 个频道关键词")
    except FileNotFoundError:
        print(f"文件 {moban_file} 未找到，请检查路径和文件名")
    return target_channels

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
    print("成功读取本地 iptv_list.txt 文件，数据行数：", len(all_lines))
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

# 加载 moban.txt 文件并获取频道关键词
target_channels = load_target_channels('moban.txt')

# 如果没有从 moban.txt 获取到关键词，则退出
if not target_channels:
    print("没有从 moban.txt 文件获取到需要保留的频道关键词。程序终止。")
    exit()

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

    if (
        channel_name.lower() in target_set and
        not any(keyword in channel_name for keyword in exclude_keywords)
    ):
        grouped_streams[channel_name].append(stream_url)

# 写入输出文件
if grouped_streams:
    with open(output_file, 'w', encoding='utf-8') as out_file:
        out_file.write("abc频道,#genre#\n")
        # 遍历并按频道名称写入所有匹配的流
        for channel in sorted(grouped_streams.keys()):
            for url in grouped_streams[channel]:
                out_file.write(f"{channel}, {url}\n")
    print(f"筛选完成，已写入 {output_file}")
else:
    print("未找到符合条件的频道")
