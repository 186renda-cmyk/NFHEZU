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
BLOG_INDEX_FILE = os.path.join(BLOG_DIR, 'index.html')
SITEMAP_FILE = os.path.join(PROJECT_ROOT, 'sitemap.xml')

# Manual Metadata for consistency
POST_METADATA = {
    'how-to-change-netflix-language-to-chinese.html': {'date': '2026-01-30'},
    'netflix-best-movies-shows.html': {'date': '2026-01-28'},
    'netflix-buying-guide.html': {'date': '2026-01-25'},
    'how-to-subscribe-netflix-in-china.html': {'date': '2026-01-20'},
    'how-to-watch-netflix-in-china.html': {'date': '2026-01-15'},
    'best-netflix-region-guide.html': {'date': '2026-01-10'},
    'netflix-content-library-guide.html': {'date': '2026-01-05'},
    'how-to-watch-netflix-on-devices.html': {'date': '2026-01-01'}
}

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
    Handles URLs with hashes or query parameters.
    """
    if not url:
        return url
    
    # Skip external links, anchors, and data URIs
    if url.startswith(('http:', 'https:', '#', 'data:', 'mailto:', 'tel:')):
        return url
    
    # Split hash/query
    main_url = url
    suffix = ''
    if '#' in url:
        parts = url.split('#', 1)
        main_url = parts[0]
        suffix = '#' + parts[1]
    elif '?' in url:
        parts = url.split('?', 1)
        main_url = parts[0]
        suffix = '?' + parts[1]

    # List of extensions to preserve
    preserve_exts = ['.ico', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.css', '.js', '.xml', '.txt', '.json']
    
    # Check if it has an extension that should be preserved
    for ext in preserve_exts:
        if main_url.lower().endswith(ext):
            return url
            
    # Remove .html or .htm suffix
    main_url = re.sub(r'\.html?$', '', main_url, flags=re.IGNORECASE)
    
    return main_url + suffix

def process_links(soup, is_blog=False):
    """
    Process all a[href] and img[src] to remove .html suffix where appropriate.
    Also fixes relative links to absolute paths.
    """
    for tag in soup.find_all(['a', 'link', 'img', 'script']):
        # Handle href
        if tag.has_attr('href'):
            url = tag['href']
            
            # Fix relative links
            if is_blog and url and not url.startswith(('http:', 'https:', '#', 'data:', 'mailto:', 'tel:', '/')):
                if url.startswith('../'):
                    url = '/' + url[3:]
                elif url == 'index' or url == 'index.html':
                    url = '/blog/'
                else:
                    url = '/blog/' + url
            
            # Fix /index
            if url == '/index' or url == '/index.html':
                url = '/'
            elif url.startswith('/index.html#'):
                url = '/#' + url[12:]
            elif url.startswith('/index#'):
                url = '/#' + url[7:]

            # Fix known homepage anchors that might have been malformed
            known_anchors = ['platforms', 'compare', 'guide', 'faq', 'reviews']
            for anchor in known_anchors:
                if url == f'/{anchor}':
                    url = f'/#{anchor}'

            tag['href'] = clean_link(url)
            
            # Add rel="nofollow noopener noreferrer" to external links
            href = tag['href']
            if href and (href.startswith('http://') or href.startswith('https://')):
                # Check if it's an external link (not nfhezu.top)
                if 'nfhezu.top' not in href:
                    rel = tag.get('rel', [])
                    if isinstance(rel, str):
                        rel = rel.split()
                    
                    # Add necessary values if not present
                    for val in ['nofollow', 'noopener', 'noreferrer']:
                        if val not in rel:
                            rel.append(val)
                    
                    tag['rel'] = rel
        
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
            # Prioritize manual metadata, then fallback to file mtime
            if filename in POST_METADATA:
                date_str = POST_METADATA[filename]['date']
                dt = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                mtime = dt.timestamp()
            else:
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
    elif 'subscribe' in fn or 'pay' in fn or '支付' in fn or 'how-to' in fn or 'tutorial' in fn or 'guide' in fn:
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
    Generate a single card HTML (Clean SaaS Design)
    Matches the design in blog/index.html
    """
    theme = get_theme(post['filename'])
    
    return f'''
    <article class="group relative h-full bg-[#121212] hover:bg-[#1a1a1a] rounded-2xl overflow-hidden border border-white/5 {theme['border']} transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl hover:shadow-black/50 flex flex-col">
        <!-- Hover Gradient Effect -->
        <div class="absolute inset-0 bg-gradient-to-br {theme['gradient']} opacity-0 group-hover:opacity-10 transition-opacity duration-500"></div>
        
        <a href="{post['url']}" class="block flex-1 no-underline z-10 flex flex-col p-5">
            <!-- Header: Icon & Tag -->
            <div class="flex items-center justify-between mb-3">
                <div class="{theme['blur_color']} w-8 h-8 rounded-lg flex items-center justify-center text-gray-300 group-hover:text-white transition-colors">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        {theme['icon']}
                    </svg>
                </div>
                <span class="text-[10px] font-bold tracking-wider uppercase {theme['tag_bg']} bg-opacity-20 text-gray-300 px-2 py-0.5 rounded-full border border-white/5 group-hover:border-white/10 transition-colors">
                    {theme['tag_text']}
                </span>
            </div>
            
            <!-- Content -->
            <h3 class="text-base font-bold text-white mb-2 line-clamp-2 leading-snug group-hover:text-gray-100 transition-colors">
                {post['title']}
            </h3>
            
            <p class="text-gray-400 text-xs line-clamp-3 leading-relaxed mb-4 flex-1">
                {post['description']}
            </p>
            
            <!-- Footer: CTA Arrow -->
            <div class="flex items-center text-[10px] font-medium text-gray-500 group-hover:text-white transition-colors mt-auto pt-3 border-t border-white/5 group-hover:border-white/10">
                <span>阅读全文</span>
                <svg class="w-3 h-3 ml-1 transform group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
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
        grid.append(card_soup)
        
    # Format and Save
    write_file(INDEX_FILE, soup.prettify())
    print("Updated index.html with latest posts.")

def update_blog_index_html(all_posts):
    """
    Update blog/index.html with ALL posts.
    """
    print(f"Updating {BLOG_INDEX_FILE}...")
    if not os.path.exists(BLOG_INDEX_FILE):
        print("Error: blog/index.html not found.")
        return

    content = read_file(BLOG_INDEX_FILE)
    soup = BeautifulSoup(content, 'html.parser')
    
    # Find the articles grid container
    grid = soup.find('div', id='articlesGrid')
    if not grid:
        print("Warning: #articlesGrid not found in blog/index.html")
        return
        
    # Clear existing cards
    grid.clear()
    
    # Generate new cards for ALL posts
    for post in all_posts:
        card_html = create_card_html(post)
        card_soup = BeautifulSoup(card_html, 'html.parser')
        grid.append(card_soup)
        
    # Format and Save
    write_file(BLOG_INDEX_FILE, soup.prettify())
    print("Updated blog/index.html with all posts.")

def generate_recommendations(current_filename, all_posts):
    """
    Generate HTML for recommended reading (random 4 posts excluding current).
    """
    others = [p for p in all_posts if p['filename'] != current_filename and p['filename'] != 'how-to-change-netflix-language-to-chinese.html']
    
    # User requested 4 cards
    count = 4
    if len(others) < count:
        recs = others
    else:
        recs = random.sample(others, count)
        
    if not recs:
        return None

    # Use lg:grid-cols-4 for 4 cards
    html = '''
    <div class="mt-16 pt-8 border-t border-white/10 recommendation-section">
        <h3 class="text-xl font-bold text-white mb-6 flex items-center gap-2">
            <span class="w-1 h-6 bg-netflix-red rounded-full shadow-[0_0_12px_rgba(229,9,20,0.6)]"></span>
            推荐阅读
        </h3>
        <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
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
    """
    domain = "https://nfhezu.top"
    
    clean_fn = clean_link(filename)
    if clean_fn == 'index':
        clean_fn = ''
    
    if is_blog:
        url = f"{domain}/blog/{clean_fn}"
        is_blog_index = (clean_fn == '')
        
        if is_blog_index:
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
            breadcrumb_items = [
                {"@type": "ListItem", "position": 1, "name": "首页", "item": domain + "/"},
                {"@type": "ListItem", "position": 2, "name": "探索发现", "item": domain + "/blog/"},
                {"@type": "ListItem", "position": 3, "name": title, "item": url}
            ]
            
            main_schema = {
                "@context": "https://schema.org",
                "@type": "BlogPosting",
                "headline": title,
                "image": f"{domain}/images/netflix-experience.png",
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
                "datePublished": datetime.date.today().isoformat(),
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
    """
    navs = soup.find_all('nav')
    breadcrumb_nav = None
    
    for nav in navs:
        if nav.get('id') == 'main-nav':
            continue
        if "首页" in nav.get_text():
            breadcrumb_nav = nav
            break
            
    if breadcrumb_nav:
        breadcrumb_nav['aria-label'] = 'breadcrumb'
    else:
        main = soup.find('main')
        if main:
            new_nav = soup.new_tag('nav', attrs={'aria-label': 'breadcrumb', 'class': 'flex mb-8 text-xs text-slate-500 font-medium tracking-wide uppercase'})
            
            link_home = soup.new_tag('a', href='/', attrs={'class': 'hover:text-slate-300 transition'})
            link_home.string = "首页"
            new_nav.append(link_home)
            
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
            
            current = soup.new_tag('span', attrs={'class': 'text-slate-300'})
            current.string = "当前页面" 
            new_nav.append(current)
            
            main.insert(0, new_nav)
            
    return soup

