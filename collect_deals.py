import requests
from bs4 import BeautifulSoup
import csv
import re
import os
import sys
import time
import random

# --- 추천 필터링 키워드 (엄마 추천: 건우 관심사 및 교육/생활용품) ---
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
    """제목 문자열에서 가격 숫자를 추출합니다 (다양한 패턴 대응)."""
    # 숫자와 콤마 조합 뒤에 '원'이 붙는 패턴 (공백 허용)
    match = re.search(r'([\d,]+)\s*원', title)
    if match:
        price_str = match.group(1).replace(',', '')
        return int(price_str) if price_str.isdigit() else 0
    return 0

def get_soup(url, session):
    """지정된 URL에 접속하여 BeautifulSoup 객체를 반환합니다."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Cache-Control': 'no-cache',
    }
    
    try:
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        # 뽐뿌 인코딩 처리 (EUC-KR 강제 지정 및 폴백)
        try:
            response.encoding = 'euc-kr'
            if 'html' not in response.text: # 인코딩 실패 시
                response.encoding = response.apparent_encoding
        except:
            response.encoding = response.apparent_encoding
            
        return BeautifulSoup(response.text, 'html.parser'), response.text
    except Exception as e:
        print(f"⚠️ 접속 시도 중 오류 발생 ({url}): {e}")
        return None, ""

def collect_from_ppomppu():
    """뽐뿌 핫딜 게시판 수집 (데스크톱/모바일 다중 시도)"""
    session = requests.Session()
    urls = [
        "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu", # PC 버전
        "https://m.ppomppu.co.kr/new/bbs_list.php?id=ppomppu"     # 모바일 버전 (차단 확률 낮음)
    ]
    
    collected_data = []

    for url in urls:
        print(f"🌐 접속 시도 중: {url}")
        soup, html_raw = get_soup(url, session)
        
        if not soup:
            continue

        # 차단 문구 확인
        if any(msg in html_raw for msg in ["접속이 제한", "Robot", "자동접속"]):
            print(f"❌ 차단 확인: {url} 버전은 현재 GitHub IP를 차단 중입니다.")
            continue

        is_mobile = "m.ppomppu" in url
        
        if is_mobile:
            # 모바일 버전 파싱 로직
            rows = soup.select('li.common-list-item') or soup.select('ul.list_default > li')
        else:
            # 데스크톱 버전 파싱 로직
            rows = soup.select('tr.list0, tr.list1')

        print(f"🔎 {url}에서 후보 항목 {len(rows)}개 발견.")

        for row in rows:
            try:
                if is_mobile:
                    # 모바일 파싱
                    title_tag = row.select_one('.title') or row.select_one('strong')
                    link_tag = row.select_one('a')
                    img_tag = row.select_one('img')
                else:
                    # 데스크톱 파싱
                    title_tag = row.find(['font', 'span'], class_='list_title')
                    if not title_tag: continue
                    link_tag = title_tag.find_parent('a')
                    img_tag = row.find('img', class_='thumb_border')

                if not title_tag or not link_tag: continue

                full_title = title_tag.get_text(strip=True)
                if len(full_title) < 5: continue

                # 링크 생성
                href = link_tag['href']
                base_url = "https://m.ppomppu.co.kr/new/" if is_mobile else "https://www.ppomppu.co.kr/zboard/"
                link = base_url + href if not href.startswith('http') else href

                # 공지 제외 (번호 체크)
                if not is_mobile:
                    num_td = row.find('td', class_='eng v_middle')
                    if num_td and (num_td.find('img') or not num_td.get_text(strip=True).isdigit()):
                        continue

                # 데이터 추출
                platform = "기타"
                p_match = re.search(r'\[(.*?)\]', full_title)
                if p_match: platform = p_match.group(1)
                
                price = extract_price(full_title)
                product_name = re.sub(r'\[.*?\]', '', full_title).strip()
                product_name = re.sub(r'\(.*?\)', '', product_name).strip()
                
                # 뱃지 로직
                badge = "NEW"
                if any(keyword in product_name for keyword in RECOMMENDED_KEYWORDS):
                    badge = "엄마 추천"
                elif price > 100000:
                    badge = "HOT"
                
                # 이미지 주소
                img_url = ""
                if img_tag and img_tag.get('src'):
                    src = img_tag.get('src')
                    if src.startswith('//'): img_url = "https:" + src
                    elif src.startswith('/'): img_url = "https://www.ppomppu.co.kr" + src
                    else: img_url = src
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
            except:
                continue
        
        # 데이터가 하나라도 수집되었다면 다음 URL 시도하지 않음
        if collected_data:
            break
            
    return collected_data

def save_to_csv(data):
    """수집 데이터를 deals.csv로 저장"""
    keys = ["category", "platform", "productName", "currentPrice", "originalPrice", "badge", "sourceSite", "link", "image", "color"]
    try:
        if not data:
            print("⚠️ 수집된 데이터가 최종적으로 0개입니다.")
            sys.exit(1)

        with open('deals.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"✅ 성공: {len(data)}개의 항목 저장 완료.")
    except Exception as e:
        print(f"❌ CSV 저장 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 [수동 디버깅 모드] 핫딜 수집 엔진 가동...")
    start_time = time.time()
    
    # 랜덤 대기 (봇 감지 회피)
    time.sleep(random.uniform(1, 3))
    
    deals = collect_from_ppomppu()
    
    if deals:
        save_to_csv(deals)
    else:
        print("❌ 수집 실패: PC/모바일 버전 모두 접속이 제한되었거나 구조가 변경되었습니다.")
        sys.exit(1)
        
    print(f"⏱️ 소요 시간: {time.time() - start_time:.2f}초")
