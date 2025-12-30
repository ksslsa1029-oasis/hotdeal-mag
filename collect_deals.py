import requests
from bs4 import BeautifulSoup
import csv
import re
import os
import sys
import time
import random

# --- 추천 필터링 키워드 (엄마 추천 & 건우 취향 저격) ---
# 7살 아들 건우가 좋아하는 곤충, 생물 관련 키워드와 교육용품 리스트입니다.
RECOMMENDED_KEYWORDS = [
    # 건우 맞춤형 키워드 (곤충/생물/과학/피규어)
    '사슴벌레', '장수풍뎅이', '곤충', '생물', '도감', '파브르', '표본', '과학잡지', 
    '내셔널지오그래픽', '자연관찰', '관찰키트', '현미경', '돋보기', '레고', '피규어', '공룡',
    # 유아/학생 교육용 키워드
    '유치원', '초등학교', '중학교', '고등학생', '입학', '신학기', '어린이날',
    '장난감', '교구', '학용품', '필기구', '백팩', '책가방', '문제집', '참고서',
    '태블릿', '아이패드', '갤럭시탭', '인강용', '노트북', '운동화', '트레이닝복'
]

def get_platform_color(platform):
    """플랫폼 이름에 따라 테마 색상을 결정합니다."""
    p = platform.lower()
    if '쿠팡' in p: return 'red'
    if '네이버' in p or 'n쇼핑' in p: return 'green'
    if '11번가' in p or 'g마켓' in p or '지마켓' in p or '옥션' in p: return 'red'
    return 'blue'

def extract_price(title):
    """제목 문자열에서 가격 숫자를 추출합니다 (다양한 패턴 대응)."""
    # 1. '숫자원' 형태 탐색 (예: 15,900원)
    match = re.search(r'([\d,]+)\s*원', title)
    if match:
        price_str = match.group(1).replace(',', '')
        if price_str.isdigit():
            return int(price_str)
            
    # 2. '원'이 없어도 3자리 이상의 숫자 콤마 패턴 탐색 (예: 15,900)
    match = re.search(r'([\d]{1,3}(?:,[\d]{3})+)', title)
    if match:
        price_str = match.group(1).replace(',', '')
        return int(price_str)
        
    return 0

