import requests
import re
import os
from collections import defaultdict

# 需要保留的频道关键词（精确匹配）
target_channels = [
    'CCTV1', 'CCTV2', 'CCTV13',
    'CCTV世界地理[1920x1080]',
    'CCTV央视文化精品[1920x1080]',
    '湖南卫视', '湖南都市', '深圳都市',
    'EYETV 旅游', '亞洲旅遊', '美食星球',
    '亚洲武侠', 'Now爆谷台', 'Now星影台',
    '亚洲武侠', 'Now爆谷台', '龍祥',
    'Sun TV HD', 'SUN MUSIC', 'FASHION TV',
    'Playboy Plus', '欧美艺术', '美国家庭'
]

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
    'https://raw.githubusercontent.com/lcq61871/df1/refs/heads/main/iptv_list.txt',
    'https://raw.githubusercontent.com/lcq61871/iptvz/refs/heads/main/maotv.txt',
    'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt',
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

    # 调试输出
    print(f"处理频道: {channel_name}, {stream_url}")

    # 检查频道名称是否符合要求
    if channel_name.lower() in target_set:
        # 排除包含特定关键词的频道
        if any(keyword in channel_name for keyword in exclude_keywords):
            print(f"排除频道: {channel_name}, 包含排除关键词")
        else:
            grouped_streams[channel_name].append(stream_url)
    else:
        print(f"不符合条件的频道: {channel_name}")

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
