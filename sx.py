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
except FileNotFoundError:
    print("本地 iptv_list.txt 文件未找到，将仅使用远程源")

# 远程源 1
url1 = 'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt'
try:
    response1 = requests.get(url1, timeout=10)
    if response1.status_code == 200:
        all_lines.extend(response1.text.splitlines())
    else:
        print(f"从 {url1} 获取数据失败, 状态码: {response1.status_code}")
except Exception as e:
    print(f"获取 {url1} 失败: {e}")

# 新增的远程源 3
url3 = 'https://raw.githubusercontent.com/alenin-zhang/IPTV/refs/heads/main/LITV.txt'
try:
    response3 = requests.get(url3, timeout=10)
    if response3.status_code == 200:
        all_lines.extend(response3.text.splitlines())
        print(f"从 {url3} 获取数据成功, 状态码: {response3.status_code}")
    else:
        print(f"从 {url3} 获取数据失败, 状态码: {response3.status_code}")
except Exception as e:
    print(f"获取 {url3} 失败: {e}")

# 进行精确匹配过滤
target_set = set(name.lower() for name in target_channels)
target_streams = []

print("开始筛选符合条件的频道...")

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
        not any(bad in channel_name for bad in exclude_keywords)
    ):
        print(f"匹配到频道: {channel_name}, URL: {stream_url}")  # 打印匹配的频道信息
        target_streams.append(f"{channel_name}, {stream_url}")

if target_streams:
    try:
        with open('filtered_streams.txt', 'w', encoding='utf-8') as out_file:
            out_file.write("abc频道,#genre#\n")
            out_file.write("\n".join(target_streams))
        print("筛选完成，已写入 filtered_streams.txt")
    except Exception as e:
        print(f"写入 filtered_streams.txt 失败: {e}")
else:
    print("未找到符合条件的频道")