def get_soup(url, session):
    """지정된 URL에 접속하여 BeautifulSoup 객체를 반환하며, 상세 로그를 남깁니다."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Cache-Control': 'no-cache',
        'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'DNT': '1'
    }
    
    try:
        print(f"DEBUG: {url} 접속 시도 중...")
        response = session.get(url, headers=headers, timeout=25)
        
        # 뽐뿌 특유의 euc-kr 인코딩 강제 처리
        if response.encoding and response.encoding.lower() == 'iso-8859-1':
            response.encoding = 'euc-kr'
        elif not response.encoding or response.encoding.lower() == 'utf-8':
            response.encoding = 'euc-kr'
            
        if response.status_code != 200:
            print(f"⚠️ {url} 접속 실패 (상태 코드: {response.status_code})")
            return None, ""

        return BeautifulSoup(response.text, 'html.parser'), response.text
    except Exception as e:
        print(f"❌ 접속 오류 발생 ({url}): {e}")
        return None, ""

def collect_from_ppomppu():
    """뽐뿌 핫딜 게시판 수집 (데스크톱/모바일 다중 시도)"""
    session = requests.Session()
    urls = [
        "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu", # PC 버전
        "https://m.ppomppu.co.kr/new/bbs_list.php?id=ppomppu"     # 모바일 버전
    ]
    
    collected_data = []

    for url in urls:
        print(f"\n🌐 현재 수집 대상: {url}")
        soup, html_raw = get_soup(url, session)
        
        if not soup:
            continue

        # 차단 메시지 확인
        block_keywords = ["접속이 제한", "Robot", "자동접속", "Access Denied", "IP가 차단", "보안절차", "비정상적인 접근"]
        if any(msg in html_raw for msg in block_keywords):
            print(f"❌ 차단 감지: {url} 버전은 현재 GitHub Actions 환경에서 차단되었습니다.")
            continue

        is_mobile = "m.ppomppu" in url
        rows = []
        
        if is_mobile:
            rows = soup.select('.list_default li') or soup.select('li.common-list-item') or soup.select('.bbsList li')
        else:
            rows = soup.select('tr.list0, tr.list1') or soup.select('tr[align="center"]')
            if not rows:
                main_table = soup.find('table', id='main_list')
                if main_table:
                    rows = main_table.find_all('tr', recursive=False)[1:]

        print(f"🔎 후보 항목 {len(rows)}개 발견.")

        if not rows:
            print(f"⚠️ {url}에서 유효한 데이터 행을 찾지 못했습니다. 구조 분석이 필요합니다.")
            continue

        for idx, row in enumerate(rows):
            try:
                if is_mobile:
                    title_tag = row.select_one('.title') or row.select_one('strong') or row.select_one('.subject')
                    link_tag = row.select_one('a')
                    img_tag = row.select_one('img')
                else:
                    title_tag = row.find(['font', 'span'], class_='list_title') or row.select_one('a font')
                    if not title_tag: 
                        tds = row.find_all('td')
                        if len(tds) >= 3:
                            title_tag = tds[2].find('a') # PC 버전 제목 위치
                    
                    if not title_tag: continue
                    link_tag = title_tag if title_tag.name == 'a' else title_tag.find_parent('a')
                    img_tag = row.find('img', class_='thumb_border')

                if not title_tag or not link_tag: continue

                full_title = title_tag.get_text(strip=True)
                if not full_title or len(full_title) < 5: continue

                href = link_tag.get('href', '')
                if not href: continue
                
                base_url = "https://m.ppomppu.co.kr/new/" if is_mobile else "https://www.ppomppu.co.kr/zboard/"
                link = base_url + href if not href.startswith('http') else href

                # 공지 및 광고 필터링
                if not is_mobile:
                    num_td = row.find('td', class_='eng v_middle')
                    if num_td:
                        num_text = num_td.get_text(strip=True)
                        if num_td.find('img') or not num_text.isdigit():
                            continue

                platform = "기타"
                p_match = re.search(r'\[(.*?)\]', full_title)
                if p_match: platform = p_match.group(1)
                
                price = extract_price(full_title)
                product_name = re.sub(r'\[.*?\]', '', full_title).strip()
                product_name = re.sub(r'\(.*?\)', '', product_name).strip()
                
                # 뱃지 로직: 건우 취향(곤충/생물) 우선 순위 부여
                badge = "NEW"
                is_gunwoo_pick = False
                if any(keyword in product_name for keyword in RECOMMENDED_KEYWORDS):
                    # 건우 선호 키워드 체크
                    gunwoo_keywords = ['사슴벌레', '장수풍뎅이', '곤충', '생물', '도감', '파브르', '표본', '과학잡지', '공룡']
                    if any(gk in product_name for gk in gunwoo_keywords):
                        badge = "건우&엄마 추천"
                        is_gunwoo_pick = True
                    else:
                        badge = "엄마 추천"
                elif price > 100000:
                    badge = "HOT"
                
                # 이미지 추출 (Lazy Loading 대응)
                img_url = ""
                if img_tag:
                    src = img_tag.get('data-original') or img_tag.get('src')
                    if src:
                        if src.startswith('//'): img_url = "https:" + src
                        elif src.startswith('/'): img_url = "https://www.ppomppu.co.kr" + src
                        else: img_url = src
                
                if not img_url:
                    img_url = f"https://placehold.co/80x80/f1f5f9/94a3b8?text={platform[:1]}"

                if is_gunwoo_pick:
                    print(f"⭐ [건우 맞춤 핫딜 발견!] {product_name}")

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
                
                if len(collected_data) >= 40: break # 더 풍성한 잡지를 위해 40개까지 수집
            except Exception as e:
                continue
        
        if collected_data:
            print(f"✅ {url}에서 {len(collected_data)}개의 유효 데이터 수집 성공.")
            break
        else:
            print(f"⚠️ {url}에서 데이터를 가져오지 못했습니다. 다음 경로를 시도합니다.")
            time.sleep(random.uniform(2.0, 4.0))
            
    return collected_data

def save_to_csv(data):
    """수집 데이터를 deals.csv로 저장하며 성공 여부를 확인합니다."""
    keys = ["category", "platform", "productName", "currentPrice", "originalPrice", "badge", "sourceSite", "link", "image", "color"]
    try:
        if not data:
            print("⚠️ [ERROR] 수집된 데이터가 최종적으로 0개입니다. 저장을 중단합니다.")
            sys.exit(1)

        # '건우&엄마 추천' 아이템이 가장 위로 오게 정렬
        data.sort(key=lambda x: (x['badge'] == '건우&엄마 추천', x['badge'] == '엄마 추천'), reverse=True)

        with open('deals.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"🎉 파일 저장 성공: deals.csv에 {len(data)}개의 핫딜이 기록되었습니다.")
    except Exception as e:
        print(f"❌ [CRITICAL] CSV 저장 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 [정밀 디버그 모드] 핫딜 수집 엔진 가동 시작")
    start_time = time.time()
    
    # 봇 감지 회피 지연
    time.sleep(random.uniform(2, 5))
    
    deals = collect_from_ppomppu()
    
    if deals:
        save_to_csv(deals)
    else:
        print("\n❌ [최종 실패] 모든 경로(PC/모바일)가 차단되었거나 사이트 구조가 완전히 변경되었습니다.")
        sys.exit(1)
        
    end_time = time.time()
    print(f"⏱️ 총 소요 시간: {end_time - start_time:.2f}초")
