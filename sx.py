import requests
import re

# ✅ 保留频道关键词
target_channels = [
    'CCTV1', 'CCTV2', 'CCTV13',
    'CCTV世界地理[1920x1080]',
    'CCTV央视文化精品[1920x1080]',
    'CCTV高尔夫·网球[1920x1080]',
    'CCTV风云足球[1920x1080]',
    '湖南都市', '湖南卫视', '甘肃卫视'
]

# ❌ 要排除的关键词
exclude_keywords = ['chinamobile', 'tvgslb', '购物', '理财']

# 存储所有行
all_lines = []

# ✅ 读取本地文件
try:
    with open('iptv_list.txt', 'r', encoding='utf-8') as f:
        all_lines.extend(f.readlines())
        print(f"已读取本地 iptv_list.txt，共 {len(all_lines)} 行")
except Exception as e:
    print(f"读取本地文件失败: {e}")

# ✅ 远程源 1（luoye）
url1 = 'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt'
try:
    response1 = requests.get(url1, timeout=10)
    if response1.status_code == 200:
        remote_lines1 = response1.text.splitlines()
        all_lines.extend(remote_lines1)
        print(f"已获取远程源1，共 {len(remote_lines1)} 行")
except Exception as e:
    print(f"获取 {url1} 失败: {e}")

# ✅ 远程源 2（M3U 格式）
url2 = 'https://raw.githubusercontent.com/peterHchina/iptv/refs/heads/main/CCTV-V4.m3u'
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
        print(f"已解析远程 M3U，共 {len(m3u_lines)} 行")
except Exception as e:
    print(f"获取 {url2} 失败: {e}")

# ✅ 筛选目标频道
target_streams = []

for line in all_lines:
    line = line.strip()
    if not line or 'http' not in line:
        continue

    match = re.match(r'(.+?)\s+(https?://\S+)', line)
    if not match:
        continue

    channel_name = match.group(1).strip()
    stream_url = match.group(2).strip()

    # 判断是否匹配目标频道，且不包含排除关键词
    if any(name in channel_name for name in target_channels) and not any(bad in channel_name for bad in exclude_keywords):
        target_streams.append(f"{channel_name}, {stream_url}")

# ✅ 写入结果
if target_streams:
    with open('filtered_streams.txt', 'w', encoding='utf-8') as out_file:
        out_file.write("abc频道,#genre#\n")
        out_file.write("\n".join(target_streams))
    print(f"✅ 筛选完成，写入 {len(target_streams)} 条记录到 filtered_streams.txt")
else:
    print("⚠️ 未找到符合条件的频道")
