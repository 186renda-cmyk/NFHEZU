import os
import re
import random
import json
import datetime
from bs4 import BeautifulSoup, Comment

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG_DIR = os.path.join(PROJECT_ROOT, 'blog')
INDEX_FILE = os.path.join(PROJECT_ROOT, 'index.html')

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def clean_link(url):
    """
    Remove .html suffix from internal links.
    Keep suffix for files like .ico, .svg, .png, .jpg, .css, .js, .xml, .txt
    """
    if not url:
        return url
    
    # Skip external links, anchors, and data URIs
    if url.startswith(('http:', 'https:', '#', 'data:', 'mailto:', 'tel:')):
        return url
    
    # List of extensions to preserve
    preserve_exts = ['.ico', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.css', '.js', '.xml', '.txt', '.json']
    
    # Check if it has an extension that should be preserved
    for ext in preserve_exts:
        if url.lower().endswith(ext):
            return url
            
    # Remove .html or .htm suffix
    return re.sub(r'\.html?$', '', url, flags=re.IGNORECASE)

def process_links(soup):
    """
    Process all a[href] and img[src] to remove .html suffix where appropriate.
    """
    for tag in soup.find_all(['a', 'link', 'img', 'script']):
        # Handle href
        if tag.has_attr('href'):
            tag['href'] = clean_link(tag['href'])
        
        # Handle src
        if tag.has_attr('src'):
            tag['src'] = clean_link(tag['src'])
            
    return soup

def extract_assets():
    """
    Phase 1: Smart Extraction from index.html
    """
    print(f"Loading {INDEX_FILE}...")
    if not os.path.exists(INDEX_FILE):
        print("Error: index.html not found!")
        return None

    content = read_file(INDEX_FILE)
    soup = BeautifulSoup(content, 'html.parser')
    
    # 1. Extract Layout Components
    nav = soup.find('nav', id='main-nav') or soup.find('nav')
    footer = soup.find('footer')
    
    if not nav:
        print("Warning: <nav> not found in index.html")
    if not footer:
        print("Warning: <footer> not found in index.html")

    # Clean links in nav and footer
    if nav:
        process_links(nav)
    if footer:
        process_links(footer)

    # 2. Extract Brand Assets (Favicons)
    favicons = []
    # Find all link tags with rel containing 'icon'
    for link in soup.find_all('link'):
        rel = link.get('rel', [])
        if isinstance(rel, list):
            rel = ' '.join(rel)
        
        if 'icon' in rel:
            # Force root relative path for non-data URIs
            href = link.get('href', '')
            if href and not href.startswith(('http:', 'https:', 'data:')):
                if not href.startswith('/'):
                    href = '/' + href
                link['href'] = href
            favicons.append(link)
            
    return {
        'nav': nav,
        'footer': footer,
        'favicons': favicons
    }

def get_blog_posts():
    """
    Get list of blog posts for recommendation system.
    """
    posts = []
    if not os.path.exists(BLOG_DIR):
        return posts
        
    for filename in os.listdir(BLOG_DIR):
        if filename.endswith('.html') and filename != 'index.html':
            file_path = os.path.join(BLOG_DIR, filename)
            soup = BeautifulSoup(read_file(file_path), 'html.parser')
            title = soup.title.string if soup.title else filename
            
            # Try to find a description or image for better recommendation cards
            desc = soup.find('meta', attrs={'name': 'description'})
            desc_content = desc['content'] if desc else ''
            
            # Extract og:image
            og_image = soup.find('meta', property='og:image')
            image_url = og_image['content'] if og_image else '/images/netflix-experience.png'
            # Ensure image path is root relative if it's local
            if image_url and not image_url.startswith(('http', 'https', '/')):
                image_url = '/blog/' + image_url # Assuming images are relative to blog/
                # But wait, in the html files they might be "images/..." which means blog/images/...
                # Let's check how they are referenced.
                # In the provided files, og:image is "images/devices-monitor.png"
                # If the file is in blog/, "images/..." refers to blog/images/...
                # So prepending /blog/ is correct for root-relative path.
            
            posts.append({
                'filename': filename,
                'url': '/blog/' + clean_link(filename),
                'title': title,
                'description': desc_content,
                'image': image_url
            })
    return posts

def generate_recommendations(current_filename, all_posts):
    """
    Generate HTML for recommended reading (random 2 posts excluding current).
    """
    others = [p for p in all_posts if p['filename'] != current_filename]
    if len(others) < 2:
        recs = others
    else:
        recs = random.sample(others, 2)
        
    if not recs:
        return None

    html = '''
    <div class="mt-16 pt-8 border-t border-white/10 recommendation-section">
        <h3 class="text-xl font-bold text-white mb-6 flex items-center gap-2">
            <span class="w-1 h-6 bg-netflix-red rounded-full shadow-[0_0_12px_rgba(229,9,20,0.6)]"></span>
            推荐阅读
        </h3>
        <div class="grid md:grid-cols-2 gap-4">
    '''
    
    for post in recs:
        html += f'''
            <a href="{post['url']}" class="group block h-full p-6 bg-[#1a1a1a] rounded-2xl border border-white/5 hover:border-netflix-red/30 hover:bg-[#202020] transition-all duration-300 no-underline">
                <h4 class="text-lg font-bold text-netflix-red mb-3 leading-snug group-hover:text-red-400 transition-colors line-clamp-2">
                    {post['title']}
                </h4>
                
                <p class="text-sm text-gray-400 leading-relaxed line-clamp-3 group-hover:text-gray-300 transition-colors">
                    {post['description']}
                </p>
            </a>
        '''
    
    html += '''
        </div>
    </div>
    '''
    return BeautifulSoup(html, 'html.parser')

def generate_json_ld(soup, filename, is_blog=True, title=None, desc=None):
    """
    Generate JSON-LD script tag.
    Includes BreadcrumbList and BlogPosting/WebPage.
    """
    domain = "https://nfhezu.top"
    
    if is_blog:
        url = f"{domain}/blog/{clean_link(filename)}"
        breadcrumb_items = [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": domain + "/"},
            {"@type": "ListItem", "position": 2, "name": "探索发现", "item": domain + "/blog/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": url}
        ]
        
        schema_objects = [
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": breadcrumb_items
            },
            {
                "@context": "https://schema.org",
                "@type": "BlogPosting",
                "headline": title,
                "image": f"{domain}/images/netflix-experience.png", # Default or extract
                "author": {
                    "@type": "Organization",
                    "name": "NFhezu 编辑部",
                    "url": domain
                },
                "publisher": {
                    "@type": "Organization",
                    "name": "NFhezu",
                    "logo": {
                        "@type": "ImageObject",
                        "url": f"{domain}/logo.png"
                    }
                },
                "datePublished": datetime.date.today().isoformat(), # Ideally parse from content
                "dateModified": datetime.date.today().isoformat(),
                "description": desc or title
            }
        ]
    else:
        # Root pages like privacy, disclaimer
        url = f"{domain}/{clean_link(filename)}"
        breadcrumb_items = [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": domain + "/"},
            {"@type": "ListItem", "position": 2, "name": title, "item": url}
        ]
        
        schema_objects = [
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": breadcrumb_items
            },
            {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "name": title,
                "url": url,
                "description": desc or title
            }
        ]

    # Create script tag
    script_content = json.dumps(schema_objects, indent=2, ensure_ascii=False)
    # Wrap in one script tag or multiple? 
    # Usually one script tag with @graph or array is fine, but here we used list of objects.
    # To be safe and standard, let's output one script tag per object or a graph.
    # Let's use @graph style for cleaner single script.
    
    final_json = {
        "@context": "https://schema.org",
        "@graph": schema_objects
    }
    
    tag = soup.new_tag('script', type='application/ld+json')
    tag.string = json.dumps(final_json, indent=2, ensure_ascii=False)
    return tag

