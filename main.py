def filter_and_modify_sources(corrections):
    filtered_corrections = []
    name_dict = ['购物', '理财', '导视', '指南', '测试', '芒果', 'CGTN']
    
    # 添加新的关键词列表
    keyword_dict = [
        'EYETV 旅游', '亞洲旅遊', '美食星球', '亚洲武侠', 'Now爆谷台', 'Now星影台',
        '龍祥', 'Sun TV HD', 'SUN MUSIC', 'FASHION TV', 'Playboy Plus', '欧美艺术', '美国家庭'
    ]
    
    url_dict = []  # '2409:'留空不过滤ipv6频道

    for name, url in corrections:
        # 如果频道名称包含过滤列表中的任何一个关键词，则过滤掉该频道
        if any(word.lower() in name.lower() for word in name_dict) or any(word in url for word in url_dict):
            print("过滤频道:" + name + "," + url)
        # 如果频道名称包含任何新的关键词，则也允许通过
        elif any(word.lower() in name.lower() for word in keyword_dict):
            filtered_corrections.append((name, url))
        else:
            # 进行频道名称的替换操作
            name = name.replace("FHD", "").replace("HD", "").replace("hd", "").replace("频道", "").replace("高清", "") \
                .replace("超清", "").replace("20M", "").replace("-", "").replace("4k", "").replace("4K", "") \
                .replace("4kR", "")
            filtered_corrections.append((name, url))
    return filtered_corrections
