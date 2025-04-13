import requests
import re

# 需要保留的频道关键词（精确匹配）
target_channels = [
    'CCTV1', 'CCTV2', 'CCTV13',
    'CCTV世界地理[1920x1080]',
    'CCTV央视文化精品[1920x1080]',
    'CCTV高尔夫·网球[1920x1080]',
    'CCTV风云足球[1920x1080]',
    '湖南都市', '湖南卫视', '甘肃卫视'
]

# 要排除的关键词（模糊匹配）
exclude_keywords = ['chinamobile', 'tvgslb', '购物', '理财']

# 保存所有 IPTV 数据行
all_lines = []

# 读取本地文件
try:
    with open('iptv_list.txt', 'r', encoding='utf-8') as f:
        all_lines.extend(f.readlines())
    print("成功读取本地 iptv_list.txt 文件")
except FileNotFoundError:
    print("本地 iptv_list.txt 文件未找到，将仅使用远程源")

# 远程源 1
url1 = 'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt'
print("正在从远程 URL 1 获取数据...")
try:
    response1 = requests.get(url1, timeout=10)
    if response1.status_code == 200:
        all_lines.extend(response1.text.splitlines())
        print(f"从 {url1} 获取数据成功, 状态码: {response1.status_code}")
    else:
        print(f"从 {url1} 获取数据失败, 状态码: {response1.status_code}")
except Exception as e:
    print(f"获取 {url1} 失败: {e}")

# 远程源 2（M3U 格式）
url2 = 'https://raw.githubusercontent.com/peterHchina/iptv/refs/heads/main/CCTV-V4.m3u'
print("正在从远程 URL 2 获取数据...")
try:
    response2 = requests.get(url2, timeout=10)
    if response2.status_code == 200:
        m3u_lines = response2.text.splitlines()
        for i in range(0, len(m3u_lines) - 1):
            if m3u_lines[i].startswith('#EXTINF') and m3u_lines[i + 1].startswith('http'):
                match = re.search(r',(.+)', m3u_lines[i])
                if match:
                    channel = match.group(1).strip()
                    url = m3u_lines[i + 1].strip()
                    all_lines.append(f'{channel} {url}')
        print(f"从 {url2} 获取数据成功, 状态码: {response2.status_code}")
    else:
        print(f"从 {url2} 获取数据失败, 状态码: {response2.status_code}")
except Exception as e:
    print(f"获取 {url2} 失败: {e}")

# 进行精确匹配过滤
target_set = set(name.lower() for name in target_channels)
target_streams = []

# 调试: 打印所有收集到的行
print(f"共收集到 {len(all_lines)} 行数据，开始进行筛选...")

for line in all_lines:
    line = line.strip()
    if not line or 'http' not in line:
        continue

    match = re.match(r'(.+?)\s+(https?://\S+)', line)
    if not match:
        continue

    channel_name = match.group(1).strip()
    stream_url = match.group(2).strip()

    # 调试: 打印每个匹配到的频道
    print(f"匹配到频道: {channel_name}, URL: {stream_url}")

    if (
        channel_name.lower() in target_set and
        not any(bad in channel_name for bad in exclude_keywords)
    ):
        target_streams.append(f"{channel_name}, {stream_url}")

# 写入输出文件
if target_streams:
    with open('filtered_streams.txt', 'w', encoding='utf-8') as out_file:
        out_file.write("abc频道,#genre#\n")
        out_file.write("\n".join(target_streams))
    print("筛选完成，已写入 filtered_streams.txt")
else:
    print("未找到符合条件的频道")