def ensure_breadcrumb_html(soup, is_blog=True):
    """
    Ensure there is a visual breadcrumb with aria-label="breadcrumb".
    Fixes audit.py warning.
    """
    # Try to find existing breadcrumb-like nav
    # Heuristic: nav containing "首页" link
    navs = soup.find_all('nav')
    breadcrumb_nav = None
    
    for nav in navs:
        # Check if it's the main nav (skip)
        if nav.get('id') == 'main-nav':
            continue
        
        # Check text content
        if "首页" in nav.get_text():
            breadcrumb_nav = nav
            break
            
    if breadcrumb_nav:
        # Fix existing
        breadcrumb_nav['aria-label'] = 'breadcrumb'
    else:
        # Create new if missing (simple version)
        # Only insert if we have a main container
        main = soup.find('main')
        if main:
            new_nav = soup.new_tag('nav', attrs={'aria-label': 'breadcrumb', 'class': 'flex mb-8 text-xs text-slate-500 font-medium tracking-wide uppercase'})
            
            # Home link
            link_home = soup.new_tag('a', href='/', attrs={'class': 'hover:text-slate-300 transition'})
            link_home.string = "首页"
            new_nav.append(link_home)
            
            # Separator
            sep = soup.new_tag('span', attrs={'class': 'mx-2'})
            sep.string = "/"
            new_nav.append(sep)
            
            if is_blog:
                link_blog = soup.new_tag('a', href='/blog/', attrs={'class': 'hover:text-slate-300 transition'})
                link_blog.string = "Blog"
                new_nav.append(link_blog)
                
                sep2 = soup.new_tag('span', attrs={'class': 'mx-2'})
                sep2.string = "/"
                new_nav.append(sep2)
            
            # Current page (text only)
            current = soup.new_tag('span', attrs={'class': 'text-slate-300'})
            current.string = "当前页面" # Placeholder, hard to get exact title here without passing it
            new_nav.append(current)
            
            main.insert(0, new_nav)
            
    return soup

