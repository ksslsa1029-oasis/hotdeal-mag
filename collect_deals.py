import requests
from bs4 import BeautifulSoup
import csv
import re
import os
import time

def get_platform_color(platform):
    """Determines theme color based on platform name."""
    p = platform.lower()
    if '쿠팡' in p: return 'red'
    if '네이버' in p or 'n쇼핑' in p: return 'green'
    if '11번가' in p or 'g마켓' in p or '지마켓' in p or '옥션' in p: return 'red'
    if '티몬' in p or '위메프' in p: return 'blue'
    return 'blue'

def extract_price(title):
    """Extracts numeric price from the title string."""
    # Pattern to find numbers before '원'
    match = re.search(r'([\d,]+)원', title)
    if match:
        price_str = match.group(1).replace(',', '')
        if price_str.isdigit():
            return int(price_str)
    return 0

def collect_from_ppomppu():
    """Crawler for Ppomppu Hot Deal board with enhanced anti-block features."""
    url = "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu"
    
    session = requests.Session()
    # Updated headers to mimic a modern Chrome browser more accurately
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }
    
    try:
        print(f"🌐 Connecting to: {url}")
        response = session.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        
        # Ppomppu encoding handling: Force euc-kr if not specified
        if response.encoding.lower() == 'iso-8859-1':
            response.encoding = 'euc-kr'
        else:
            response.encoding = response.apparent_encoding
            
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return []
    
    collected_data = []
    
    # Robust Multi-layer Selector Strategy
    # 1. Primary: Standard classes used in Ppomppu
    title_elements = soup.find_all(['font', 'span'], class_='list_title')
    
    # 2. Backup: If primary fails, use CSS selectors for link patterns
    if not title_elements:
        print("⚠️ Primary selectors failed. Trying backup selectors...")
        title_elements = soup.select('a > font.list_title') or soup.select('a > span.list_title')
    
    # 3. Final Fallback: All links that look like view articles
    if not title_elements:
        print("⚠️ Trying global link search...")
        title_elements = [a for a in soup.find_all('a', href=True) if 'view.php?id=ppomppu' in a['href'] and a.get_text(strip=True)]

    if not title_elements:
        print("⚠️ No data found. Debug: Check if site is blocking or structure changed.")
        return []

    print(f"🔎 Found {len(title_elements)} potential items. Starting parsing...")

    for title_tag in title_elements:
        try:
            # Find the actual link tag
            link_tag = title_tag if title_tag.name == 'a' else title_tag.find_parent('a')
            if not link_tag or not link_tag.get('href'): continue
            
            # Find the row container (TR) to get images and IDs
            parent_tr = title_tag.find_parent('tr')
            if not parent_tr: continue
            
            full_title = title_tag.get_text(strip=True)
            if len(full_title) < 5: continue # Skip short/empty titles

            # Filter out notices/ads: Check for numeric post ID
            num_td = parent_tr.find('td', class_='eng v_middle')
            if num_td:
                num_text = num_td.get_text(strip=True)
                # Skip if the first column is an image (Notice/Ad icon)
                if num_td.find('img') or not num_text.isdigit():
                    continue

            # Extract Link
            href = link_tag['href']
            link = "https://www.ppomppu.co.kr/zboard/" + href if not href.startswith('http') else href
            
            # Extract Platform [Platform]
            platform = "기타"
            p_match = re.search(r'\[(.*?)\]', full_title)
            if p_match:
                platform = p_match.group(1)
            
            # Price and Product Name Refinement
            price = extract_price(full_title)
            product_name = re.sub(r'\[.*?\]', '', full_title).strip()
            product_name = re.sub(r'\(.*?\)', '', product_name).strip()
            
            # Image Extraction: Look for thumb_border class
            img_tag = parent_tr.find('img', class_='thumb_border')
            img_url = ""
            if img_tag and img_tag.get('src'):
                src = img_tag.get('src')
                img_url = "https:" + src if src.startswith('//') else src
            else:
                img_url = "https://placehold.co/80x80/f1f5f9/94a3b8?text=HOT"

            collected_data.append({
                "category": "핫딜",
                "platform": platform,
                "productName": product_name,
                "currentPrice": str(price),
                "originalPrice": str(int(price * 1.3)) if price > 0 else "0",
                "badge": "HOT" if price > 100000 else "NEW",
                "sourceSite": "뽐뿌",
                "link": link,
                "image": img_url,
                "color": get_platform_color(platform)
            })
            
            if len(collected_data) >= 30: break # Collect up to 30 items
            
        except Exception:
            continue
            
    return collected_data

def save_to_csv(data):
    """Saves collected data to deals.csv."""
    keys = ["category", "platform", "productName", "currentPrice", "originalPrice", "badge", "sourceSite", "link", "image", "color"]
    try:
        if not data:
            print("⚠️ No data to save. Operation aborted.")
            return

        with open('deals.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"✅ Success: {len(data)} items saved to deals.csv.")
    except Exception as e:
        print(f"❌ Save Failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Ppomppu Real-time Collector...")
    deals = collect_from_ppomppu()
    if deals:
        save_to_csv(deals)
    else:
        print("❌ No data collected. Possible block or structural change.")