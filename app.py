import streamlit as st
import easyocr
import cv2
import pandas as pd
import numpy as np
import re
import datetime

# =========================
# 1. 설정 및 DB 로드
# =========================
# 모바일 대응: 페이지 폭을 전체 화면으로 설정
st.set_page_config(page_title="차량판별 시스템", layout="wide")

# CSS 스타일링 (모바일 최적화)
st.markdown("""
    <style>
    .main-title { font-size: 24px !important; font-weight: bold; margin-bottom: 10px; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
    .status-box { padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def load_db():
    try:
        # car_db.csv 파일이 있어야 합니다.
        df = pd.read_csv("car_db.csv")
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df = df.dropna(subset=['car_number'])
        
        def format_car_num(val):
            try:
                return str(int(float(val))).zfill(4)
            except:
                return str(val).strip().zfill(4)
        
        df['car_number'] = df['car_number'].apply(format_car_num)
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        st.stop()

df = load_db()

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ko', 'en'])

reader = load_ocr()

# =========================
# 2. UI 구성 (상단 타이틀 및 탭)
# =========================
st.markdown('<p class="main-title">🚗 차량 번호 판별 및 홀짝제 점검</p>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["⌨️ 직접 입력", "📷 사진 인식", "📖 이용 가이드"])

car_number = None

# [탭 1] 직접 입력
with tab1:
    input_number = st.text_input("차량 번호 뒤 4자리 입력", max_chars=4, placeholder="예: 4348")
    if st.button("조회하기", key="btn_input"):
        if input_number:
            car_number = input_number
        else:
            st.warning("번호를 입력해주세요.")

# [탭 2] 사진 인식
with tab2:
    uploaded_file = st.file_uploader("번호판 촬영 또는 업로드", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        img = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), 1)
        st.image(img, use_container_width=True, caption="업로드된 이미지")
        if st.button("번호 추출 및 분석", key="btn_ocr"):
            with st.spinner("이미지 분석 중..."):
                results = reader.readtext(img)
                detected_text = "".join([r[1] for r in results])
                numbers = re.findall(r'\d+', detected_text)
                if numbers:
                    full_number = "".join(numbers)
                    car_number = full_number[-4:] if len(full_number) >= 4 else full_number
                else:
                    st.error("숫자를 인식하지 못했습니다. 다시 촬영해 주세요.")

# [탭 3] 이용 가이드
with tab3:
    st.info("### 💡 시스템 사용법")
    st.markdown("""
    본 사이트는 차량2부제에 따라 KHEPI의 직원차량을 확인하기 위한 사이트입니다.
    1. **직원 차량 확인**: 등록된 차번호를 기준으로 이름과 부서를 확인합니다.
    2. **홀짝제(2부제)  점검**: 
        - **날짜가 홀수**인 날: 번호 끝자리가 짝수인 차량은 위반입니다.
        - **날짜가 짝수**인 날: 번호 끝자리가 홀수인 차량은 위반입니다
    3. **주의 사항**:
        - 사진 인식 시 번호판이 정면에서 잘 보이도록 촬영해 주세요.
        - 정보가 다른 경우 관리자에게 DB 수정을 요청하세요.
    """)

# =========================
# 3. 결과 출력 및 홀짝제 판별
# =========================
if car_number:
    search_target = str(car_number).strip().zfill(4)
    result = df[df['car_number'] == search_target]

    # 오늘 날짜 기반 홀짝 판단
   # 1. 현재 세계 표준시 가져오기
    now_utc = datetime.datetime.utcnow()
    # 2. 한국 시간으로 변환 (UTC + 9시간)
    korea_time = now_utc + datetime.timedelta(hours=9)

    # 3. 한국 시간의 날짜(day)를 기준으로 판별
    today_day = korea_time.day
    is_date_even = (today_day % 2 == 0)
    day_type_str = "짝수" if is_date_even else "홀수"
    
    # 차량 번호 끝자리 기반 홀짝 판단
    last_digit = int(search_target[-1])
    is_car_even = (last_digit % 2 == 0)
    
    # 위반 여부 (날짜와 차량의 홀짝이 다르면 위반)
    is_violation = (is_date_even != is_car_even)

    st.markdown("---")
    
    # [1] 등록 정보 섹션
    if not result.empty:
        st.success(f"### ✅ 등록 차량 확인: {search_target}")
        for _, row in result.iterrows():
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"성명:, {row['name']}")
            with c2
                st.markdonn(f"소속 부서:, {row['department']}")
    else:
        st.error(f"### ❌ 미등록 차량: {search_target}")
        st.write("방문객 안내 대상을 확인해 주세요.")

    # [2] 홀짝제 점검 섹션
    st.markdown("### 📅 홀짝제(2부제) 결과")
    st.write(f"오늘은 **{korea_time.month}월 {korea_time.day}일({day_type_str}날)** 입니다.")
    
    if is_violation:
        st.warning(f"🚨 **[운행 위반]** 오늘은 {day_type_str} 운행일입니다. (차량 끝자리: {last_digit})")
    else:
        st.info(f"✅ **[정상 운행]** 오늘 운행 가능한 차량입니다.")
