import requests
import re
import os
from collections import defaultdict
import concurrent.futures
import time

# ===== 参数配置 =====
target_channels = [
    'CCTV1 综合[1920x1080]', 'CCTV2 财经[1920x1080]', 'CCTV13 新闻[1920x1080]',
    'CCTV世界地理[1920x1080]', 'CCTV央视文化精品[1920x1080]',
    'CCTV风云足球[1920x1080]', 'CCTV高尔夫·网球[1920x1080]', 'CCTV央视台球[1920x1080]',
    'CCTV怀旧剧场[1920x1080]', '功夫台', '龍祥時代',
	'湖南卫视[1920x1080]', '湖南都市高清 12M', '深圳都市频道',
    '亚洲武侠', 'Now爆谷台', 'Now星影台',
    'Playbo', '欧美艺术', '美国家庭'
]

exclude_keywords = ['chinamobile', 'tvgslb', '购物', '理财']
exclude_domains = ['kkk.jjjj.jiduo.me', 'www.freetv.top']  # 可以轻松在此添加更多域名
timeout = 15
max_workers = 20

# ===== 确认当前目录并准备文件路径 =====
cwd = os.getcwd()
log_path = os.path.join(cwd, 'speed_tv.txt')
out_path = os.path.join(cwd, 'filtered_streams.txt')

# ===== 删除旧文件 =====
if os.path.exists(out_path):
    os.remove(out_path)
if os.path.exists(log_path):
    os.remove(log_path)
print("✅ 已清理旧的输出文件")

# ===== 收集源数据 =====
all_lines = []
try:
    with open('iptv_list3.txt', 'r', encoding='utf-8') as f:
        all_lines.extend(f.readlines())
    print("📄 已读取本地 iptv_list3.txt")
except FileNotFoundError:
    print("⚠️ 本地文件未找到")

remote_urls = [
    'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt',
    'https://raw.githubusercontent.com/ngdikman/hksar/refs/heads/main/dianxin.txt',
    'https://raw.githubusercontent.com/lcq61871/iptvz/refs/heads/main/maotv.txt'
]

# 拉取远程数据
for url in remote_urls:
    try:
        print(f"🌐 拉取: {url}")
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            continue
        lines = r.text.splitlines()
        if url.endswith('.m3u'):
            for i in range(len(lines) - 1):
                if lines[i].startswith('#EXTINF') and lines[i + 1].startswith('http'):
                    match = re.search(r',(.+)', lines[i])
                    if match:
                        stream_url = lines[i + 1].strip()
                        # 排除特定域名
                        if any(domain in stream_url for domain in exclude_domains):
                            continue
                        all_lines.append(f"{match.group(1).strip()} {stream_url}")
        else:
            for line in lines[2:]:
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) == 2:
                        channel, stream = parts
                        # 排除特定域名
                        if any(domain in stream for domain in exclude_domains):
                            continue
                        all_lines.append(f"{channel.strip()} {stream.strip()}")
    except Exception as e:
        print(f"❌ 获取失败: {e}")

print(f"📺 获取频道源总数: {len(all_lines)}")

# ===== 精确匹配并整理 =====
target_set = set(name.lower() for name in target_channels)
grouped_streams = defaultdict(set)

for line in all_lines:
    line = line.strip()
    if not line or 'http' not in line:
        continue
    match = re.match(r'(.+?)\s+(https?://\S+)', line)
    if not match:
        continue
    channel_name = match.group(1).strip()
    stream_url = match.group(2).strip()
    if channel_name.lower() in target_set and not any(keyword in channel_name for keyword in exclude_keywords):
        grouped_streams[channel_name].add(stream_url)

# ===== 测速并选最快的前5个源 =====
def test_stream_speed(url, timeout=10):
    try:
        start = time.time()
        response = requests.get(url, timeout=timeout, stream=True)
        if response.status_code == 200:
            duration = time.time() - start
            return url, duration
    except requests.RequestException:
        pass
    return url, float('inf')

def get_fastest_urls(channel, urls, top_n=5):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(test_stream_speed, url, timeout): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                url, duration = future.result()
                if duration != float('inf'):
                    results.append((url, duration))
            except Exception as e:
                print(f"❌ 测速失败: {e}")
                continue
    results.sort(key=lambda x: x[1])  # 根据延迟排序
    with open(log_path, 'a', encoding='utf-8') as log:
        if results:
            log.write(f"【{channel}】测速成功 {len(results[:top_n])} 条\n")
            for url, delay in results[:top_n]:
                log.write(f"  {delay:.2f}s  {url}\n")
        else:
            log.write(f"【{channel}】⚠️ 无可用源\n")
    print(f"✅ {channel} | 写入 {len(results[:top_n])} 条测速日志")
    return [url for url, _ in results[:top_n]]

# ===== 生成最终节目表 =====
final_streams = defaultdict(list)

for channel, urls in grouped_streams.items():
    print(f"⚙️ 正在测速: {channel} 共 {len(urls)} 条链接")
    fastest = get_fastest_urls(channel, urls, top_n=5)
    final_streams[channel].extend(fastest)

# ===== 写入 filtered_streams.txt =====
with open(out_path, 'w', encoding='utf-8') as f:
    f.write("abc频道,#genre#\n")
    for channel, urls in sorted(final_streams.items()):
        for url in urls:
            f.write(f"{channel}, {url}\n")

print("✅ 完成！输出文件：")
print(f"📄 {out_path}")
print(f"📄 {log_path}")
