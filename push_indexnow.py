import os
import json
import urllib.request
import urllib.error

# --- 配置区域 ---
HOST = "nfhezu.top"
KEY = "8d493f761bc146c994dc76029412a3bc"
# 密钥文件必须可以通过此 URL 访问，否则验证会失败
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
# 脚本所在目录即为网站根目录
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_all_urls(root_dir, domain):
    """扫描目录下的所有HTML文件并生成URL列表"""
    urls = []
    # 默认添加根域名
    urls.append(f"https://{domain}/")
    
    print(f"正在扫描目录: {root_dir} ...")
    
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.html'):
                # 获取相对路径
                rel_path = os.path.relpath(os.path.join(dirpath, filename), root_dir)
                
                # 排除验证文件本身（如果它被误存为html）或其他无关文件
                if "google" in filename or "baidu" in filename:
                    continue

                # 转换路径分隔符 (Windows兼容)
                url_path = rel_path.replace(os.sep, '/')
                
                # 构建完整URL
                full_url = f"https://{domain}/{url_path}"
                urls.append(full_url)
                
                # 如果是 index.html，额外添加目录形式的 URL (例如 /blog/)
                if filename == 'index.html':
                    dir_url = url_path.replace('index.html', '')
                    if dir_url: # 避免空字符串
                        urls.append(f"https://{domain}/{dir_url}")
                        
    # 去重并排序
    return sorted(list(set(urls)))

def push_to_indexnow(urls):
    """发送请求到 IndexNow"""
    endpoint = "https://api.indexnow.org/indexnow"
    
    data = {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls
    }
    
    # 转换为 JSON 并编码
    json_data = json.dumps(data).encode('utf-8')
    
    print(f"\n准备推送 {len(urls)} 个链接到 IndexNow:")
    for url in urls:
        print(f" - {url}")
        
    # 发送请求
    req = urllib.request.Request(
        endpoint, 
        data=json_data, 
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )
    
    try:
        print("\n正在发送请求...")
        with urllib.request.urlopen(req) as response:
            if response.status in [200, 202]:
                print("✅ 成功! 链接已提交给 Bing/IndexNow，等待收录。")
            else:
                print(f"❌ 提交失败: 状态码 {response.status}")
                print(response.read().decode('utf-8'))
                
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP 错误: {e.code} - {e.reason}")
        print(e.read().decode('utf-8'))
    except Exception as e:
        print(f"❌ 发生异常: {e}")

if __name__ == "__main__":
    print("--- IndexNow 自动化推送脚本 ---")
    site_urls = get_all_urls(ROOT_DIR, HOST)
    
    if site_urls:
        push_to_indexnow(site_urls)
    else:
        print("未找到任何 HTML 文件。")
