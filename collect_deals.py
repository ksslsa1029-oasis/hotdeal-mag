import requests
from bs4 import BeautifulSoup
import csv
import re
import os
import sys
import time

# --- 추천 필터링 키워드 (엄마 추천: 건우 관심사 및 교육/생활용품) ---
# 김건우 군이 좋아하는 곤충, 생물 키워드와 학생용 키워드를 통합 관리합니다.
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
    """플랫폼 이름에 따라 테마 색상을 결정합니다."""
    p = platform.lower()
    if '쿠팡' in p: return 'red'
    if '네이버' in p or 'n쇼핑' in p: return 'green'
    if '11번가' in p or 'g마켓' in p or '지마켓' in p or '옥션' in p: return 'red'
    if '티몬' in p or '위메프' in p: return 'blue'
    return 'blue'

def extract_price(title):
    """제목 문자열에서 가격 숫자를 추출합니다."""
    # 숫자와 콤마 조합 뒤에 '원'이 붙는 패턴 탐색
    match = re.search(r'([\d,]+)원', title)
    if match:
        price_str = match.group(1).replace(',', '')
        return int(price_str) if price_str.isdigit() else 0
    return 0

def collect_from_ppomppu():
    """뽐뿌 핫딜 게시판 수집 (보안 우회 및 다중 셀렉터 적용)"""
    url = "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu"
    
    session = requests.Session()
    # 최신 브라우저 헤더를 더 정교하게 모사하여 차단 방지
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }
    
    try:
        print(f"🌐 뽐뿌 서버 접속 시도 중: {url}")
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 뽐뿌 특유의 한글 깨짐 방지 (euc-kr 대응 및 자동 감지)
        if response.encoding.lower() == 'iso-8859-1':
            response.encoding = 'euc-kr'
        else:
            response.encoding = response.apparent_encoding
        
        print(f"✅ 접속 성공 (상태 코드: {response.status_code})")
        
        # 보안 페이지 또는 차단 여부 확인
        html_content = response.text
        if "사용자의 접속이 제한" in html_content or "Robot" in html_content or "자동접속" in html_content:
            print("❌ 차단됨: GitHub Actions IP가 뽐뿌의 보안 시스템에 의해 감지되었습니다.")
            print(f"DEBUG (응답 내용 일부): {html_content[:500]}")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        print(f"❌ 접속 단계 치명적 실패: {e}")
        return []
    
    collected_data = []
    
    # 뽐뿌의 게시글 리스트는 보통 'list0', 'list1' 클래스를 가진 tr 태그들입니다.
    rows = soup.select('tr.list0, tr.list1')
    
    if not rows:
        print("⚠️ 클래스 기반 행 찾기 실패. id='main_list' 기반 백업 로직을 실행합니다.")
        table = soup.find('table', id='main_list')
        if table:
            rows = table.find_all('tr', recursive=False)
            # 헤더나 의미 없는 행 제외를 위해 필터링
            rows = [r for r in rows if r.find('td', class_='eng v_middle')]
    
    print(f"🔎 총 {len(rows)}개의 잠재적 행(Row)을 분석합니다.")

    for idx, row in enumerate(rows):
        try:
            # 1. 제목 및 링크 태그 찾기
            # 클래스 list_title을 우선 탐색하고 없으면 구조적으로 탐색
            title_tag = row.find(['font', 'span'], class_='list_title')
            if not title_tag:
                # 뽐뿌 구조가 바뀔 경우 td 내의 a 태그를 직접 찾음
                td_list = row.find_all('td', recursive=False)
                if len(td_list) >= 3:
                    title_tag = td_list[2].find('a')
            
            if not title_tag:
                continue

            full_title = title_tag.get_text(strip=True)
            if not full_title or len(full_title) < 5:
                continue

            # 링크 추출
            link_tag = title_tag if title_tag.name == 'a' else title_tag.find_parent('a')
            if not link_tag or not link_tag.get('href'):
                continue
            
            # 상세 링크 완성
            href = link_tag['href']
            link = "https://www.ppomppu.co.kr/zboard/" + href if not href.startswith('http') else href

            # 2. 공지사항 및 광고글 제외 로직
            # 글 번호가 td.eng.v_middle에 숫자로 들어있는지 확인
            num_td = row.find('td', class_='eng v_middle')
            if num_td:
                num_text = num_td.get_text(strip=True)
                # 이미지가 있거나(공지 아이콘), 숫자가 아니면 제외
                if num_td.find('img') or not num_text.isdigit():
                    continue
            else:
                # 번호 영역이 없으면 일반 게시글이 아닐 확률이 높음
                continue

            # 3. 플랫폼 및 상품명/가격 정제
            platform = "기타"
            p_match = re.search(r'\[(.*?)\]', full_title)
            if p_match:
                platform = p_match.group(1)
            
            price = extract_price(full_title)
            # 정규표현식을 이용해 불필요한 대괄호/괄호 제거
            product_name = re.sub(r'\[.*?\]', '', full_title).strip()
            product_name = re.sub(r'\(.*?\)', '', product_name).strip()
            
            # --- 뱃지 로직 (엄마 추천 적용) ---
            badge = "NEW"
            if any(keyword in product_name for keyword in RECOMMENDED_KEYWORDS):
                badge = "엄마 추천"
            elif price > 100000:
                badge = "HOT"
            
            # 4. 썸네일 이미지 추출 및 정규화
            img_tag = row.find('img', class_='thumb_border')
            img_url = ""
            if img_tag and img_tag.get('src'):
                src = img_tag.get('src')
                if src.startswith('//'):
                    img_url = "https:" + src
                elif src.startswith('/'):
                    img_url = "https://www.ppomppu.co.kr" + src
                else:
                    img_url = src
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
            
        except Exception as e:
            # 개별 행 파싱 실패 시 로그만 남기고 계속 진행
            print(f"⚠️ {idx}번 행 파싱 중 건너뜀: {e}")
            continue
            
    return collected_data

def save_to_csv(data):
    """수집 데이터를 deals.csv로 저장"""
    keys = ["category", "platform", "productName", "currentPrice", "originalPrice", "badge", "sourceSite", "link", "image", "color"]
    try:
        if not data:
            print("⚠️ 수집된 데이터가 0개입니다. 저장을 취소하고 에러를 발생시킵니다.")
            sys.exit(1)

        with open('deals.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"✅ 최종 업데이트 성공: {len(data)}개의 항목이 저장되었습니다.")
    except Exception as e:
        print(f"❌ CSV 저장 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 [디버그/보강 모드] 핫딜 수집 엔진을 시작합니다.")
    start_time = time.time()
    
    deals = collect_from_ppomppu()
    
    if deals:
        save_to_csv(deals)
    else:
        print("❌ 수집된 데이터가 없습니다. 사이트 차단 여부나 구조를 다시 확인해야 합니다.")
        sys.exit(1)
        
    end_time = time.time()
    print(f"⏱️ 총 소요 시간: {end_time - start_time:.2f}초")
