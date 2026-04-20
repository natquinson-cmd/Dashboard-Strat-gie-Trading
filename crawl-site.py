#!/usr/bin/env python3
"""Crawl emilie-quinson.com and save as static HTML site."""
import os
import re
import time
from urllib.parse import urljoin, urlparse, unquote
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://emilie-quinson.com"
OUTPUT_DIR = Path("site-static")
VISITED = set()
TO_VISIT = set()
ASSETS = set()

# Pages to start from
ENTRY_POINTS = [
    "/",
    "/a-propos/",
    "/accompagnements/",
    "/interventions/",
    "/bloom/",
    "/contact/",
    "/me-soutenir/",
]

# Don't follow these
SKIP_PATTERNS = [
    "/wp-admin", "/wp-login", "/wp-json", "/feed", "?replytocom",
    "?share=", "?preview=", "/author/", "/tag/", "/category/",
    "/comments/feed", "?page_id=", "/xmlrpc.php", ".php",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Claude-Migration-Bot",
}

session = requests.Session()
session.headers.update(HEADERS)


def should_skip(url):
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "emilie-quinson.com":
        return True
    path = parsed.path + ("?" + parsed.query if parsed.query else "")
    for pattern in SKIP_PATTERNS:
        if pattern in path:
            return True
    return False


def normalize_url(url):
    """Make URL absolute and strip fragments."""
    url = url.strip()
    if not url or url.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    full = urljoin(BASE_URL, url)
    full = full.split("#")[0]
    return full


def url_to_path(url):
    """Convert URL to local file path (strip query strings for assets)."""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if path.endswith("/") or path == "":
        path = path + "index.html"
    elif "." not in Path(path).name:
        path = path + "/index.html"
    return OUTPUT_DIR / path.lstrip("/")


def save_file(path, content, is_text=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if is_text else "wb"
    encoding = "utf-8" if is_text else None
    with open(path, mode, encoding=encoding) as f:
        f.write(content)


def extract_links(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    assets = set()

    # Page links (<a href>)
    for a in soup.find_all("a", href=True):
        url = normalize_url(a["href"])
        if url and not should_skip(url):
            links.add(url)

    # Assets: <img>, <link>, <script>, <source>
    for tag in soup.find_all(["img", "link", "script", "source"]):
        attr = "src" if tag.name != "link" else "href"
        if tag.get(attr):
            url = normalize_url(tag[attr])
            if url and urlparse(url).netloc == "emilie-quinson.com":
                # Skip REST API / RSD / wlwmanifest
                pl = urlparse(url).path.lower()
                if any(s in url for s in ["/wp-json", "xmlrpc.php", "wlwmanifest"]):
                    continue
                assets.add(url)
        # data-src lazy
        if tag.get("data-src"):
            url = normalize_url(tag["data-src"])
            if url and urlparse(url).netloc == "emilie-quinson.com":
                assets.add(url)
        # srcset
        if tag.get("srcset"):
            for part in tag["srcset"].split(","):
                src = part.strip().split(" ")[0]
                url = normalize_url(src)
                if url and urlparse(url).netloc == "emilie-quinson.com":
                    assets.add(url)

    return links, assets


def rewrite_urls(html):
    """Rewrite absolute URLs to relative ones for static hosting."""
    html = html.replace("https://emilie-quinson.com/", "/")
    html = html.replace("http://emilie-quinson.com/", "/")
    # Strip ?ver=... query strings from asset URLs in HTML
    html = re.sub(r'(\.(?:css|js|png|jpg|jpeg|gif|svg|woff2?|ttf|eot|ico))\?[^"\'\s)>]*', r'\1', html)
    return html


def fetch(url):
    try:
        r = session.get(url, timeout=20)
        return r
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def crawl_page(url):
    if url in VISITED:
        return
    VISITED.add(url)
    print(f"[{len(VISITED)}] {url}")

    r = fetch(url)
    if not r or r.status_code != 200:
        return

    content_type = r.headers.get("Content-Type", "")
    if "html" in content_type:
        html = rewrite_urls(r.text)
        save_file(url_to_path(url), html, is_text=True)
        links, assets = extract_links(r.text, url)
        for link in links:
            if link not in VISITED:
                TO_VISIT.add(link)
        for asset in assets:
            ASSETS.add(asset)
    else:
        save_file(url_to_path(url), r.content, is_text=False)


def download_asset(url):
    if url in VISITED:
        return
    VISITED.add(url)
    path = url_to_path(url)
    if path.exists():
        return
    print(f"  asset: {url}")
    r = fetch(url)
    if not r or r.status_code != 200:
        return
    content_type = r.headers.get("Content-Type", "")
    if "css" in content_type or "javascript" in content_type or "html" in content_type:
        content = rewrite_urls(r.text)
        save_file(path, content, is_text=True)
        # Also extract URLs from CSS (fonts, images)
        if "css" in content_type:
            for match in re.finditer(r'url\(["\']?([^"\')]+)["\']?\)', r.text):
                asset_url = normalize_url(match.group(1))
                if asset_url and urlparse(asset_url).netloc == "emilie-quinson.com":
                    ASSETS.add(asset_url)
    else:
        save_file(path, r.content, is_text=False)


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Seed
    for entry in ENTRY_POINTS:
        TO_VISIT.add(BASE_URL + entry)

    # Crawl pages
    while TO_VISIT:
        url = TO_VISIT.pop()
        crawl_page(url)
        time.sleep(0.1)  # Be nice

    print(f"\nCrawled {len(VISITED)} pages. Downloading {len(ASSETS)} assets...")

    # Download all assets
    asset_list = list(ASSETS)
    for i, asset in enumerate(asset_list):
        download_asset(asset)
        if i % 50 == 0:
            print(f"  [{i}/{len(asset_list)}]")
        time.sleep(0.05)

    print("\nDone!")
    print(f"Total files: {sum(1 for _ in OUTPUT_DIR.rglob('*') if _.is_file())}")


if __name__ == "__main__":
    main()
