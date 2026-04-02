import streamlit as st
import easyocr
import cv2
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="차량 판별 시스템", layout="centered")

# =========================
# 제목
# =========================
st.title("🚗 차량 번호 판별 시스템")
st.caption("순찰 직원용 차량 확인 시스템")

# =========================
# DB 로드
# =========================
@st.cache_data
def load_db():
    st.write("컬럼 목록:", df.columns.tolist())
    st.write("DB 값:", df['car_number'].tolist())
    try:
        df = pd.read_csv("car_db.csv")

        required_cols = ["car_number"]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"❌ '{col}' 컬럼이 CSV에 없습니다.")
                st.stop()

        return df

    except Exception:
        st.error("❌ car_db.csv 파일을 찾을 수 없습니다. GitHub에 업로드해주세요.")
        st.stop()

df=load_db()

df['car_number'] = df['car_number'].astype(str).str.strip().str.zfill(4)

# =========================
# OCR 초기화 (속도 개선)
# =========================
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ko', 'en'])

reader = load_ocr()

# =========================
# 모드 선택
# =========================
mode = st.radio("🔽 모드 선택", ["⌨️ 번호 입력", "📷 사진 업로드"])

car_number = None

# =========================
# 번호 입력
# =========================
if mode == "⌨️ 번호 입력":
    col1, col2 = st.columns([3,1])

    with col1:
        input_number = st.text_input("차량 번호 뒤 4자리 입력", max_chars=4)

    with col2:
        if st.button("조회"):
            car_number = input_number

# =========================
# 사진 업로드
# =========================
elif mode == "📷 사진 업로드":
    uploaded_file = st.file_uploader("번호판 이미지 업로드", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        img = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), 1)
        st.image(img, caption="업로드 이미지", use_container_width=True)

        if st.button("OCR 분석"):
            results = reader.readtext(img)

            detected_text = " ".join([r[1] for r in results])
            st.write("🔍 OCR 결과:", detected_text)

            numbers = re.findall(r'\d+', detected_text)
            full_number = "".join(numbers)

            if len(full_number) >= 4:
                car_number = full_number[-4:]
                st.success(f"🚗 추출된 번호: {car_number}")
            else:
                st.error("⚠️ 번호판 인식 실패")

# =========================
# 결과 출력
# =========================
if car_number:
    car_number = str(car_number).strip().zfill(4)
    df['car_number'] = df['car_number'].astype(str).str.zfill(4)

    if car_number in df['car_number'].values:
        result = df[df['car_number'] == car_number]
        st.success("✅ 직원 차량입니다")
        st.dataframe(result, use_container_width=True)
    else:
        # ⭐ 차번호 없는 직원 있는지 확인
        no_car_staff = df[df['car_number'].isna() | (df['car_number']=="")]

        if len(no_car_staff) > 0:
            st.warning("⚠️ 등록되지 않은 차량입니다 (직원 차량일 수 있음)")
        else:
            st.error("❌ 비직원 차량입니다")
