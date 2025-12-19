import requests
from bs4 import BeautifulSoup
import csv
import re
import os
import sys
import time

# --- 추천 필터링 키워드 (유치원/초/중/고 학생용 및 엄마 추천) ---
# 이 키워드가 포함된 상품은 자동으로 '엄마 추천' 뱃지가 붙습니다.
# 건우가 좋아하는 곤충, 생물, 피규어 관련 키워드도 포함되어 있습니다.
RECOMMENDED_KEYWORDS = [
    '유치원', '초등학교', '중학교', '고등학생', '입학', '신학기', '어린이날',
    '장난감', '교구', '학용품', '필기구', '백팩', '책가방',
    '문제집', '참고서', '스터디플래너', '독서실', '수험생',
    '태블릿', '아이패드', '갤럭시탭', '인강용', '노트북',
    '운동화', '후드티', '패딩', '트레이닝복', '조거팬츠',
    '보드게임', '슬라임', '닌텐도', '레고', '피규어', '도감',
    '곤충', '생물', '사슴벌레', '장수풍뎅이', '관찰키트', '자연관찰'
]

def get_platform_color(platform):
    """플랫폼 이름에 따라 UI에 표시될 테마 색상을 결정합니다."""
    p = platform.lower()
    if '쿠팡' in p: return 'red'
    if '네이버' in p or 'n쇼핑' in p: return 'green'
    if '11번가' in p or 'g마켓' in p or '지마켓' in p or '옥션' in p: return 'red'
    if '티몬' in p or '위메프' in p: return 'blue'
    return 'blue'

def extract_price(title):
    """제목 문자열에서 가격 숫자를 추출합니다 (예: 15,900원 -> 15900)."""
    match = re.search(r'([\d,]+)원', title)
    if match:
        price_str = match.group(1).replace(',', '')
        if price_str.isdigit():
            return int(price_str)
    return 0

def collect_from_ppomppu():
    """뽐뿌 핫딜 게시판 실시간 수집 로직"""
    url = "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu"
    
    # 봇 차단을 피하기 위한 브라우저 헤더 설정
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        print(f"🌐 뽐뿌 서버 접속 시도 중...")
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        # 뽐뿌 특유의 인코딩 처리
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"❌ 접속 실패: {e}")
        return []
    
    collected_data = []
    # 게시글 제목 태그 추출 (font 혹은 span 태그에 list_title 클래스 사용)
    title_elements = soup.find_all(['font', 'span'], class_='list_title')
    
    print(f"🔎 총 {len(title_elements)}개의 항목 분석 시작...")

    for title_tag in title_elements:
        try:
            # 해당 행(tr) 및 링크 태그 찾기
            parent_tr = title_tag.find_parent('tr')
            if not parent_tr: continue
            
            link_tag = title_tag.find_parent('a')
            if not link_tag: continue
            
            full_title = title_tag.get_text(strip=True)
            if not full_title: continue

            # 공지사항 및 광고글 제외 (게시글 번호가 숫자가 아닌 경우)
            num_td = parent_tr.find('td', class_='eng v_middle')
            if num_td:
                num_text = num_td.get_text(strip=True)
                if not num_text.isdigit(): continue

            # 상세 링크 완성
            href = link_tag['href']
            link = "https://www.ppomppu.co.kr/zboard/" + href if not href.startswith('http') else href
            
            # 플랫폼 추출 (예: [쿠팡])
            platform = "기타"
            p_match = re.search(r'\[(.*?)\]', full_title)
            if p_match:
                platform = p_match.group(1)
            
            # 가격 추출 및 상품명 정제
            price = extract_price(full_title)
            product_name = re.sub(r'\[.*?\]', '', full_title).strip()
            product_name = re.sub(r'\(.*?\)', '', product_name).strip()
            
            # --- 뱃지 결정 로직 (엄마 추천 적용) ---
            badge = "NEW"
            if any(keyword in product_name for keyword in RECOMMENDED_KEYWORDS):
                badge = "엄마 추천"
            elif price > 100000:
                badge = "HOT"
            
            # 이미지 추출
            img_tag = parent_tr.find('img', class_='thumb_border')
            img_url = ""
            if img_tag and img_tag.get('src'):
                src = img_tag.get('src')
                img_url = "https:" + src if src.startswith('//') else src
            else:
                img_url = f"https://placehold.co/80x80/f1f5f9/94a3b8?text={platform[:1]}"

            collected_data.append({
                "category": "핫딜",
                "platform": platform,
                "productName": product_name,
                "currentPrice": str(price),
                "originalPrice": str(int(price * 1.3)) if price > 0 else "0",
                "badge": badge,
                "sourceSite": "뽐뿌",
                "link": link,
                "image": img_url,
                "color": get_platform_color(platform)
            })
            
            if len(collected_data) >= 25: break
            
        except Exception:
            continue
            
    return collected_data

def save_to_csv(data):
    """수집된 데이터를 deals.csv 파일로 저장합니다."""
    keys = ["category", "platform", "productName", "currentPrice", "originalPrice", "badge", "sourceSite", "link", "image", "color"]
    try:
        if not data:
            print("⚠️ 저장할 데이터가 없어 작업을 중단합니다.")
            sys.exit(1)

        with open('deals.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"✅ 수집 성공: {len(data)}개의 핫딜을 저장했습니다.")
    except Exception as e:
        print(f"❌ 파일 저장 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 실시간 핫딜 수집 및 '엄마 추천' 필터링 가동...")
    deals = collect_from_ppomppu()
    if deals:
        save_to_csv(deals)
    else:
        print("❌ 수집된 데이터가 없습니다.")
        sys.exit(1)