def ensure_author_date_visible(soup, mtime):
    """
    Ensure the article header contains visible Author and Date information.
    """
    header = soup.find('header')
    if not header:
        return soup
        
    # Check if author/date block exists (by checking for time tag or specific class)
    if header.find('time'):
        return soup
        
    # Create the block
    dt = datetime.datetime.fromtimestamp(mtime)
    date_str = dt.strftime('%Y-%m-%d')
    
    html = f'''
    <div class="flex items-center gap-4 text-sm text-gray-400 border-b border-white/10 pb-8 mt-6">
         <div class="flex items-center gap-3">
             <div class="w-10 h-10 rounded-full bg-gradient-to-br from-[#E50914] to-black border border-white/10 flex items-center justify-center text-white font-bold text-xs shadow-lg relative overflow-hidden group">
                 <span class="relative z-10">NF</span>
                 <div class="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
             </div>
             <div>
                 <span class="text-white font-bold block">NFhezu 编辑部</span>
                 <span class="text-xs text-[#E50914]">资深流媒体观察员</span>
             </div>
         </div>
         <div class="h-8 w-px bg-white/10 mx-2"></div>
         <div class="flex flex-col gap-0.5">
             <time datetime="{date_str}" class="text-gray-300 font-medium">{date_str}</time>
             <span class="text-xs text-gray-500">最后更新</span>
         </div>
    </div>
    '''
    
    block_soup = BeautifulSoup(html, 'html.parser')
    header.append(block_soup)
    return soup

