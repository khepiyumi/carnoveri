import streamlit as st
import easyocr
import cv2
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="차량 판별 시스템", layout="centered")

# =========================
# 1. DB 로드 및 강력한 데이터 클리닝
# =========================
@st.cache_data
def load_db():
    try:
        # CSV 로드
        df = pd.read_csv("car_db.csv")
        
        # [수정] 모든 컬럼의 앞뒤 공백 제거 (부서명 뒤 공백 등 해결)
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 차량 번호가 없는 행 제거
        df = df.dropna(subset=['car_number'])
        
        # [핵심] 차량 번호를 무조건 '4자리 문자열'로 통일
        def format_car_num(val):
            try:
                # 숫자형태(4348.0 등)를 정수형 문자열 "4348"로 변환
                return str(int(float(val))).zfill(4)
            except:
                # 변환 실패 시 공백 제거 후 반환
                return str(val).strip().zfill(4)
        
        df['car_number'] = df['car_number'].apply(format_car_num)
        
        return df

    except Exception as e:
        st.error(f"❌ DB 로드 오류: {e}")
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
# 3. UI 구성
# =========================
st.title("🚗 차량 번호 판별 시스템")

mode = st.radio("🔽 모드 선택", ["⌨️ 번호 입력", "📷 사진 업로드"])

car_number = None

if mode == "⌨️ 번호 입력":
    col1, col2 = st.columns([3,1])
    with col1:
        input_number = st.text_input("차량 번호 뒤 4자리 입력", max_chars=4)
    with col2:
        if st.button("조회"):
            car_number = input_number

elif mode == "📷 사진 업로드":
    uploaded_file = st.file_uploader("번호판 이미지 업로드", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        img = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), 1)
        st.image(img, use_container_width=True)
        if st.button("OCR 분석"):
            results = reader.readtext(img)
            detected_text = "".join([r[1] for r in results])
            numbers = re.findall(r'\d+', detected_text)
            full_number = "".join(numbers)
            if len(full_number) >= 4:
                car_number = full_number[-4:]
            else:
                st.error("⚠️ 번호를 인식하지 못했습니다.")

# =========================
# 4. 결과 출력 (매칭 로직 강화)
# =========================
if car_number:
    # 입력값도 4자리 문자열로 변환
    search_target = str(car_number).strip().zfill(4)
    
    # DB에서 조회 (문자열 비교)
    result = df[df['car_number'] == search_target]

    st.divider()
    
    if not result.empty:
        st.success(f"✅ 직원 차량입니다: {search_target}")
        # index=False로 깔끔하게 출력
        st.table(result)
    else:
        st.error(f"❌ 비직원 차량입니다: {search_target}")
        # 디버깅용: 현재 DB에 로드된 번호 목록 일부 보여주기 (개발 시에만 확인)
        with st.expander("데이터 확인 (디버깅용)"):
            st.write("현재 DB 상단 5개 번호:", df['car_number'].head().tolist())
