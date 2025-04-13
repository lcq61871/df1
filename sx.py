import os

# 打印当前工作目录，确保路径正确
print(f"Current working directory: {os.getcwd()}")

# 检查 iptv_list.txt 文件是否存在
if not os.path.isfile('iptv_list.txt'):
    print("iptv_list.txt 文件不存在！")
    exit(1)

# 打开 iptv_list.txt 文件并读取内容
print("Reading iptv_list.txt...")
try:
    with open('iptv_list.txt', 'r', encoding='utf-8') as file:
        lines = file.readlines()
    print(f"Read {len(lines)} lines from iptv_list.txt")
except Exception as e:
    print(f"Error reading iptv_list.txt: {e}")
    exit(1)

# 定义需要抓取的频道名称
target_channels = ['CCTV1', 'CCTV2', 'CCTV3', '湖南卫视', '甘肃卫视']
print(f"Target channels: {target_channels}")

# 用来存储目标频道的直播源
target_streams = []

# 遍历文件中的每一行，检查频道是否在目标频道列表中
for line in lines:
    # 跳过包含 #genre# 或更新时间的行
    if '#' in line or ',' not in line:
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
        with open(output_file, 'w', encoding='utf-8') as out_file:
            out_file.write("\n".join(target_streams))
        print(f"筛选完成！已保存到 '{output_file}'")
    else:
        print("没有找到匹配的直播源。")
except Exception as e:
    print(f"Error writing to {output_file}: {e}")
    exit(1)
