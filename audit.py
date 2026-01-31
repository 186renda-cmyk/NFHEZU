import os
import re
import sys
import time
import concurrent.futures
import urllib.parse
from collections import defaultdict
from bs4 import BeautifulSoup
import requests
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

class SiteAuditor:
    def __init__(self, root_dir='.'):
        self.root_dir = os.path.abspath(root_dir)
        self.files = []
        self.base_url = None
        self.keywords = []
        self.internal_links_map = defaultdict(int) # target_path -> count
        self.external_links = set()
        self.orphans = []
        self.top_pages = []
        self.score = 100
        self.issues = []
        self.page_titles = {} # path -> title
        
        # Configuration
        self.ignore_paths = ['.git', 'node_modules', '__pycache__', 'MasterTool']
        self.ignore_urls_prefixes = ['/go/', 'javascript:', 'mailto:', '#']
        self.ignore_files = ['google', '404.html'] # Partial match on filename
        self.trusted_external_links = ['https://unogs.com/', 'https://unogs.com'] # Skip checking these

    def log(self, type, message):
        if type == 'SUCCESS':
            print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")
        elif type == 'ERROR':
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")
        elif type == 'WARN':
            print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} {message}")
        elif type == 'INFO':
            print(f"{Fore.BLUE}[INFO]{Style.RESET_ALL} {message}")

    def add_issue(self, type, message, deduction=0):
        self.issues.append({'type': type, 'message': message})
        self.score = max(0, self.score - deduction)
        self.log(type, message)

    def auto_configure(self):
        index_path = os.path.join(self.root_dir, 'index.html')
        if not os.path.exists(index_path):
            self.add_issue('ERROR', "Root index.html not found! Cannot auto-configure.", 100)
            return False

        try:
            with open(index_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
                # Base URL
                canonical = soup.find('link', rel='canonical')
                if canonical and canonical.get('href'):
                    self.base_url = canonical['href'].rstrip('/')
                    self.log('SUCCESS', f"Base URL detected: {self.base_url}")
                else:
                    og_url = soup.find('meta', property='og:url')
                    if og_url and og_url.get('content'):
                        self.base_url = og_url['content'].rstrip('/')
                        self.log('SUCCESS', f"Base URL detected from og:url: {self.base_url}")
                    else:
                        self.log('WARN', "Could not detect Base URL from index.html")

                # Keywords
                meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
                if meta_keywords and meta_keywords.get('content'):
                    self.keywords = [k.strip() for k in meta_keywords['content'].split(',')]
                    self.log('INFO', f"Keywords detected: {len(self.keywords)}")
                
        except Exception as e:
            self.add_issue('ERROR', f"Failed to parse index.html: {str(e)}", 100)
            return False
        
        return True

    def scan_files(self):
        for root, dirs, files in os.walk(self.root_dir):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in self.ignore_paths]
            
            for file in files:
                # Filter files
                if not file.endswith('.html'):
                    continue
                if any(ignore in file for ignore in self.ignore_files):
                    continue
                
                full_path = os.path.join(root, file)
                self.files.append(full_path)

        self.log('INFO', f"Found {len(self.files)} HTML files to audit.")

    def resolve_local_path(self, current_file_path, link_href):
        """
        Resolves a link to a local file path.
        Returns the absolute path if found, or None.
        """
        # Remove query params and hash
        link_href = link_href.split('#')[0].split('?')[0]
        if not link_href:
            return None

        # Handle absolute URLs that point to our domain
        if self.base_url and link_href.startswith(self.base_url):
            link_href = link_href[len(self.base_url):]
            if not link_href.startswith('/'):
                link_href = '/' + link_href

        # If it's still an absolute URL (external), return None (handled elsewhere)
        if link_href.startswith('http://') or link_href.startswith('https://'):
            return None

        # Handle root-relative paths
        if link_href.startswith('/'):
            # It's relative to root
            potential_path = link_href.lstrip('/')
            base_search_dir = self.root_dir
        else:
            # It's relative to current file
            potential_path = link_href
            base_search_dir = os.path.dirname(current_file_path)

        # Check exact file match
        target_path_1 = os.path.join(base_search_dir, potential_path)
        if os.path.isfile(target_path_1):
            return target_path_1
        
        # Check if it refers to a directory -> look for index.html
        target_path_2 = os.path.join(base_search_dir, potential_path, 'index.html')
        if os.path.isfile(target_path_2):
            return target_path_2
        
        # Check if it implies a .html file without extension
        target_path_3 = os.path.join(base_search_dir, potential_path + '.html')
        if os.path.isfile(target_path_3):
            return target_path_3

        return None

    def check_external_links(self):
        # Filter out trusted links
        links_to_check = [url for url in self.external_links if url not in self.trusted_external_links]
        self.log('INFO', f"Checking {len(links_to_check)} external links (skipped {len(self.external_links) - len(links_to_check)} trusted)...")
        
        def check_url(url):
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            try:
                response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
                if response.status_code == 405 or response.status_code == 403:
                    # Method Not Allowed or Forbidden, try GET
                    response = requests.get(url, headers=headers, timeout=10, stream=True)
                
                if response.status_code >= 400:
                    return url, response.status_code
            except requests.RequestException:
                return url, "Connection Error"
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_url, url) for url in links_to_check]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    url, status = result
                    self.add_issue('ERROR', f"Broken External Link: {url} (Status: {status})", 5)

    def audit_page(self, file_path):
        rel_path = os.path.relpath(file_path, self.root_dir)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                soup = BeautifulSoup(content, 'html.parser')

                # H1 Check
                h1s = soup.find_all('h1')
                if len(h1s) == 0:
                    self.add_issue('ERROR', f"Missing H1 tag in {rel_path}", 5)
                elif len(h1s) > 1:
                    self.add_issue('WARN', f"Multiple H1 tags in {rel_path}", 0) # No deduction in spec but good to warn

                # Schema Check
                schema = soup.find('script', type='application/ld+json')
                if not schema:
                    self.add_issue('WARN', f"Missing Schema (JSON-LD) in {rel_path}", 2)

                # Breadcrumb Check
                has_breadcrumb = False
                if soup.find(attrs={"aria-label": "breadcrumb"}) or soup.find(class_=lambda x: x and 'breadcrumb' in x):
                    has_breadcrumb = True
                
                # If it's not index.html, it should have breadcrumbs (heuristic)
                if os.path.basename(file_path) != 'index.html' and not has_breadcrumb:
                     # Only warn if deep structure? For now, following spec blindly might be too noisy. 
                     # Spec says: "Check if page contains...", implies warning if missing.
                     pass # Let's strictly follow requirement: just check. Spec implies warning if missing?
                     # "Breadcrumb: 检查页面是否包含..." -> usually implies requirement.
                     # But homepage usually doesn't need breadcrumb.
                     if rel_path != 'index.html':
                         self.add_issue('WARN', f"Missing Breadcrumb in {rel_path}", 0) # Warn but maybe 0 deduction to be safe unless specified? Spec says "Missing Schema (-2)", doesn't explicitly penalize Breadcrumb in "Reporting" section but mentions it in Semantics. Let's keep it 0 or small.

                # Link Analysis
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    
                    # Ignore specific patterns
                    if any(href.startswith(p) for p in self.ignore_urls_prefixes):
                        continue
                    
                    # External Links
                    if href.startswith('http://') or href.startswith('https://'):
                        # Check if it points to self
                        if self.base_url and href.startswith(self.base_url):
                            self.add_issue('WARN', f"Internal link uses absolute URL in {rel_path}: {href} -> Use /path", 2)
                            # Treat as internal for existence check
                        else:
                            self.external_links.add(href)
                            # Check rel attributes
                            rel = a.get('rel', [])
                            if 'nofollow' not in rel and 'noopener' not in rel:
                                # This is a soft check, maybe not worth an error yet, but noted in requirements
                                pass 
                            continue

                    # URL Normality Checks
                    if not href.startswith('/') and not href.startswith('#') and not href.startswith('http'):
                         self.add_issue('WARN', f"Relative path used in {rel_path}: {href} -> Use absolute path /...", 2)

                    if href.endswith('.html'):
                         self.add_issue('WARN', f".html suffix used in {rel_path}: {href} -> Use Clean URL", 2)

                    # Dead Link Check (Local)
                    target_file = self.resolve_local_path(file_path, href)
                    if target_file:
                        self.internal_links_map[target_file] += 1
                    else:
                        self.add_issue('ERROR', f"Dead Link in {rel_path}: {href}", 10)

        except Exception as e:
            self.add_issue('ERROR', f"Failed to audit {rel_path}: {str(e)}", 0)

    def analyze_equity(self):
        # Orphans
        for file_path in self.files:
            rel_path = os.path.relpath(file_path, self.root_dir)
            if rel_path == 'index.html':
                continue
            
            # Check if this file was targeted
            # internal_links_map keys are absolute paths
            if self.internal_links_map[file_path] == 0:
                self.add_issue('WARN', f"Orphan Page (No incoming links): {rel_path}", 5)

        # Top Pages
        sorted_pages = sorted(self.internal_links_map.items(), key=lambda x: x[1], reverse=True)
        self.top_pages = sorted_pages[:10]

    def run(self):
        print(f"{Fore.CYAN}Starting SEO Audit for: {self.root_dir}{Style.RESET_ALL}")
        
        if not self.auto_configure():
            return

        self.scan_files()
        
        for file_path in self.files:
            self.audit_page(file_path)
            
        self.check_external_links()
        self.analyze_equity()
        
        # Reporting
        print("\n" + "="*50)
        print(f"{Fore.CYAN}AUDIT REPORT{Style.RESET_ALL}")
        print("="*50)
        
        print(f"\n{Fore.YELLOW}Top 10 Pages by Inbound Links:{Style.RESET_ALL}")
        for path, count in self.top_pages:
            print(f"{count} links -> {os.path.relpath(path, self.root_dir)}")

        print("\n" + "-"*50)
        print(f"Final Score: {Fore.MAGENTA}{self.score}/100{Style.RESET_ALL}")
        
        if self.score < 100:
            print(f"\n{Fore.RED}Actionable Advice:{Style.RESET_ALL}")
            print("Please fix the errors above. Consider running a fix script if available.")

if __name__ == "__main__":
    auditor = SiteAuditor('.')
    auditor.run()