def rebuild_head(soup, filename, favicons, is_blog=True, posts=None):
    """
    Phase 2: Head Reconstruction
    """
    old_head = soup.head
    new_head = soup.new_tag('head')
    
    title_tag = old_head.find('title')
    title_str = title_tag.string.strip() if title_tag and title_tag.string else filename
    
    desc_tag = old_head.find('meta', attrs={'name': 'description'})
    desc_str = desc_tag['content'].strip() if desc_tag and desc_tag.get('content') else ''
    
    keywords_tag = old_head.find('meta', attrs={'name': 'keywords'})
    
    new_head.append(soup.new_tag('meta', charset="utf-8"))
    new_head.append(soup.new_tag('meta', attrs={"name": "viewport", "content": "width=device-width, initial-scale=1.0"}))
    
    if title_tag:
        new_head.append(title_tag)
    else:
        new_title = soup.new_tag('title')
        new_title.string = filename
        new_head.append(new_title)

    if desc_tag:
        new_head.append(desc_tag)
    
    if keywords_tag:
        new_head.append(keywords_tag)
        
    clean_fn = clean_link(filename)
    if clean_fn == 'index':
        clean_fn = ''

    if is_blog:
        canonical_url = f"https://nfhezu.top/blog/{clean_fn}"
    else:
        canonical_url = f"https://nfhezu.top/{clean_fn}"
        
    canonical = soup.new_tag('link', rel="canonical", href=canonical_url)
    new_head.append(canonical)

    new_head.append(soup.new_tag('meta', attrs={"name": "robots", "content": "index, follow"}))
    new_head.append(soup.new_tag('meta', attrs={"http-equiv": "content-language", "content": "zh-CN"}))
    
    new_head.append(soup.new_tag('link', rel="alternate", href=canonical_url, hreflang="x-default"))
    new_head.append(soup.new_tag('link', rel="alternate", href=canonical_url, hreflang="zh"))
    new_head.append(soup.new_tag('link', rel="alternate", href=canonical_url, hreflang="zh-CN"))

    for icon in favicons:
        import copy
        new_head.append(copy.copy(icon))
        
    for tag in old_head.find_all(['link', 'script', 'style']):
        if tag.name == 'link' and 'icon' in str(tag.get('rel', '')):
            continue
        if tag.name == 'link' and tag.get('rel') == ['canonical']:
            continue
        if tag.name == 'link' and tag.get('rel') == ['alternate']:
            continue
        if tag.name == 'script' and tag.get('type') == 'application/ld+json':
            continue
        new_head.append(tag)

    json_ld_tag = generate_json_ld(soup, filename, is_blog=is_blog, title=title_str, desc=desc_str, posts=posts)
    new_head.append(json_ld_tag)

    soup.head.replace_with(new_head)
    return soup

