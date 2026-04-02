import streamlit as st
import easyocr
import cv2
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="차량 판별 시스템", layout="centered")

# =========================
# 1. DB 로드 및 전처리 (매칭 오류 해결 핵심)
# =========================
@st.cache_data
def load_db():
    try:
        # CSV 로드
        df = pd.read_csv("car_db.csv")
        
        # [span_1](start_span)차량 번호가 없는 행(빈 칸)은 비교 대상에서 제외[span_1](end_span)
        df = df.dropna(subset=['car_number'])
        
        # 데이터 타입 통일: 숫자를 4자리 문자열(예: 720 -> "0720")로 변환
        # float -> int -> str 순서로 변환해야 소수점(.0)이 생기지 않습니다.
        df['car_number'] = df['car_number'].astype(float).astype(int).astype(str).str.zfill(4)
        
        return df

    except Exception as e:
        st.error(f"❌ car_db.csv 파일을 로드하는 중 오류가 발생했습니다: {e}")
        st.stop()

# 실행 시 DB 로드
df = load_db()

# =========================
# 2. OCR 초기화
# =========================
@st.cache_resource
def load_ocr():
    # 한국어와 영어를 인식하도록 설정
    return easyocr.Reader(['ko', 'en'])

reader = load_ocr()

# =========================
# 3. UI 구성
# =========================
st.title("🚗 차량 번호 판별 시스템")
st.caption("순찰 직원용 차량 확인 시스템")

mode = st.radio("🔽 모드 선택", ["⌨️ 번호 입력", "📷 사진 업로드"])

car_number = None

# ⌨️ 번호 입력 모드
if mode == "⌨️ 번호 입력":
    col1, col2 = st.columns([3,1])
    with col1:
        input_number = st.text_input("차량 번호 뒤 4자리 입력", max_chars=4, placeholder="예: 4348")
    with col2:
        if st.button("조회"):
            if input_number:
                car_number = input_number
            else:
                st.warning("번호를 입력해주세요.")

# 📷 사진 업로드 모드
elif mode == "📷 사진 업로드":
    uploaded_file = st.file_uploader("번호판 이미지 업로드", type=["jpg", "png", "jpeg"])
    if uploaded_file is not None:
        img = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), 1)
        st.image(img, caption="업로드 이미지", use_container_width=True)

        if st.button("OCR 분석"):
            with st.spinner("이미지에서 번호를 추출 중입니다..."):
                results = reader.readtext(img)
                detected_text = "".join([r[1] for r in results]).replace(" ", "")
                
                # 숫자만 추출
                numbers = re.findall(r'\d+', detected_text)
                full_number = "".join(numbers)

                if len(full_number) >= 4:
                    car_number = full_number[-4:]
                    st.info(f"🔍 인식된 번호: {car_number}")
                else:
                    st.error("⚠️ 번호판 숫자를 인식하지 못했습니다. 직접 입력 모드를 이용해 주세요.")

# =========================
# 4. 최종 매칭 결과 출력
# =========================
if car_number:
    # 입력받은 번호도 4자리 문자열 형식으로 맞춤
    target_number = str(car_number).strip().zfill(4)
    
    # DB에서 조회
    matching_result = df[df['car_number'] == target_number]

    st.divider() # 구분선
    
    if not matching_result.empty:
        st.success(f"✅ **직원 차량입니다.** (조회 번호: {target_number})")
        # 해당 번호의 모든 사용자 정보 표시 (동일 번호 다수 대비)
        st.dataframe(matching_result, use_container_width=True, hide_index=True)
    else:
        st.error(f"❌ **비직원 차량입니다.** (조회 번호: {target_number})")
        st.info("DB에 해당 번호가 등록되어 있지 않습니다.")
