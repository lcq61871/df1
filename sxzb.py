import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# 统一获取路径
ZUBO_ALL_URL = "https://raw.githubusercontent.com/q1017673817/iptvz/refs/heads/main/zubo_all.txt"

# 排序后的 Top 3 分组对应的自定义输出标签
LABELS = ["北央视,#genre#", "东央视,#genre#", "西央视,#genre#"]

# 输出目标文件名
OUTPUT_FILE = "output_streams.txt"


def parse_telecom_groups(content_text):
    """
    解析 zubo_all.txt，按分组提取所有【电信】组播分组及其内部 CCTV 频道
    """
    lines = content_text.splitlines()
    groups_data = {}
    current_group = None

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue

        # 匹配分组标记行（例如：湖北电信-组播1,#genre#）
        if ",#genre#" in line_str:
            group_name = line_str.split(",#genre#")[0].strip()
            # 筛选包含“电信”字样的分组
            if "电信" in group_name:
                current_group = group_name
                if current_group not in groups_data:
                    groups_data[current_group] = []
            else:
                current_group = None
            continue

        # 提取当前分组下的 CCTV 频道
        if current_group and "," in line_str:
            channel_name, url = line_str.split(",", 1)
            channel_name = channel_name.strip()
            if "CCTV" in channel_name.upper():
                groups_data[current_group].append((channel_name, url.strip()))

    # 过滤掉虽然包含电信分组但里面没有 CCTV 频道的空组
    valid_groups = {g: channels for g, channels in groups_data.items() if channels}
    return valid_groups


def test_group_speed(group_info):
    """
    对单组分组中的频道抽取测试链接（优先选 CCTV1），测量 HTTP 响应延迟 (单位: 秒)
    """
    group_name, channels = group_info
    test_url = None

    # 优先使用 CCTV1 / CCTV-1 的 URL 测速，如果没有则选第一个
    for ch_name, url in channels:
        if "CCTV1" in ch_name.upper().replace("-", ""):
            test_url = url
            break
    if not test_url:
        test_url = channels[0][1]

    # 发起 HTTP 请求测试连通性与首字节延迟
    try:
        start_time = time.time()
        # 尝试使用 HEAD 方法快速获取响应，如果不支持则回退到 GET
        r = requests.head(test_url, timeout=3, allow_redirects=True)
        if r.status_code >= 400:
            r = requests.get(test_url, timeout=3, stream=True)
        
        elapsed = time.time() - start_time
        if r.status_code < 400:
            return group_name, elapsed
    except Exception:
        pass

    # 测速失败或超时返回无限大
    return group_name, float('inf')


def main():
    print("🚀 开始从 zubo_all.txt 拉取全省电信组播数据...")

    try:
        r = requests.get(ZUBO_ALL_URL, timeout=15)
        if r.status_code != 200 or not r.text.strip():
            print(f"❌ 拉取失败: HTTP {r.status_code}")
            return

        groups_data = parse_telecom_groups(r.text.strip())
        print(f"📊 共解析出 {len(groups_data)} 个有效电信组播分组，开始进行并发测速...")

        # 多线程并发对各个电信分组进行测速
        group_speeds = []
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_group = {
                executor.submit(test_group_speed, (g, chs)): g 
                for g, chs in groups_data.items()
            }
            for future in as_completed(future_to_group):
                g_name, speed = future.result()
                if speed != float('inf'):
                    group_speeds.append((g_name, speed))
                    print(f"⚡ 测速成功: 【{g_name}】 - 延迟: {speed:.3f} 秒")
                else:
                    print(f"❌ 测速超时/失败: 【{g_name}】")

        if not group_speeds:
            print("⚠️ 未测出任何可用的电信组播源！")
            return

        # 按延迟由低到高（速度由快到慢）排序
        group_speeds.sort(key=lambda x: x[1])
        top3_groups = group_speeds[:3]

        print("\n🏆 筛选出的播放速度最快 Top 3 电信分组：")
        for idx, (g_name, speed) in enumerate(top3_groups):
            print(f"  第 {idx+1} 名: {g_name} (延迟: {speed:.3f}s) -> 映射为: {LABELS[idx]}")

        # 组装最终写入文本
        combined_lines = []
        for idx, (g_name, speed) in enumerate(top3_groups):
            label = LABELS[idx]
            channels = groups_data[g_name]
            
            combined_lines.append(label)
            for ch_name, url in channels:
                combined_lines.append(f"{ch_name},{url}")

        # 写入文件
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(combined_lines))

        print(f"\n🎉 处理完成！最快 3 个分组的 CCTV 线路已成功写入: {OUTPUT_FILE}")

    except Exception as e:
        print(f"❌ 程序运行异常: {e}")


if __name__ == "__main__":
    main()