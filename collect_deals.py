import requests
from bs4 import BeautifulSoup
import csv
import re
import os
import sys
import time

# --- 엄마 추천 키워드 (유치원~고등학생 타겟) ---
# 건우가 좋아하는 곤충과 생물 관련 키워드도 포함되어 있습니다.
RECOMMENDED_KEYWORDS = [
    '유치원', '초등학교', '중학교', '고등학생', '입학', '신학기', '어린이날',
    '장난감', '교구', '학용품', '필기구', '백팩', '책가방',
    '문제집', '참고서', '스터디플래너', '독서실', '수험생',
    '태블릿', '아이패드', '갤럭시탭', '인강용', '노트북',
    '운동화', '후드티', '패딩', '트레이닝복', '조거패츠',
    '보드게임', '슬라임', '닌텐도', '레고', '피규어', '도감',
    '곤충', '생물', '사슴벌레', '장수풍뎅이', '관찰키트', '자연관찰'
]

def get_platform_color(platform):
    """플랫폼 이름에 따라 테마 색상을 결정합니다."""
    p = platform.lower()
    if '쿠팡' in p: return 'red'
    if '네이버' in p or 'n쇼핑' in p: return 'green'
    if '11번가' in p or 'g마켓' in p or '지마켓' in p or '옥션' in p: return 'red'
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
    # 최신 브라우저 헤더를 모방하여 차단 방지 (User-Agent는 주기적으로 업데이트 권장)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    }
    
    try:
        print(f"🌐 뽐뿌 서버 접속 시도 중: {url}")
        response = session.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        
        # 뽐뿌 특유의 한글 깨짐 방지 (euc-kr 대응)
        if response.encoding.lower() == 'iso-8859-1':
            response.encoding = 'euc-kr'
        else:
            response.encoding = response.apparent_encoding
        
        print(f"✅ 접속 성공 (상태 코드: {response.status_code})")
        
        # 보안 페이지 또는 차단 여부 확인
        if "사용자의 접속이 제한" in response.text or "Robot" in response.text:
            print("❌ 차단됨: GitHub Actions IP가 뽐뿌에 의해 차단되었습니다.")
            # 디버깅을 위해 응답 텍스트 일부 출력
            print(f"DEBUG (응답 내용 일부): {response.text[:500]}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"❌ 접속 실패: {e}")
        return []
    
    collected_data = []
    
    # 1단계: 가장 일반적인 제목 셀렉터
    # 뽐뿌는 보통 font.list_title 또는 span.list_title을 사용합니다.
    title_elements = soup.select('.list_title')
    
    # 2단계: 실패 시 백업 셀렉터 (구조적 접근)
    if not title_elements:
        print("⚠️ 기본 셀렉터 실패. 백업 로직을 실행합니다.")
        # 게시글 리스트 테이블 내의 링크를 직접 탐색
        title_elements = soup.select('tr.list0 a > font') + soup.select('tr.list1 a > font')

    if not title_elements:
        print("❌ 데이터를 찾을 수 없습니다. 응답 HTML 구조를 확인하세요.")
        # 구조 분석을 위해 로그에 HTML 일부 출력
        print(f"DEBUG (HTML Snippet): {response.text[:1000]}")
        return []

    print(f"🔎 후보 항목 {len(title_elements)}개 발견. 데이터 파싱 시작...")

    for title_tag in title_elements:
        try:
            # 게시글 행(TR) 찾기
            parent_tr = title_tag.find_parent('tr')
            if not parent_tr: continue
            
            # 링크 태그 추출
            link_tag = title_tag if title_tag.name == 'a' else title_tag.find_parent('a')
            if not link_tag or not link_tag.get('href'): continue
            
            full_title = title_tag.get_text(strip=True)
            if len(full_title) < 5: continue # 너무 짧은 텍스트는 유효한 제목이 아님

            # 공지사항 및 광고글 제외 로직
            # 뽐뿌는 일반 게시글 번호가 td.eng.v_middle에 숫자로 들어있습니다.
            num_td = parent_tr.find('td', class_='eng v_middle')
            if num_td:
                num_text = num_td.get_text(strip=True)
                # 이미지가 들어있거나 숫자가 아니면 공지/광고
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
            
            # 썸네일 이미지 추출 및 정규화
            img_tag = parent_tr.find('img', class_='thumb_border')
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
                # 이미지가 없을 경우 플랫폼 로고 대용 이미지
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
            
            if len(collected_data) >= 25: break # 상위 25개 수집
            
        except Exception as e:
            # 개별 항목 파싱 실패 시 로그를 남기고 다음 항목 진행
            print(f"⚠️ 항목 파싱 중 건너뜀: {e}")
            continue
            
    return collected_data

def save_to_csv(data):
    """수집 데이터를 deals.csv로 저장"""
    keys = ["category", "platform", "productName", "currentPrice", "originalPrice", "badge", "sourceSite", "link", "image", "color"]
    try:
        if not data:
            print("⚠️ 수집된 데이터가 최종적으로 0개입니다. 저장을 중단합니다.")
            sys.exit(1)

        with open('deals.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"✅ 최종 완료: {len(data)}개의 항목이 deals.csv에 업데이트되었습니다.")
    except Exception as e:
        print(f"❌ 파일 저장 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 [디버그 모드] 실시간 핫딜 수집 엔진 가동...")
    start_time = time.time()
    
    deals = collect_from_ppomppu()
    
    if deals:
        save_to_csv(deals)
    else:
        print("❌ 데이터 수집에 완전히 실패했습니다. 사이트 차단 또는 구조 변경을 확인하세요.")
        # GitHub Actions에서 에러로 표시되도록 강제 종료
        sys.exit(1)
        
    end_time = time.time()
    print(f"⏱️ 총 소요 시간: {end_time - start_time:.2f}초")
