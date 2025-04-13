# 在 sx.py 脚本中添加调试信息
import os

print("Starting to process IPTV list...")

# 检查文件是否正确打开
try:
    with open('iptv_list.txt', 'r', encoding='utf-8') as file:
        lines = file.readlines()
        print(f"Read {len(lines)} lines from iptv_list.txt")
except Exception as e:
    print(f"Error reading iptv_list.txt: {e}")
    exit(1)

# 定义需要抓取的频道名称
target_channels = ['CCTV1', 'CCTV2', 'CCTV3', '湖南卫视', '甘肃卫视']

# 用来存储目标频道的直播源
target_streams = []

# 遍历文件中的每一行，检查频道是否在目标频道列表中
for line in lines:
    # 假设文件每行的格式是：频道名称 url
    parts = line.strip().split(' ', 1)  # 按空格分割频道名称和URL
    if len(parts) == 2:
        channel_name, stream_url = parts
        # 如果频道名称在目标列表中，则添加到目标直播源列表
        if any(target_channel in channel_name for target_channel in target_channels):
            print(f"Found matching channel: {channel_name}")  # 输出找到的频道
            target_streams.append(f'{channel_name}: {stream_url}')

# 如果找到目标频道，输出到 filtered_streams.txt
output_file = 'filtered_streams.txt'
try:
    if target_streams:
        with open(output_file, 'w', encoding='utf-8') as out_file:
            out_file.write("\n".join(target_streams))
        print(f"筛选完成！已保存到 '{output_file}'")
    else:
        print("没有找到匹配的直播源。")
except Exception as e:
    print(f"Error writing to {output_file}: {e}")
    exit(1)