def rebuild_head(soup, filename, favicons, is_blog=True):
    """
    Phase 2: Head Reconstruction
    """
    old_head = soup.head
    new_head = soup.new_tag('head')
    
    # Extract metadata for reuse
    title_tag = old_head.find('title')
    title_str = title_tag.string if title_tag else filename
    
    desc_tag = old_head.find('meta', attrs={'name': 'description'})
    desc_str = desc_tag['content'] if desc_tag else ''
    
    keywords_tag = old_head.find('meta', attrs={'name': 'keywords'})
    
    # --- Group A: Basic Metadata ---
    new_head.append(soup.new_tag('meta', charset="utf-8"))
    new_head.append(soup.new_tag('meta', attrs={"name": "viewport", "content": "width=device-width, initial-scale=1.0"}))
    
    if title_tag:
        new_head.append(title_tag)
    else:
        new_title = soup.new_tag('title')
        new_title.string = filename
        new_head.append(new_title)
        
    new_head.append('\n')

    # --- Group B: SEO Core ---
    if desc_tag:
        new_head.append(desc_tag)
    
    if keywords_tag:
        new_head.append(keywords_tag)
        
    # Canonical
    if is_blog:
        canonical_url = f"https://nfhezu.top/blog/{clean_link(filename)}"
    else:
        canonical_url = f"https://nfhezu.top/{clean_link(filename)}"
        
    canonical = soup.new_tag('link', rel="canonical", href=canonical_url)
    new_head.append(canonical)
    
    new_head.append('\n')

    # --- Group C: Indexing & Geo ---
    new_head.append(soup.new_tag('meta', attrs={"name": "robots", "content": "index, follow"}))
    new_head.append(soup.new_tag('meta', attrs={"http-equiv": "content-language", "content": "zh-CN"}))
    
    # Hreflang Matrix
    new_head.append(soup.new_tag('link', rel="alternate", href=canonical_url, hreflang="x-default"))
    new_head.append(soup.new_tag('link', rel="alternate", href=canonical_url, hreflang="zh"))
    new_head.append(soup.new_tag('link', rel="alternate", href=canonical_url, hreflang="zh-CN"))
    
    new_head.append('\n')

    # --- Group D: Branding & Resources ---
    # Favicons (from Phase 1)
    for icon in favicons:
        import copy
        new_head.append(copy.copy(icon))
        
    # Preserve existing CSS/JS (Tailwind, Fonts, etc.)
    for tag in old_head.find_all(['link', 'script', 'style']):
        # Skip favicons
        if tag.name == 'link' and 'icon' in str(tag.get('rel', '')):
            continue
        # Skip canonical
        if tag.name == 'link' and tag.get('rel') == ['canonical']:
            continue
        # Skip alternate/hreflang
        if tag.name == 'link' and tag.get('rel') == ['alternate']:
            continue
        # Skip old JSON-LD (we will regenerate)
        if tag.name == 'script' and tag.get('type') == 'application/ld+json':
            continue
            
        new_head.append(tag)
        
    new_head.append('\n')

    # --- Group E: Structured Data ---
    # Generate fresh JSON-LD
    json_ld_tag = generate_json_ld(soup, filename, is_blog=is_blog, title=title_str, desc=desc_str)
    new_head.append(json_ld_tag)

    soup.head.replace_with(new_head)
    return soup

