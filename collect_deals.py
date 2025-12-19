import requests
from bs4 import BeautifulSoup
import csv
import re
import os
import sys
import time

# --- 엄마 추천 키워드 (유치원~고등학생 타겟) ---
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
    p = platform.lower()
    if '쿠팡' in p: return 'red'
    if '네이버' in p or 'n쇼핑' in p: return 'green'
    if '11번가' in p or 'g마켓' in p or '지마켓' in p or '옥션' in p: return 'red'
    return 'blue'

def extract_price(title):
    match = re.search(r'([\d,]+)원', title)
    if match:
        price_str = match.group(1).replace(',', '')
        return int(price_str) if price_str.isdigit() else 0
    return 0

def collect_from_ppomppu():
    """뽐뿌 핫딜 게시판 수집 (보안 우회 및 다중 셀렉터 적용)"""
    url = "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu"
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Cache-Control': 'no-cache'
    }
    
    try:
        print(f"🌐 뽐뿌 서버 접속 시도 중...")
        response = session.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        
        # 인코딩 강제 설정 (뽐뿌 특유의 한글 깨짐 방지)
        if response.encoding.lower() == 'iso-8859-1':
            response.encoding = 'euc-kr'
        else:
            response.encoding = response.apparent_encoding
            
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"❌ 접속 실패: {e}")
        return []
    
    collected_data = []
    
    # 1단계: 기본 셀렉터 (list_title 클래스)
    title_elements = soup.find_all(['font', 'span', 'a'], class_='list_title')
    
    # 2단계: 실패 시 백업 셀렉터 (제목 링크 패턴 분석)
    if not title_elements:
        print("⚠️ 기본 셀렉터 실패. 백업 셀렉터 가동...")
        title_elements = soup.select('a > font') or soup.select('td.name a')

    print(f"🔎 후보 항목 {len(title_elements)}개 발견. 데이터 파싱 중...")

    for title_tag in title_elements:
        try:
            # 게시글 행(TR) 찾기
            parent_tr = title_tag.find_parent('tr')
            if not parent_tr: continue
            
            # 링크 태그 및 텍스트 추출
            link_tag = title_tag if title_tag.name == 'a' else title_tag.find_parent('a')
            if not link_tag or not link_tag.get('href'): continue
            
            full_title = title_tag.get_text(strip=True)
            if len(full_title) < 5: continue # 너무 짧은 제목은 광고/공지일 확률 높음

            # 공지사항 및 광고글 제외 (게시글 번호가 숫자가 아닌 경우)
            num_td = parent_tr.find('td', class_='eng v_middle')
            if num_td:
                num_text = num_td.get_text(strip=True)
                # 공지 아이콘이 있거나 숫자가 아니면 제외
                if num_td.find('img') or not num_text.isdigit():
                    continue

            # 상세 링크 완성
            href = link_tag['href']
            link = "https://www.ppomppu.co.kr/zboard/" + href if not href.startswith('http') else href
            
            # 플랫폼 추출 [플랫폼]
            platform = "기타"
            p_match = re.search(r'\[(.*?)\]', full_title)
            if p_match:
                platform = p_match.group(1)
            
            # 가격 및 상품명 정제
            price = extract_price(full_title)
            product_name = re.sub(r'\[.*?\]', '', full_title).strip()
            product_name = re.sub(r'\(.*?\)', '', product_name).strip()
            
            # --- 뱃지 로직 (엄마 추천 적용) ---
            badge = "NEW"
            if any(keyword in product_name for keyword in RECOMMENDED_KEYWORDS):
                badge = "엄마 추천"
            elif price > 100000:
                badge = "HOT"
            
            # 썸네일 이미지 추출
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
            
            if len(collected_data) >= 25: break # 최대 25개
            
        except Exception:
            continue
            
    return collected_data

def save_to_csv(data):
    """수집 데이터를 deals.csv로 저장"""
    keys = ["category", "platform", "productName", "currentPrice", "originalPrice", "badge", "sourceSite", "link", "image", "color"]
    try:
        if not data:
            print("⚠️ 수집된 데이터가 없습니다. 중단합니다.")
            sys.exit(1)

        with open('deals.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"✅ 완료: {len(data)}개의 항목이 업데이트되었습니다.")
    except Exception as e:
        print(f"❌ 저장 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 실시간 핫딜 수집 및 '엄마 추천' 필터링 가동...")
    deals = collect_from_ppomppu()
    if deals:
        save_to_csv(deals)
    else:
        print("❌ 데이터 수집에 완전히 실패했습니다.")
        sys.exit(1)
