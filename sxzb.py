import os
import re
import urllib.parse
import requests

# 目标拉取的4个组播文件及其对应展示的分类标签
TARGET_FILES = [
    ("组播_广东电信.txt", "东央视,#genre#"),
    ("组播_广西电信.txt", "西央视,#genre#"),
    ("组播_湖南电信.txt", "南央视,#genre#"),
    ("组播_湖北电信.txt", "北央视,#genre#"),
]

# GitHub Raw 基础路径
BASE_URL = "https://raw.githubusercontent.com/q1017673817/iptvz/main/"

# 远程 dszb.txt 基础直播源地址
REMOTE_DSZB_URL = "https://raw.githubusercontent.com/lcq61871/iptvz/main/dszb.txt"

# 最终生成的目标文件名
OUTPUT_FILE = "904.txt"


def filter_cctv_channels(content_text):
    """
    过滤并保留 CCTV 相关的直播频道信息，忽略自带的二级分类分组
    """
    lines = content_text.splitlines()
    filtered_lines = []

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue

        # 如果包含 comma 分隔的频道与URL
        if "," in line_str:
            channel_name, url = line_str.split(",", 1)
            channel_name = channel_name.strip()
            # 过滤掉内部的 #genre# 分组标记，仅保留包含 CCTV 的频道
            if "#genre#" not in url and "CCTV" in channel_name.upper():
                filtered_lines.append(f"{channel_name},{url.strip()}")

    return filtered_lines


def main():
    print("🚀 开始自动处理与合并直播源文件...")
    final_lines = []

    # 1. 首先拉取基础文件 dszb.txt
    print(f"🌐 正在拉取基础文件 dszb.txt...")
    try:
        r_dszb = requests.get(REMOTE_DSZB_URL, timeout=15)
        if r_dszb.status_code == 200 and r_dszb.text.strip():
            final_lines.append(r_dszb.text.strip())
            print("✅ 成功拉取 dszb.txt")
        else:
            print(f"⚠️ 拉取 dszb.txt 失败 (HTTP {r_dszb.status_code})")
    except Exception as e:
        print(f"❌ 请求 dszb.txt 异常: {e}")

    # 2. 依次提取 4 个组播文件中的 CCTV 频道并放在后面
    print("\n🌐 正在拉取并提取 CCTV 组播直播源...")
    for file_name, genre_label in TARGET_FILES:
        # 对中文文件名进行 URL 编码（防止出现 404）
        encoded_name = urllib.parse.quote(file_name)
        url = BASE_URL + encoded_name

        print(f"🌐 正在拉取: {file_name}")
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                content = r.text.strip()
                if content:
                    cctv_lines = filter_cctv_channels(content)
                    if cctv_lines:
                        # 添加你指定的央视分组标签
                        final_lines.append(genre_label)
                        final_lines.extend(cctv_lines)
                        print(
                            f"✅ 成功获取并过滤 {file_name}，保留 {len(cctv_lines)} 个 CCTV 频道"
                        )
                    else:
                        print(f"⚠️ {file_name} 中未找到 CCTV 频道")
                else:
                    print(f"⚠️ 文件内容为空: {file_name}")
            else:
                print(f"❌ 拉取失败: {file_name} (HTTP {r.status_code})")
        except Exception as e:
            print(f"❌ 请求异常: {file_name}, 错误: {e}")

    # 3. 写入最终文件 904.txt
    if final_lines:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(final_lines))
        print(f"\n🎉 处理完成！生成新文件: {OUTPUT_FILE}")
    else:
        print("⚠️ 未拉取到有效数据，未能生成文件。")


if __name__ == "__main__":
    main()
