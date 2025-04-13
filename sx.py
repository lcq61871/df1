import os
import requests

# 打印当前工作目录，确保路径正确
print(f"Current working directory: {os.getcwd()}")

# 从远程 URL 下载 iptv_list.txt 内容
iptv_url = "https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt"
print(f"Downloading iptv_list.txt from {iptv_url}...")

# 下载远程文件内容
try:
    response = requests.get(iptv_url)
    response.raise_for_status()  # 如果请求失败，将抛出异常
    remote_lines = response.text.splitlines()  # 获取文本内容并按行分割
    print(f"Successfully downloaded {len(remote_lines)} lines from the URL")
except requests.exceptions.RequestException as e:
    print(f"Error downloading iptv_list.txt from URL: {e}")
    remote_lines = []  # 如果下载失败，使用空列表

# 尝试读取本地的 iptv_list.txt 文件
local_lines = []
if os.path.isfile('iptv_list.txt'):
    print("Reading local iptv_list.txt...")
    try:
        with open('iptv_list.txt', 'r', encoding='utf-8') as file:
            local_lines = file.readlines()
        print(f"Read {len(local_lines)} lines from the local file")
    except Exception as e:
        print(f"Error reading local iptv_list.txt: {e}")
else:
    print("Local iptv_list.txt file not found!")

# 合并本地和远程的内容
lines = local_lines + remote_lines

# 定义需要抓取的频道名称
target_channels = ['CCTV1', 'CCTV2', 'CCTV13', 'CCTV世界地理[1920x1080]', 'CCTV央视文化精品[1920x1080]', 'CCTV高尔夫·网球[1920x1080]', 'CCTV风云足球[1920x1080]', '湖南都市''湖南卫视', '甘肃卫视']
print(f"Target channels: {target_channels}")

# 用来存储目标频道的直播源
target_streams = []

# 遍历文件中的每一行，检查频道是否在目标频道列表中
for line in lines:
    # 跳过包含 #genre# 或其他无效信息的行
    if '#genre#' in line or ',' not in line:
        print(f"Skipping invalid line: {line.strip()}")  # 输出跳过的行
        continue

    print(f"Processing line: {line.strip()}")  # 打印每行内容，查看格式
    parts = line.strip().split(',', 1)  # 按逗号分割频道名称和URL
    if len(parts) == 2:
        channel_name, stream_url = parts
        # 使用完全匹配来检查频道名称是否在目标列表中
        if channel_name in target_channels:
            print(f"Found matching channel: {channel_name}")  # 输出找到的频道
            # 改成逗号格式
            target_streams.append(f'{channel_name}, {stream_url}')
        else:
            print(f"No match for: {channel_name}")  # 输出未匹配的频道
    else:
        print(f"Invalid line format, skipping: {line.strip()}")

# 如果找到目标频道，输出到 filtered_streams.txt
output_file = 'filtered_streams.txt'
try:
    if target_streams:
        # 在文件开头加上 "abc频道,#genre#"
        with open(output_file, 'w', encoding='utf-8') as out_file:
            out_file.write("abc频道,#genre#\n")  # 添加头部信息
            out_file.write("\n".join(target_streams))  # 写入目标频道数据
        print(f"筛选完成！已保存到 '{output_file}'")
    else:
        print("没有找到匹配的直播源。")
except Exception as e:
    print(f"Error writing to {output_file}: {e}")
    exit(1)
