import os
import re
import urllib.parse
import requests

# 目标拉取的4个组播文件列表
TARGET_FILES = [
    "组播_湖南电信.txt",
    "组播_湖北电信.txt",
    "组播_广东电信.txt",
    "组播_广西电信.txt",
]

# GitHub Raw 基础路径
BASE_URL = "https://raw.githubusercontent.com/q1017673817/iptvz/main/"

# 最终生成的新文件名
OUTPUT_FILE = "output_streams.txt"


def main():
    print("🚀 开始自动提取【q1017673817/iptvz】指定组播直播源...")
    combined_lines = []

    for file_name in TARGET_FILES:
        # 对中文文件名进行 URL 编码（防止出现 404）
        encoded_name = urllib.parse.quote(file_name)
        url = BASE_URL + encoded_name

        print(f"🌐 正在拉取: {file_name}")
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                content = r.text.strip()
                if content:
                    # 在每个分组前面打上分类标签（也可直接添加内容）
                    combined_lines.append(f"{file_name.replace('.txt','')},#genre#")
                    combined_lines.append(content)
                    print(f"✅ 成功获取: {file_name}")
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