def generate_sitemap(all_posts):
    """
    Generate sitemap.xml
    """
    print(f"Generating {SITEMAP_FILE}...")
    
    domain = "https://nfhezu.top"
    today = datetime.date.today().isoformat()
    
    # Start XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # 1. Homepage
    xml += f'''  <url>
    <loc>{domain}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
'''
    
    # 2. Blog Index
    xml += f'''  <url>
    <loc>{domain}/blog/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
'''

    # 3. Blog Posts
    for post in all_posts:
        dt = datetime.datetime.fromtimestamp(post['mtime'])
        date_str = dt.strftime('%Y-%m-%d')
        url = f"{domain}{post['url']}"
        xml += f'''  <url>
    <loc>{url}</loc>
    <lastmod>{date_str}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
'''

    # 4. Other Pages (Privacy, Disclaimer)
    others = ['privacy.html', 'disclaimer.html']
    for filename in others:
        if os.path.exists(os.path.join(PROJECT_ROOT, filename)):
            url = f"{domain}/{clean_link(filename)}"
            xml += f'''  <url>
    <loc>{url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
'''
            
    xml += '</urlset>'
    write_file(SITEMAP_FILE, xml)
    print("Sitemap generated.")

def fix_styles(soup):
    """
    Inject CSS to fix prose styles interfering with recommendation cards.
    """
    style_tag = soup.find('style')
    if not style_tag:
        style_tag = soup.new_tag('style')
        if soup.head:
            soup.head.append(style_tag)
    
    css_fix = """
        /* Fix for recommendation cards inheriting prose styles */
        .recommendation-section a { 
            text-decoration: none !important; 
            color: inherit !important; 
            font-weight: inherit !important;
        }
        .recommendation-section a:hover { 
            color: inherit !important; 
            text-decoration: none !important;
        }
        /* Fix layout issues */
        .recommendation-section article {
            height: 100%;
        }
    """
    
    if style_tag.string:
        if "Fix for recommendation cards" not in style_tag.string:
            style_tag.string += css_fix
    else:
        style_tag.string = css_fix
        
    return soup

