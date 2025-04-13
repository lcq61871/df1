import requests

# 定义需要抓取的频道名称
target_channels = ['CCTV1', 'CCTV2', 'CCTV13', 'CCTV世界地理[1920x1080]', 'CCTV央视文化精品[1920x1080]', 'CCTV高尔夫·网球[1920x1080]', 'CCTV风云足球[1920x1080]', '湖南都市''湖南卫视', '甘肃卫视']
print(f"Target channels: {target_channels}")

# 定义需要过滤掉的关键词
exclude_keywords = ['chinamobile', 'tvgslb', '购物', '理财']

# 读取本地的 iptv_list.txt 文件
iptv_sources = []

# 读取本地文件
with open('iptv_list.txt', 'r', encoding='utf-8') as file:
    lines = file.readlines()

# 如果需要抓取远程的 IPTV 列表
remote_url = "https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt"
response = requests.get(remote_url)

if response.status_code == 200:
    remote_lines = response.text.splitlines()
else:
    remote_lines = []

# 合并本地和远程的 IPTV 数据
lines.extend(remote_lines)

# 用来存储目标频道的直播源
target_streams = []

# 遍历文件中的每一行，检查频道是否在目标频道列表中并过滤掉不需要的频道
for line in lines:
    parts = line.strip().split(' ', 1)  # 按空格分割频道名称和 URL
    if len(parts) == 2:
        channel_name, stream_url = parts
        # 如果频道名称在目标列表中并且没有包含排除的关键词
        if any(target_channel in channel_name for target_channel in target_channels) and not any(keyword in channel_name for keyword in exclude_keywords):
            target_streams.append(f'{channel_name}, {stream_url}')  # 修改分隔符为逗号

# 如果找到了目标直播源，输出它们
if target_streams:
    with open('filtered_streams.txt', 'w', encoding='utf-8') as out_file:
        out_file.write("abc频道,#genre#\n")  # 在文件前加上这行内容
        out_file.write("\n".join(target_streams))
    print(f"筛选完成！已保存到 'filtered_streams.txt'")
else:
    print("没有找到匹配的直播源。")
