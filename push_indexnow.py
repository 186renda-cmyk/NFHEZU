import os
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

# --- 配置区域 ---
HOST = "nfhezu.top"
KEY = "8d493f761bc146c994dc76029412a3bc"
# 密钥文件必须可以通过此 URL 访问，否则验证会失败
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
# 脚本所在目录即为网站根目录
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SITEMAP_PATH = os.path.join(ROOT_DIR, "sitemap.xml")

def get_urls_from_sitemap(sitemap_path):
    """从 sitemap.xml 提取 URL"""
    urls = []
    if not os.path.exists(sitemap_path):
        return urls
    
    print(f"正在读取 Sitemap: {sitemap_path}")
    try:
        tree = ET.parse(sitemap_path)
        root = tree.getroot()
        # 处理命名空间 (Standard Sitemap Protocol)
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # 尝试使用命名空间查找
        found = False
        for url in root.findall('sm:url', ns):
            loc = url.find('sm:loc', ns)
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
                found = True
        
        # 如果没找到（可能是没有命名空间或格式不同），尝试通用遍历
        if not found:
            for elem in root.iter():
                if 'loc' in elem.tag and elem.text:
                    urls.append(elem.text.strip())
                    
    except Exception as e:
        print(f"⚠️ 解析 Sitemap 出错: {e}")
        
    return urls

def get_urls_from_scan(root_dir, domain):
    """扫描目录下的所有HTML文件并生成URL列表 (备用方案)"""
    urls = []
    
    print(f"正在扫描目录: {root_dir} ...")
    
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.html'):
                # 获取相对路径
                rel_path = os.path.relpath(os.path.join(dirpath, filename), root_dir)
                
                # 排除验证文件本身或其他无关文件
                if "google" in filename or "baidu" in filename:
                    continue

                # 转换路径分隔符
                url_path = rel_path.replace(os.sep, '/')
                
                # 处理 URL 规则
                if filename == 'index.html':
                    # 目录页/首页：保留尾部斜杠
                    if url_path == 'index.html':
                        # 根目录首页
                        full_url = f"https://{domain}/"
                    else:
                        # 子目录首页 (如 blog/index.html -> blog/)
                        dir_path = url_path.replace('/index.html', '/')
                        full_url = f"https://{domain}/{dir_path}"
                else:
                    # 文章页/详情页：去除 .html 且去除尾部斜杠
                    clean_path = url_path.replace('.html', '')
                    full_url = f"https://{domain}/{clean_path}"
                
                urls.append(full_url)
                        
    return sorted(list(set(urls)))

def push_to_indexnow(urls):
    """发送请求到 IndexNow"""
    if not urls:
        print("没有需要推送的 URL。")
        return

    endpoint = "https://api.indexnow.org/indexnow"
    
    data = {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls
    }
    
    json_data = json.dumps(data).encode('utf-8')
    
    print(f"\n准备推送 {len(urls)} 个链接到 IndexNow:")
    for url in urls:
        print(f" - {url}")
        
    req = urllib.request.Request(
        endpoint, 
        data=json_data, 
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )
    
    try:
        print("\n正在发送请求...")
        with urllib.request.urlopen(req) as response:
            if response.status in [200, 202]:
                print("✅ 成功! 链接已提交给 Bing/IndexNow。")
            else:
                print(f"❌ 提交失败: 状态码 {response.status}")
                print(response.read().decode('utf-8'))
                
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP 错误: {e.code} - {e.reason}")
        try:
            print(e.read().decode('utf-8'))
        except:
            pass
    except Exception as e:
        print(f"❌ 发生异常: {e}")

if __name__ == "__main__":
    print("--- IndexNow 自动化推送脚本 ---")
    
    # 1. 尝试从 Sitemap 获取 (优先)
    site_urls = get_urls_from_sitemap(SITEMAP_PATH)
    
    # 2. 如果 Sitemap 获取失败或为空，回退到文件扫描
    if site_urls:
        print(f"✅ 从 Sitemap 获取到 {len(site_urls)} 个链接")
    else:
        print("⚠️ Sitemap 为空或读取失败，切换到文件扫描模式")
        site_urls = get_urls_from_scan(ROOT_DIR, HOST)
    
    # 3. 推送
    if site_urls:
        push_to_indexnow(site_urls)
    else:
        print("❌ 未找到任何 HTML 文件或 URL。")
