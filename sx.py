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
    'https://raw.githubusercontent.com/80947108/888/6253b4e896ca08dc0ef16f9cf64f182d9d4116e6/tv/FGlive.m3u',
    'https://raw.githubusercontent.com/peterHchina/iptv/refs/heads/main/CCTV-V4.m3u',
    'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt',
    'https://raw.githubusercontent.com/lcq61871/iptvz/refs/heads/main/maotv.txt'
]

# 拉取并解析远程源
for url in remote_urls:
    try:
        print(f"正在获取远程数据: {url}")
        response = requests.get(url, timeout=10)
        
        # 打印状态码和前几行响应内容
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print("成功获取数据。响应内容预览：")
            print(response.text[:200])  # 打印前200个字符查看响应内容
            
            lines = response.text.splitlines()

            # 判断文件格式（.m3u 文件或 .txt 文件）
            if url.endswith('.m3u'):
                print(f"正在解析 m3u 文件: {url}")
                for i in range(len(lines) - 1):
                    if lines[i].startswith('#EXTINF') and lines[i + 1].startswith('http'):
                        match = re.search(r',(.+)', lines[i])
                        if match:
                            channel = match.group(1).strip()
                            stream_url = lines[i + 1].strip()
                            all_lines.append(f'{channel} {stream_url}')
            elif url.endswith('.txt'):
                print(f"正在解析 txt 文件: {url}")
                # 跳过前两行，解析每一行的频道名称和 URL
                for line in lines[2:]:  # 跳过前两行
                    if ',' in line:
                        parts = line.split(',')
                        if len(parts) == 2:  # 确保每行是频道名和 URL
                            channel, stream_url = parts
                            channel = channel.strip()
                            stream_url = stream_url.strip()
                            all_lines.append(f'{channel} {stream_url}')
            else:
                print(f"不支持的文件格式: {url}")
        else:
            print(f"{url} 获取失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"获取 {url} 失败: {e}")

# 打印获取到的频道信息
print(f"共获取到 {len(all_lines)} 条频道信息")

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
    with open('filtered_streams.txt', 'w', encoding='utf-8') as out_file:
        out_file.write("abc频道,#genre#\n")
        for channel in sorted(grouped_streams.keys()):
            for url in grouped_streams[channel]:
                out_file.write(f"{channel}, {url}\n")
    print("筛选完成，已写入 filtered_streams.txt")
else:
    print("未找到符合条件的频道")
