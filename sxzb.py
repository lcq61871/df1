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

# 最终生成的新文件名
OUTPUT_FILE = "output_streams.txt"


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
    print("🚀 开始自动提取【q1017673817/iptvz】CCTV 组播直播源...")
    combined_lines = []

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
                        combined_lines.append(genre_label)
                        combined_lines.extend(cctv_lines)
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

    if combined_lines:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(combined_lines))
        print(f"🎉 处理完成！生成新文件: {OUTPUT_FILE}")
    else:
        print("⚠️ 未拉取到有效数据。")


if __name__ == "__main__":
    main()
