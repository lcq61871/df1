import requests
import re

# 需要保留的频道关键词
target_channels = ['CCTV1', 'CCTV2', 'CCTV13', 'CCTV世界地理[1920x1080]', 'CCTV央视文化精品[1920x1080]', 'CCTV高尔夫·网球[1920x1080]', 'CCTV风云足球[1920x1080]', '湖南都市''湖南卫视', '甘肃卫视']
print(f"Target channels: {target_channels}")

# 要排除的关键词
exclude_keywords = ['chinamobile', 'tvgslb', '购物', '理财']

# 保存所有的 IPTV 数据行
all_lines = []

# 读取本地文件
with open('iptv_list.txt', 'r', encoding='utf-8') as f:
    all_lines.extend(f.readlines())

# 远程源 1（luoye）
url1 = 'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt'
try:
    response1 = requests.get(url1, timeout=10)
    if response1.status_code == 200:
        all_lines.extend(response1.text.splitlines())
except Exception as e:
    print(f"获取 {url1} 失败: {e}")

# 远程源 2（CCTV-V4.m3u 格式为 M3U，需要解析）
url2 = 'https://raw.githubusercontent.com/peterHchina/iptv/refs/heads/main/CCTV-V4.m3u'
try:
    response2 = requests.get(url2, timeout=10)
    if response2.status_code == 200:
        m3u_lines = response2.text.splitlines()
        # 提取频道名和链接，假设格式：#EXTINF:-1,频道名 \n http链接
        for i in range(0, len(m3u_lines), 2):
            if m3u_lines[i].startswith('#EXTINF') and (i + 1 < len(m3u_lines)):
                match = re.search(r',(.+)', m3u_lines[i])
                if match:
                    channel = match.group(1).strip()
                    url = m3u_lines[i + 1].strip()
                    all_lines.append(f'{channel} {url}')
except Exception as e:
    print(f"获取 {url2} 失败: {e}")

# 筛选目标频道
target_streams = []

for line in all_lines:
    parts = line.strip().split(' ', 1)
    if len(parts) == 2:
        channel_name, stream_url = parts
        if (
            any(name.lower() in channel_name.lower() for name in target_channels) and
            not any(bad in channel_name for bad in exclude_keywords)
        ):
            target_streams.append(f"{channel_name}, {stream_url}")

# 写入结果
if target_streams:
    with open('filtered_streams.txt', 'w', encoding='utf-8') as out_file:
        out_file.write("abc频道,#genre#\n")
        out_file.write("\n".join(target_streams))
    print("筛选完成，已写入 filtered_streams.txt")
else:
    print("未找到符合条件的频道")