def process_file(file_path, assets, all_posts, is_blog=True, inject_recs=True):
    filename = os.path.basename(file_path)
    print(f"Processing {filename}...")
    
    content = read_file(file_path)
    soup = BeautifulSoup(content, 'html.parser')
    
    soup = rebuild_head(soup, filename, assets['favicons'], is_blog=is_blog, posts=all_posts)
    soup = ensure_breadcrumb_html(soup, is_blog=is_blog)
    
    # Fix styles for all blog posts
    if is_blog:
        soup = fix_styles(soup)
    
    # Inject Author/Date for Blog Articles (not index)
    if is_blog and inject_recs:
        mtime = os.path.getmtime(file_path)
        soup = ensure_author_date_visible(soup, mtime)
    
    old_nav = soup.find('nav', id='main-nav') or soup.find('nav')
    if old_nav:
        import copy
        new_nav = copy.copy(assets['nav'])
        for a in new_nav.find_all('a'):
            href = a.get('href', '')
            if href == '#' or href == '/#':
                a['href'] = '/'
            elif href.startswith('#'):
                a['href'] = '/' + href
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
            if href == '#' or href == '/#':
                a['href'] = '/'
            elif href.startswith('#'):
                a['href'] = '/' + href
            if a.has_attr('onclick'):
                del a['onclick']
        old_footer.replace_with(new_footer)
    else:
        if soup.body:
            soup.body.append(assets['footer'])
            
    if is_blog and inject_recs:
        article = soup.find('article')
        if article:
            for div in article.find_all('div', class_='recommendation-section'):
                 div.decompose()
            
            for div in article.find_all('div', class_='mt-16 pt-10 border-t border-white/10'):
                 if "推荐阅读" in div.get_text():
                     div.decompose()
            
            for div in article.find_all('div', class_='mt-12 pt-8 border-t border-white/10'):
                 if "推荐阅读" in div.get_text():
                     div.decompose()
                     
            for h3 in article.find_all('h3'):
                if "推荐阅读" in h3.get_text():
                    parent = h3.parent
                    if parent.name == 'div' and ('border-t' in parent.get('class', [])):
                        parent.decompose()

            # Remove in-content recommendation links (e.g. "👉 延伸阅读：...")
            for p in article.find_all('p'):
                text = p.get_text()
                if "延伸阅读" in text or "推荐阅读" in text:
                    if p.find('a'):
                        p.decompose()

            recommendations = generate_recommendations(filename, all_posts)
            if recommendations:
                article.append(recommendations)
            
    soup = process_links(soup, is_blog=is_blog)
    write_file(file_path, soup.prettify())
    print(f"Saved {filename}")

def main():
    print("Starting Build Process...")
    
    if not os.path.exists(INDEX_FILE):
        print("Error: index.html not found.")
        return

    assets = extract_assets()
    if not assets:
        return
    
    all_posts = get_blog_posts()
    
    # 1. Update Homepage Article Cards
    update_index_html(all_posts)
    
    # 2. Update Blog Index Page (New)
    update_blog_index_html(all_posts)
    
    # 3. Generate Sitemap (New)
    generate_sitemap(all_posts)
    
    # 4. Process All Blog Posts
    if os.path.exists(BLOG_DIR):
        for filename in os.listdir(BLOG_DIR):
            if not filename.endswith('.html'):
                continue
            
            file_path = os.path.join(BLOG_DIR, filename)
            
            if filename == 'index.html':
                 # Skip recommendations and author/date injection for index
                 process_file(file_path, assets, all_posts, is_blog=True, inject_recs=False)
            else:
                 process_file(file_path, assets, all_posts, is_blog=True, inject_recs=True)
            
    # 5. Process Root Pages
    root_files_to_process = ['privacy.html', 'disclaimer.html']
    for filename in root_files_to_process:
        file_path = os.path.join(PROJECT_ROOT, filename)
        if os.path.exists(file_path):
            process_file(file_path, assets, all_posts, is_blog=False)
    
    print("Build Complete.")

if __name__ == "__main__":
    main()