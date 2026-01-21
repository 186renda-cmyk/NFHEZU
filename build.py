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
    Sorted by modification time (newest first).
    """
    posts = []
    if not os.path.exists(BLOG_DIR):
        return posts
        
    for filename in os.listdir(BLOG_DIR):
        if filename.endswith('.html') and filename != 'index.html':
            file_path = os.path.join(BLOG_DIR, filename)
            soup = BeautifulSoup(read_file(file_path), 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else filename
            
            # Try to find a description or image for better recommendation cards
            desc = soup.find('meta', attrs={'name': 'description'})
            desc_content = desc['content'].strip() if desc and desc.get('content') else ''
            
            # Extract og:image
            og_image = soup.find('meta', property='og:image')
            image_url = og_image['content'] if og_image else '/images/netflix-experience.png'
            if image_url and not image_url.startswith(('http', 'https', '/')):
                image_url = '/blog/' + image_url
            
            # Get modification time
            mtime = os.path.getmtime(file_path)
            
            posts.append({
                'filename': filename,
                'url': '/blog/' + clean_link(filename),
                'title': title,
                'description': desc_content,
                'image': image_url,
                'mtime': mtime
            })
    
    # Sort by modification time, newest first
    posts.sort(key=lambda x: x['mtime'], reverse=True)
    return posts

def get_theme(filename):
    """
    Return theme configuration based on filename keywords.
    """
    # Define themes
    themes = {
        'blue': {
            'border': 'hover:border-blue-500/50',
            'gradient': 'from-[#0a102a] to-[#0a0a0a] group-hover:from-[#0f1c4d]',
            'tag_bg': 'bg-blue-600',
            'tag_text': '深度解析',
            'text_hover': 'group-hover:text-blue-400',
            'blur_color': 'bg-blue-500/10 group-hover:bg-blue-500/20',
            'icon': '<path d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"></path>'
        },
        'yellow': {
            'border': 'hover:border-yellow-500/50',
            'gradient': 'from-[#2a1c05] to-[#0a0a0a] group-hover:from-[#452b0a]',
            'tag_bg': 'bg-yellow-600',
            'tag_text': '选区指南',
            'text_hover': 'group-hover:text-yellow-400',
            'blur_color': 'bg-yellow-500/10 group-hover:bg-yellow-500/20',
            'icon': '<path d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"></path>'
        },
        'red': {
            'border': 'hover:border-netflix-red/50',
            'gradient': 'from-[#2a0505] to-[#0a0a0a] group-hover:from-[#450a0a]',
            'tag_bg': 'bg-netflix-red',
            'tag_text': '避坑指南',
            'text_hover': 'group-hover:text-netflix-red',
            'blur_color': 'bg-netflix-red/10 group-hover:bg-netflix-red/20',
            'icon': '<path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"></path>'
        },
        'cyan': {
            'border': 'hover:border-cyan-500/50',
            'gradient': 'from-[#05202a] to-[#0a0a0a] group-hover:from-[#0a3045]',
            'tag_bg': 'bg-cyan-600',
            'tag_text': '新手教程',
            'text_hover': 'group-hover:text-cyan-400',
            'blur_color': 'bg-cyan-500/10 group-hover:bg-cyan-500/20',
            'icon': '<path d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"></path>'
        },
        'purple': {
            'border': 'hover:border-purple-500/50',
            'gradient': 'from-[#1a0524] to-[#0a0a0a] group-hover:from-[#2d0a3d]',
            'tag_bg': 'bg-purple-600',
            'tag_text': '片单推荐',
            'text_hover': 'group-hover:text-purple-400',
            'blur_color': 'bg-purple-500/5 group-hover:bg-purple-500/10',
            'icon': '<path d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"></path>'
        },
        'green': {
            'border': 'hover:border-green-500/50',
            'gradient': 'from-[#052005] to-[#0a0a0a] group-hover:from-[#0a300a]',
            'tag_bg': 'bg-green-600',
            'tag_text': '观看指南',
            'text_hover': 'group-hover:text-green-400',
            'blur_color': 'bg-green-500/5 group-hover:bg-green-500/10',
            'icon': '<path d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"></path><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"></path>'
        }
    }
    
    # Logic to map filename to theme
    fn = filename.lower()
    if 'buying-guide' in fn or '避坑' in fn:
        return themes['red']
    elif 'region' in fn or '地区' in fn or 'country' in fn:
        return themes['yellow']
    elif 'content' in fn or 'library' in fn or '片源' in fn:
        return themes['blue']
    elif 'subscribe' in fn or 'pay' in fn or '支付' in fn:
        return themes['cyan']
    elif 'best-movies' in fn or 'recommend' in fn or '片单' in fn:
        return themes['purple']
    elif 'watch' in fn or 'device' in fn or '观看' in fn:
        return themes['green']
    else:
        # Default fallback
        return themes['red']

def create_card_html(post):
    """
    Generate a single card HTML (Rich Design with Icon/Gradient)
    Matches the design in blog/index.html
    """
    theme = get_theme(post['filename'])
    
    # Format date
    dt = datetime.datetime.fromtimestamp(post['mtime'])
    date_str = dt.strftime('%Y-%m-%d')
    
    # Generate random heat
    heat = round(random.uniform(0.5, 3.0), 1)
    heat_str = f"{heat}w"
    if heat < 1.0:
        heat_str = f"{int(heat*10)}k"
        
    return f'''
    <article class="group bg-[#121212] rounded-2xl overflow-hidden border border-white/10 {theme['border']} transition-all duration-300 hover:-translate-y-1">
        <a href="{post['url']}" class="block">
            <div class="aspect-video relative overflow-hidden bg-gradient-to-br {theme['gradient']} transition-colors duration-500">
                <!-- Decorative Circle -->
                <div class="absolute -top-8 -right-8 w-32 h-32 {theme['blur_color']} rounded-full blur-2xl transition-all"></div>
                
                <!-- Icon -->
                <div class="absolute inset-0 flex items-center justify-center">
                    <svg class="w-20 h-20 text-white/20 group-hover:text-white/40 group-hover:scale-110 group-hover:rotate-6 transition duration-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        {theme['icon']}
                    </svg>
                </div>
                
                <div class="absolute top-4 left-4 z-20 {theme['tag_bg']} text-white text-xs font-bold px-2 py-1 rounded shadow-lg border border-white/10">
                    {theme['tag_text']}
                </div>
            </div>
            
            <div class="p-6">
                <div class="text-xs text-gray-500 mb-2 flex items-center gap-2">
                    <span>📅 {date_str}</span>
                    <span>•</span>
                    <span>🔥 热度: {heat_str}</span>
                </div>
                
                <h3 class="text-xl font-bold text-white mb-3 line-clamp-2 {theme['text_hover']} transition">
                    {post['title']}
                </h3>
                
                <p class="text-gray-400 text-sm line-clamp-3 leading-relaxed">
                    {post['description']}
                </p>
            </div>
        </a>
    </article>
    '''

def update_index_html(all_posts):
    """
    Update index.html blog section with latest 4 posts.
    """
    print(f"Updating {INDEX_FILE}...")
    if not os.path.exists(INDEX_FILE):
        return

    content = read_file(INDEX_FILE)
    soup = BeautifulSoup(content, 'html.parser')
    
    # Find the blog section container
    blog_section = soup.find('section', id='blog')
    if not blog_section:
        print("Warning: #blog section not found in index.html")
        return

    # Find the grid container
    # The grid container in index.html might have different classes now.
    # In the file I read, it was: <div class="grid md:grid-cols-4 gap-6">
    grid = blog_section.find('div', class_='grid')
    if not grid:
        print("Warning: Blog grid not found in index.html")
        return
        
    # Clear existing cards
    grid.clear()
    
    # Take top 4 posts
    latest_posts = all_posts[:4]
    
    # Generate new cards
    for post in latest_posts:
        card_html = create_card_html(post)
        card_soup = BeautifulSoup(card_html, 'html.parser')
        # The card_html is an <article> tag.
        # Append it to the grid
        grid.append(card_soup)
        
    # Format and Save
    write_file(INDEX_FILE, soup.prettify())
    print("Updated index.html with latest posts.")


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
        html += create_card_html(post)
    
    html += '''
        </div>
    </div>
    '''
    return BeautifulSoup(html, 'html.parser')

def generate_json_ld(soup, filename, is_blog=True, title=None, desc=None, posts=None):
    """
    Generate JSON-LD script tag.
    Includes BreadcrumbList, BlogPosting/WebPage, and ItemList (for blog index).
    """
    domain = "https://nfhezu.top"
    
    clean_fn = clean_link(filename)
    if clean_fn == 'index':
        clean_fn = ''
    
    if is_blog:
        url = f"{domain}/blog/{clean_fn}"
        
        # Check if it is the blog index page
        is_blog_index = (clean_fn == '')
        
        if is_blog_index:
            # Blog Index Page: Breadcrumbs, CollectionPage, and ItemList
            breadcrumb_items = [
                {"@type": "ListItem", "position": 1, "name": "首页", "item": domain + "/"},
                {"@type": "ListItem", "position": 2, "name": "探索发现", "item": url}
            ]
            
            main_schema = {
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "headline": title,
                "url": url,
                "description": desc or title,
                "publisher": {
                    "@type": "Organization",
                    "name": "NFhezu",
                    "logo": {
                        "@type": "ImageObject",
                        "url": f"{domain}/logo.png"
                    }
                }
            }
            
            schema_objects = [
                {
                    "@context": "https://schema.org",
                    "@type": "BreadcrumbList",
                    "itemListElement": breadcrumb_items
                },
                main_schema
            ]

            # Add ItemList if posts are available
            if posts:
                item_list_elements = []
                for idx, post in enumerate(posts, 1):
                    item_list_elements.append({
                        "@type": "ListItem",
                        "position": idx,
                        "url": f"{domain}{post['url']}",
                        "name": post['title']
                    })
                
                item_list_schema = {
                    "@context": "https://schema.org",
                    "@type": "ItemList",
                    "itemListElement": item_list_elements
                }
                schema_objects.append(item_list_schema)

        else:
            # Blog Post: 3 levels, Type BlogPosting
            breadcrumb_items = [
                {"@type": "ListItem", "position": 1, "name": "首页", "item": domain + "/"},
                {"@type": "ListItem", "position": 2, "name": "探索发现", "item": domain + "/blog/"},
                {"@type": "ListItem", "position": 3, "name": title, "item": url}
            ]
            
            main_schema = {
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
            
            schema_objects = [
                {
                    "@context": "https://schema.org",
                    "@type": "BreadcrumbList",
                    "itemListElement": breadcrumb_items
                },
                main_schema
            ]
    else:
        # Root pages like privacy, disclaimer
        url = f"{domain}/{clean_fn}"
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

def rebuild_head(soup, filename, favicons, is_blog=True, posts=None):
    """
    Phase 2: Head Reconstruction
    """
    old_head = soup.head
    new_head = soup.new_tag('head')
    
    # Extract metadata for reuse
    title_tag = old_head.find('title')
    title_str = title_tag.string.strip() if title_tag and title_tag.string else filename
    
    desc_tag = old_head.find('meta', attrs={'name': 'description'})
    desc_str = desc_tag['content'].strip() if desc_tag and desc_tag.get('content') else ''
    
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

    # --- Group B: SEO Core ---
    if desc_tag:
        new_head.append(desc_tag)
    
    if keywords_tag:
        new_head.append(keywords_tag)
        
    # Canonical
    clean_fn = clean_link(filename)
    if clean_fn == 'index':
        clean_fn = ''

    if is_blog:
        canonical_url = f"https://nfhezu.top/blog/{clean_fn}"
    else:
        canonical_url = f"https://nfhezu.top/{clean_fn}"
        
    canonical = soup.new_tag('link', rel="canonical", href=canonical_url)
    new_head.append(canonical)

    # --- Group C: Indexing & Geo ---
    new_head.append(soup.new_tag('meta', attrs={"name": "robots", "content": "index, follow"}))
    new_head.append(soup.new_tag('meta', attrs={"http-equiv": "content-language", "content": "zh-CN"}))
    
    # Hreflang Matrix
    new_head.append(soup.new_tag('link', rel="alternate", href=canonical_url, hreflang="x-default"))
    new_head.append(soup.new_tag('link', rel="alternate", href=canonical_url, hreflang="zh"))
    new_head.append(soup.new_tag('link', rel="alternate", href=canonical_url, hreflang="zh-CN"))

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

    # --- Group E: Structured Data ---
    # Generate fresh JSON-LD
    json_ld_tag = generate_json_ld(soup, filename, is_blog=is_blog, title=title_str, desc=desc_str, posts=posts)
    new_head.append(json_ld_tag)

    soup.head.replace_with(new_head)
    return soup

def process_file(file_path, assets, all_posts, is_blog=True, inject_recs=True):
    filename = os.path.basename(file_path)
    print(f"Processing {filename}...")
    
    content = read_file(file_path)
    soup = BeautifulSoup(content, 'html.parser')
    
    # --- Phase 2: Head Reconstruction ---
    # Pass all_posts to rebuild_head for JSON-LD generation
    soup = rebuild_head(soup, filename, assets['favicons'], is_blog=is_blog, posts=all_posts)
    
    # --- Fix Breadcrumb HTML (for audit) ---
    soup = ensure_breadcrumb_html(soup, is_blog=is_blog)
    
    # --- Phase 3: Injection ---
    
    # 1. Layout Sync (Nav & Footer)
    old_nav = soup.find('nav', id='main-nav') or soup.find('nav')
    if old_nav:
        import copy
        new_nav = copy.copy(assets['nav'])
        
        # Adjust links and remove blockers
        for a in new_nav.find_all('a'):
            href = a.get('href', '')
            
            # Fix Home links
            if href == '#' or href == '/#':
                a['href'] = '/'
            elif href.startswith('#'):
                a['href'] = '/' + href
                
            # Remove onclick handlers that prevent navigation (e.g. scrollTo)
            if a.has_attr('onclick'):
                del a['onclick']
        
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
            
            # Fix Home links
            if href == '#' or href == '/#':
                a['href'] = '/'
            elif href.startswith('#'):
                a['href'] = '/' + href
                
            # Remove onclick handlers
            if a.has_attr('onclick'):
                del a['onclick']
        
        old_footer.replace_with(new_footer)
    else:
        if soup.body:
            soup.body.append(assets['footer'])
            
    # 3. Smart Recommendation Injection (Only for Blog Articles)
    if is_blog and inject_recs:
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
    write_file(file_path, soup.prettify())
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
    
    # Update Homepage with latest blog posts
    update_index_html(all_posts)
    
    # Process Blog Files
    if os.path.exists(BLOG_DIR):
        for filename in os.listdir(BLOG_DIR):
            if not filename.endswith('.html'):
                continue
            
            file_path = os.path.join(BLOG_DIR, filename)
            
            # Treat index.html in blog special: it is a blog page but not an article
            # So we process it but don't inject recommendations
            if filename == 'index.html':
                 # Passing is_blog=False prevents recommendation injection
                 # But we might want is_blog=True for breadcrumbs? 
                 # Let's check ensure_breadcrumb_html. 
                 # It adds "Blog" link if is_blog=True. 
                 # For blog/index.html, we probably don't need "Home > Blog > Blog".
                 # So is_blog=False might be safer for breadcrumbs too (Home > Title).
                 # Wait, for blog/index.html title is "探索发现...". 
                 # If is_blog=False: Home > 探索发现...
                 # If is_blog=True: Home > Blog > 探索发现...
                 # Actually, let's look at process_file's recommendation logic.
                 # It checks `if is_blog: article = soup.find('article')`.
                 # blog/index.html likely doesn't have an <article> tag for content, 
                 # or if it does, we don't want to inject there.
                 # Let's try is_blog=True but assume it handles itself or we modify process_file.
                 
                 # Simpler approach: 
                 # We want to format it and update header/nav/footer.
                 # We DON'T want recommendations.
                 # We want breadcrumbs to be correct.
                 
                 # Let's inspect blog/index.html content to see if it has <article>.
                 # Previous read shows it has <div id="articlesGrid"> but maybe not <article> wrapper for main content.
                 # Ah, the cards are <article> tags.
                 # process_file finds `soup.find('article')` which finds the *first* article.
                 # If we run it on blog/index.html, it might inject recommendations into the first card!
                 # That would be bad.
                 
                 # So we MUST skip recommendation injection for index.html.
                 # Let's modify process_file to take an optional `inject_recs` param, default True.
                 process_file(file_path, assets, all_posts, is_blog=True, inject_recs=False)
            else:
                 process_file(file_path, assets, all_posts, is_blog=True, inject_recs=True)
            
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