def process_file(file_path, assets, all_posts, is_blog=True):
    filename = os.path.basename(file_path)
    print(f"Processing {filename}...")
    
    content = read_file(file_path)
    soup = BeautifulSoup(content, 'html.parser')
    
    # --- Phase 2: Head Reconstruction ---
    soup = rebuild_head(soup, filename, assets['favicons'], is_blog=is_blog)
    
    # --- Fix Breadcrumb HTML (for audit) ---
    soup = ensure_breadcrumb_html(soup, is_blog=is_blog)
    
    # --- Phase 3: Injection ---
    
    # 1. Layout Sync (Nav & Footer)
    old_nav = soup.find('nav', id='main-nav') or soup.find('nav')
    if old_nav:
        import copy
        new_nav = copy.copy(assets['nav'])
        
        # Adjust links
        for a in new_nav.find_all('a'):
            href = a.get('href', '')
            if href.startswith('#'):
                a['href'] = '/' + href
        
        old_nav.replace_with(new_nav)
    else:
        if soup.body:
            soup.body.insert(0, assets['nav'])

    old_footer = soup.find('footer')
    if old_footer:
        import copy
        new_footer = copy.copy(assets['footer'])
        for a in new_footer.find_all('a'):
            href = a.get('href', '')
            if href.startswith('#'):
                a['href'] = '/' + href
        
        old_footer.replace_with(new_footer)
    else:
        if soup.body:
            soup.body.append(assets['footer'])
            
    # 3. Smart Recommendation Injection (Only for Blog)
    if is_blog:
        article = soup.find('article')
        if article:
            # Remove previous recommendations
            # 1. By class 'recommendation-section' (our current marker)
            for div in article.find_all('div', class_='recommendation-section'):
                 div.decompose()
            
            # 2. By structure/text content (legacy markers)
            # Find all divs that might be recommendation sections
            # Pattern 1: mt-16 pt-10 ...
            for div in article.find_all('div', class_='mt-16 pt-10 border-t border-white/10'):
                 if "推荐阅读" in div.get_text():
                     div.decompose()
            
            # Pattern 2: mt-12 pt-8 ... (Found in devices guide)
            for div in article.find_all('div', class_='mt-12 pt-8 border-t border-white/10'):
                 if "推荐阅读" in div.get_text():
                     div.decompose()
                     
            # Pattern 3: Generic fallback - find any h3 with "推荐阅读" and remove its parent div if it looks like a section
            # This is a bit risky if structure varies, but let's try to be safe
            for h3 in article.find_all('h3'):
                if "推荐阅读" in h3.get_text():
                    # Check if parent is a div that looks like a wrapper
                    parent = h3.parent
                    if parent.name == 'div' and ('border-t' in parent.get('class', [])):
                        parent.decompose()

            recommendations = generate_recommendations(filename, all_posts)
            if recommendations:
                article.append(recommendations)
            
    # 4. Global Update (Link Cleaning)
    soup = process_links(soup)
    
    # Save
    write_file(file_path, str(soup))
    print(f"Saved {filename}")

def main():
    print("Starting Build Process...")
    
    if not os.path.exists(INDEX_FILE):
        print("Error: index.html not found.")
        return

    # Phase 1
    assets = extract_assets()
    if not assets:
        return
    
    # Get blog posts for recommendations
    all_posts = get_blog_posts()
    
    # Process Blog Files
    if os.path.exists(BLOG_DIR):
        for filename in os.listdir(BLOG_DIR):
            if not filename.endswith('.html') or filename == 'index.html':
                continue
            file_path = os.path.join(BLOG_DIR, filename)
            process_file(file_path, assets, all_posts, is_blog=True)
            
    # Process Root Files (Privacy, Disclaimer)
    # Explicitly list files to process in root to avoid processing index.html or others unintentionally
    root_files_to_process = ['privacy.html', 'disclaimer.html']
    for filename in root_files_to_process:
        file_path = os.path.join(PROJECT_ROOT, filename)
        if os.path.exists(file_path):
            process_file(file_path, assets, all_posts, is_blog=False)
    
    print("Build Complete.")

if __name__ == "__main__":
    main()
