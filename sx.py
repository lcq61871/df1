import requests
import re
import os
from collections import defaultdict
import concurrent.futures
import time

# ===== 参数配置 =====
target_channels = [
    'CCTV1', 'CCTV2', 'CCTV13',
    'CCTV世界地理[1920x1080]', 'CCTV央视文化精品[1920x1080]',
    '湖南卫视[1920x1080]', '湖南都市', '深圳都市',
    'EYETV 旅游', '亞洲旅遊', '美食星球',
    '亚洲武侠', 'Now爆谷台', 'Now星影台',
    '龍祥', 'Sun TV HD', 'SUN MUSIC', 'FASHION TV',
    'Playboy Plus', '欧美艺术', '美国家庭'
]

exclude_keywords = ['chinamobile', 'tvgslb', 'kkk.jjjj.jiduo.me', '理财']
timeout = 10
max_workers = 20

# ===== 确认当前目录并准备文件路径 =====
cwd = os.getcwd()
log_path = os.path.join(cwd, 'speed_log.txt')
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
    with open('iptv_list.txt', 'r', encoding='utf-8') as f:
        all_lines.extend(f.readlines())
    print("📄 已读取本地 iptv_list.txt")
except FileNotFoundError:
    print("⚠️ 本地文件未找到")

remote_urls = [
    'https://raw.githubusercontent.com/luoye20230624/hndxzb/refs/heads/main/iptv_list.txt',
    'https://raw.githubusercontent.com/80947108/888/6253b4e896ca08dc0ef16f9cf64f182d9d4116e6/tv/FGlive.m3u',
    'https://raw.githubusercontent.com/kkllllkkkk/kkllllkkkk.github.io/refs/heads/main/1.txt',
    'https://raw.githubusercontent.com/chiang1102/a/refs/heads/main/test1.txt',
    'https://live.iptv365.org/live.txt',
    'https://freetv.fun/test_channels_taiwan.m3u',
    'https://tv.iill.top/m3u/Gather',
    'https://gcore.jsdelivr.net/gh/Guovin/iptv-api@gd/output/result.m3u',
    'https://raw.githubusercontent.com/quninainaixi/quninainaixi/refs/heads/main/DSJ2024417.txt',
    'https://raw.githubusercontent.com/sqspot/tac/refs/heads/main/173.txt',
    'https://raw.githubusercontent.com/sqspot/tac/refs/heads/main/167.txt',
    'https://raw.githubusercontent.com/sqspot/tac/refs/heads/main/108.txt',
    'https://raw.githubusercontent.com/lcq61871/df1/refs/heads/main/iptv_list.txt',
    'https://raw.githubusercontent.com/lcq61871/iptvz/refs/heads/main/maotv.txt'
]

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
                        all_lines.append(f"{match.group(1).strip()} {lines[i + 1].strip()}")
        else:
            for line in lines[2:]:
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) == 2:
                        channel, stream = parts
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
    except:
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
            except:
                continue
    results.sort(key=lambda x: x[1])
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
