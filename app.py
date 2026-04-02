import streamlit as st
import easyocr
import cv2
import pandas as pd
import numpy as np
import re

# 모바일 대응: 페이지 폭을 전체 화면으로 설정
st.set_page_config(page_title="차량판별", layout="wide")

# CSS를 이용해 타이틀 크기 조절 및 모바일 최적화 UI 스타일링
st.markdown("""
    <style>
    .main-title { font-size: 24px !important; font-weight: bold; margin-bottom: 0px; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
    div[data-testid="stMetric"] { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# =========================
# 1. DB 로드 및 데이터 클리닝
# =========================
@st.cache_data
def load_db():
    try:
        df = pd.read_csv("car_db.csv")
        # 모든 텍스트 데이터의 앞뒤 공백 제거
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        # 번호가 없는 행 제거
        df = df.dropna(subset=['car_number'])
        
        # 차량 번호를 4자리 문자열(0000) 형식으로 통일
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

# =========================
# 2. OCR 초기화
# =========================
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ko', 'en'])

reader = load_ocr()

# =========================
# 3. UI 구성 (한 줄 타이틀 및 모바일 최적화)
# =========================
st.markdown('<p class="main-title">🚗 차량 번호 판별 시스템</p>', unsafe_allow_html=True)

# 모바일에서는 탭 형식이 선택하기 더 편합니다
tab1, tab2 = st.tabs(["⌨️ 직접 입력", "📷 사진 인식"])

car_number = None

# [탭 1] 직접 입력
with tab1:
    input_number = st.text_input("차량 번호 뒤 4자리", max_chars=4, placeholder="4348")
    if st.button("차량 조회", key="btn_input"):
        if input_number:
            car_number = input_number
        else:
            st.warning("번호를 입력하세요.")

# [탭 2] 사진 인식
with tab2:
    uploaded_file = st.file_uploader("번호판 촬영/업로드", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        img = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), 1)
        st.image(img, use_container_width=True)
        if st.button("번호 추출 시작", key="btn_ocr"):
            with st.spinner("분석 중..."):
                results = reader.readtext(img)
                detected_text = "".join([r[1] for r in results])
                numbers = re.findall(r'\d+', detected_text)
                if numbers:
                    full_number = "".join(numbers)
                    car_number = full_number[-4:] if len(full_number) >= 4 else full_number
                else:
                    st.error("숫자를 찾을 수 없습니다.")

# =========================
# 4. 결과 출력 (모바일 가독성 중심)
# =========================
if car_number:
    search_target = str(car_number).strip().zfill(4)
    result = df[df['car_number'] == search_target]

    st.markdown("---")
    
    if not result.empty:
        st.success(f"✅ **직원 차량 확인됨 ({search_target})**")
        
        # 모바일에서 보기 좋게 정보를 카드 형태로 출력
        for _, row in result.iterrows():
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("이름", row['name'])
            with col_b:
                st.metric("부서", row['department'])
    else:
        st.error(f"❌ **미등록 차량 ({search_target})**")
        st.toast("DB에 일치하는 정보가 없습니다.")
