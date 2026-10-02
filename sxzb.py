import re
import requests

# 统一获取路径
ZUBO_ALL_URL = "https://raw.githubusercontent.com/q1017673817/iptvz/refs/heads/main/zubo_all.txt"

# 需提取的目标分组名称及其对应的新分类标签
TARGET_GROUPS = [
    ("湖北电信-组播1", "北央视,#genre#"),
    ("河南电信-组播1", "南央视,#genre#"),
    ("广东电信-组播1", "东央视,#genre#"),
    ("广西电信-组播1", "西央视,#genre#"),
]

# 输出文件
OUTPUT_FILE = "output_streams.txt"


def parse_and_filter_groups(content_text):
    """
    解析 zubo_all.txt 文本，按指定分组提取并过滤其中的 CCTV 频道
    """
    lines = content_text.splitlines()

    # 1. 将文件按照分类分组打散存储到字典中
    # 结构格式: { "湖北电信-组播1": ["CCTV1,http://...", "CCTV2,http://..."] }
    groups_data = {}
    current_group = None

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue

        # 判断是否为分组定义行（例如：湖北电信-组播1,#genre#）
        if ",#genre#" in line_str:
            current_group = line_str.split(",#genre#")[0].strip()
            if current_group not in groups_data:
                groups_data[current_group] = []
            continue

        # 如果属于当前分类，且包含频道名称与地址
        if current_group and "," in line_str:
            channel_name, url = line_str.split(",", 1)
            channel_name = channel_name.strip()
            # 仅保留名称中包含 CCTV 的频道
            if "CCTV" in channel_name.upper():
                groups_data[current_group].append(f"{channel_name},{url.strip()}")

    # 2. 按照需要的顺序组合提取到的数据
    result_lines = []
    for group_name, genre_label in TARGET_GROUPS:
        if group_name in groups_data and groups_data[group_name]:
            # 添加自定义标签
            result_lines.append(genre_label)
            # 添加该分组下的所有 CCTV 频道
            result_lines.extend(groups_data[group_name])
            print(
                f"✅ 成功提取分组【{group_name}】，保留 {len(groups_data[group_name])} 个 CCTV 频道"
            )
        else:
            print(f"⚠️ 未找到分组【{group_name}】或该分组下无 CCTV 频道")

    return result_lines


def main():
    print("🚀 开始自动从 zubo_all.txt 提取 CCTV 组播直播源...")

    try:
        r = requests.get(ZUBO_ALL_URL, timeout=15)
        if r.status_code == 200 and r.text.strip():
            combined_lines = parse_and_filter_groups(r.text.strip())

            if combined_lines:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(combined_lines))
                print(f"\n🎉 处理完成！生成新文件: {OUTPUT_FILE}")
            else:
                print("\n⚠️ 未匹配到任何有效数据。")
        else:
            print(f"❌ 拉取 zubo_all.txt 失败 (HTTP {r.status_code})")
    except Exception as e:
        print(f"❌ 请求异常: {e}")


if __name__ == "__main__":
    main()