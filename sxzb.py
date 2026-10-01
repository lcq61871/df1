import urllib.parse
import os
import requests

# 1. 目标文件列表
TARGET_FILES = [
    "组播_湖南电信.txt",
    "组播_湖北电信.txt",
    "组播_广东电信.txt",
    "组播_广西电信.txt",
]

# GitHub raw 基础路径
BASE_URL = "https://raw.githubusercontent.com/q1017673817/iptvz/main/"

# 输出生成的新文件名
OUTPUT_FILE = "combined_telecom_iptv.txt"


def fetch_and_combine():
    combined_content = []

    print("🚀 开始获取目标直播源数据...")

    for file_name in TARGET_FILES:
        # 对文件名进行 URL 编码（防止中文路径出现 404）
        encoded_name = urllib.parse.quote(file_name)
        url = BASE_URL + encoded_name

        print(f"🌐 正在拉取: {file_name} -> {url}")
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                # 保持 utf-8 编码读取
                content = response.text.strip()
                if content:
                    combined_content.append(f"#{file_name}\n{content}")
                    print(f"✅ 成功获取: {file_name}")
                else:
                    print(f"⚠️ 文件内容为空: {file_name}")
            else:
                print(f"❌ 拉取失败: {file_name} (状态码: {response.status_code})")
        except Exception as e:
            print(f"❌ 请求异常: {file_name}, 错误信息: {e}")

    # 保存合并后的新文件
    if combined_content:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n\n".join(combined_content))
        print(f"🎉 成功生成新文件: {OUTPUT_FILE}")
    else:
        print("⚠️ 未获取到任何有效内容，未能生成新文件。")


if __name__ == "__main__":
    fetch_and_combine()
