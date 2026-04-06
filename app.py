import streamlit as st
import easyocr
import cv2
import pandas as pd
import numpy as np
import re
import datetime
import base64

# =========================
# 1. 설정 및 세션 초기화
# =========================
st.set_page_config(page_title="KHEPI 차량 점검 시스템", layout="wide")

if 'check_history' not in st.session_state:
    st.session_state.check_history = []
if 'current_car' not in st.session_state:
    st.session_state.current_car = None
if 'batch_text_results' not in st.session_state:
    st.session_state.batch_text_results = []
if 'batch_visual_results' not in st.session_state:
    st.session_state.batch_visual_results = []
if 'last_files' not in st.session_state:
    st.session_state.last_files = []
# ✅ 과부하 방지용 개별 파일 체크 변수 추가
if 'last_single_file' not in st.session_state:
    st.session_state.last_single_file = None

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 관리 메뉴")
    if st.button("🏠 화면 초기화"):
        st.session_state.current_car = None
        st.session_state.batch_text_results = []
        st.session_state.batch_visual_results = []
        st.session_state.last_single_file = None
        st.session_state.last_files = []
        st.rerun()
    st.markdown("---")
    if st.button("🗑️ 전체 기록 삭제"):
        st.session_state.check_history = []
        st.success("모든 기록이 삭제되었습니다.")
        st.rerun()

st.markdown("""
    <style>
    .main-title { font-size: 24px !important; font-weight: bold; margin-bottom: 15px; color: #1E3A8A; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; }
    .thumb-card { border: 1px solid #ddd; border-radius: 10px; padding: 10px; background-color: white; text-align: center; margin-bottom: 10px; }
    .thumb-img { max-width: 100%; height: 100px; object-fit: contain; border-radius: 5px; margin-bottom: 5px; }
    .result-text { font-weight: bold; font-size: 13px; }
    </style>
    """, unsafe_allow_html=True)

# =========================
# 유틸리티 함수 및 데이터 로드
# =========================
@st.cache_data
def load_db():
    try:
        df = pd.read_csv("car_db.csv")
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df = df.dropna(subset=['car_number'])
        def format_car_num(val):
            try: return str(int(float(val))).zfill(4)
            except: return str(val).strip().zfill(4)
        df['car_number'] = df['car_number'].apply(format_car_num)
        # 중복 제거 로직 (ValueError 방지)
        return df.drop_duplicates(subset=['car_number'], keep='first')
    except:
        st.error("car_db.csv 파일을 찾을 수 없습니다."); st.stop()

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ko', 'en'])

df = load_db()
db_dict = df.set_index('car_number').to_dict('index')
reader = load_ocr()

def get_car_info(car_num):
    info = db_dict.get(car_num)
    if info:
        return info['name'], info['department']
    return "미등록", "외부"

def check_violation(car_num):
    now_utc = datetime.datetime.utcnow()
    korea_time = now_utc + datetime.timedelta(hours=9)
    is_date_even = (korea_time.day % 2 == 0)
    try:
        last_digit = int(car_num[-1])
        is_car_even = (last_digit % 2 == 0)
        is_violation = (is_date_even != is_car_even)
        return is_violation, korea_time, "짝수" if is_date_even else "홀수"
    except:
        return False, korea_time, "오류"

def opencv_to_base64(image):
    _, buffer = cv2.imencode('.jpg', image)
    return f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

def resize_image(image, max_width=600):
    h, w = image.shape[:2]
    if w > max_width:
        ratio = max_width / float(w)
        return cv2.resize(image, (max_width, int(h * ratio)), interpolation=cv2.INTER_AREA)
    return image

# =========================
# 2. UI 구성 (탭)
# =========================
st.markdown('<p class="main-title">🚗 KHEPI 차량 2부제 점검 시스템</p>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["🔍 차량 조회/인식", "📊 점검 누적 목록", "📖 이용 가이드"])

with tab1:
    mode = st.radio("입력 모드 선택", ["개별 확인", "일괄 확인 (여러 대)"], horizontal=True)
    
    if mode == "개별 확인":
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("⌨️ 직접 입력")
            input_num = st.text_input("번호 뒤 4자리 입력", max_chars=4)
            if st.button("단일 조회"):
                st.session_state.current_car = input_num.strip().zfill(4)

        with col2:
            st.subheader("📷 사진 인식")
            up_file = st.file_uploader("사진 업로드", type=["jpg", "png", "jpeg"], key="single")
            if up_file:
                # ✅ 과부하 방지: 파일 ID 체크
                file_id = f"{up_file.name}_{up_file.size}"
                if st.session_state.get('last_single_file') != file_id:
                    with st.spinner("🚀 자동으로 번호를 추출하는 중..."):
                        file_bytes = np.frombuffer(up_file.read(), np.uint8)
                        img_raw = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                        img_ocr = resize_image(img_raw, 600)
                        # ✅ 성능 최적화: detail=0
                        results = reader.readtext(img_ocr, detail=0)
                        nums = re.findall(r'\d{4}', "".join(results))
                        
                        if nums:
                            st.session_state.current_car = nums[-1]
                            st.session_state["last_single_file"] = file_id
                            st.toast(f"추출 성공: {st.session_state.current_car}")
                
                st.image(resize_image(cv2.imdecode(np.frombuffer(up_file.getvalue(), np.uint8), cv2.IMREAD_COLOR), 300), 
                         caption="업로드된 이미지", channels="BGR", use_container_width=False)

        if st.session_state.current_car:
            st.markdown("---")
            car_num = st.session_state.current_car
            is_v, kt, d_type = check_violation(car_num)
            name, dept = get_car_info(car_num)
            
            st.subheader(f"조회 결과: {car_num}")
            if is_v: st.error(f"🚨 운행 위반 ({kt.month}월 {kt.day}일 {d_type}날)")
            else: st.success(f"✅ 정상 운행 ({kt.month}월 {kt.day}일 {d_type}날)")
            st.write(f"**소속:** {dept} | **성명:** {name}")

            if st.button("📋 이 결과 저장하기", type="primary"):
                st.session_state.check_history.append({
                    "점검시간": kt.strftime("%y-%m-%d %H:%M:%S"), "차량번호": car_num,
                    "성명": name, "부서": dept, "판정": "위반" if is_v else "정상"
                })
                st.session_state.current_car = None
                st.rerun()

    else:
        st.subheader("📑 일괄 처리 모드")
        m_col1, m_col2 = st.columns(2)
        
        with m_col1:
            st.markdown("**1. 텍스트 입력**")
            bulk_text = st.text_area("번호 4자리 나열 (쉼표, 엔터 구분)", placeholder="1234 5678", height=150)
            if st.button("차번호 조회 시작"):
                nums = re.findall(r'\d{4}', bulk_text)
                if nums:
                    temp_res = []
                    for n in nums:
                        is_v, kt, _ = check_violation(n)
                        name, dept = get_car_info(n)
                        temp_res.append({
                            "점검시간": kt.strftime("%y-%m-%d %H:%M:%S"), "차량번호": n,
                            "성명": name, "부서": dept, "판정": "위반" if is_v else "정상"
                        })
                    st.session_state.batch_text_results = temp_res

        with m_col2:
            st.markdown("**2. 사진 여러 장 업로드**")
            multi_files = st.file_uploader("주의! 5장 이하 업로드", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="auto_batch")
            
            if multi_files:
                current_file_ids = [f"{f.name}_{f.size}" for f in multi_files]
                if current_file_ids != st.session_state.get('last_files', []):
                    st.session_state.batch_visual_results = []
                    st.session_state.last_files = current_file_ids
                    
                    p_bar = st.progress(0)
                    status = st.empty()
                    for i, f in enumerate(multi_files):
                        status.text(f"분석 중: {f.name} ({i+1}/{len(multi_files)})")
                        file_bytes = np.frombuffer(f.read(), np.uint8)
                        img_raw = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                        if img_raw is None: continue
                        
                        img_ocr = resize_image(img_raw, 600)
                        ocr_res = reader.readtext(img_ocr, detail=0)
                        found = re.findall(r'\d{4}', "".join(ocr_res))
                        n = found[-1] if found else "실패"
                        
                        is_v, kt, _ = check_violation(n)
                        name, dept = get_car_info(n)
                        
                        h_r, w_r = img_raw.shape[:2]
                        thumb = cv2.resize(img_raw, (150, int(h_r * (150 / w_r))))
                        
                        st.session_state.batch_visual_results.append({
                            "img_base64": opencv_to_base64(thumb), 
                            "점검시간": kt.strftime("%y-%m-%d %H:%M:%S"),
                            "차량번호": n, "성명": name, "부서": dept,
                            "판정": "위반" if is_v else "정상" if found else "실패"
                        })
                        p_bar.progress((i + 1) / len(multi_files))
                    status.success("✅ 분석 완료!")
                    st.rerun()

        if st.session_state.batch_text_results:
            st.markdown("---")
            st.write("### 📋 텍스트 분석 결과")
            st.table(pd.DataFrame(st.session_state.batch_text_results))
            if st.button("💾 위 결과 기록하기"):
                st.session_state.check_history.extend(st.session_state.batch_text_results)
                st.session_state.batch_text_results = []
                st.rerun()

        if st.session_state.batch_visual_results:
            st.markdown("---")
            st.write("### 📷 사진 분석 상세 결과")
            v_df = pd.DataFrame(st.session_state.batch_visual_results).drop(columns=['img_base64'])
            st.table(v_df)
            
            with st.expander("🖼️ 분석 사진 썸네일 보기"):
                cols = st.columns(5)
                for idx, item in enumerate(st.session_state.batch_visual_results):
                    with cols[idx % 5]:
                        color = "red" if item['판정'] == "위반" else "green" if item['판정'] == "정상" else "gray"
                        st.markdown(f"""
                            <div class="thumb-card">
                                <img src="{item['img_base64']}" class="thumb-img">
                                <div class="result-text">{item['차량번호']}</div>
                                <div class="result-text" style="color: {color};">{item['판정']}</div>
                            </div>
                        """, unsafe_allow_html=True)
            
            if st.button("💾 위 사진 내역 모두 기록하기", type="primary", key="save_batch_v"):
                for item in st.session_state.batch_visual_results:
                    if item['차량번호'] != "실패":
                        data = item.copy(); del data['img_base64']
                        st.session_state.check_history.append(data)
                st.session_state.batch_visual_results = []
                st.rerun()

# =========================
# 3. [탭 2] 및 [탭 3]
# =========================
with tab2:
    st.subheader("📊 오늘의 점검 내역")
    if st.session_state.check_history:
        h_df = pd.DataFrame(st.session_state.check_history).iloc[::-1]
        st.dataframe(h_df, use_container_width=True)
        csv = h_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 CSV 다운로드", data=csv, file_name=f"khepi_{datetime.datetime.now().strftime('%m%d')}.csv")
    else: st.write("기록이 없습니다.")
        
with tab3:
    st.info("💡 **KHEPI 차량 2부제 점검 가이드 Ver. 1.0**")
    
    st.markdown("""
    1. **시스템 목적**: 본 사이트는 차량 2부제 시행에 따라 KHEPI 직원 차량 및 위반 여부를 확인하기 위한 시스템입니다.
    <br><br>
    2. **사용권한과 책임**:
        * **권한**: 본 시스템에서 조회되는 정보는 업무목적으로만 사용해야 합니다.
        * **책임**: 차량번호 및 개인정보에 대한 외부유출을 엄격히 금지하며, 이를 위반하여 발생하는 모든 책임은 사용자 본인에게 있습니다.
    <br><br>
    3. **2부제 운영 원칙**:
        * **날짜가 [홀수]인 날**: 차량 번호 끝자리가 [짝수]면 위반입니다.
        * **날짜가 [짝수]인 날**: 차량 번호 끝자리가 [홀수]면 위반입니다.
    <br><br>
    4. **사용 방법**:
        * **조회**: 차량 번호 4자리를 직접 입력하거나 번호판 사진을 찍어 분석하세요.
        * **차번호 일괄입력**: 쉼표나 엔터로 구분된 4자리 숫자들을 한꺼번에 판별합니다.
        * **사진 일괄입력**: 여러 장의 사진을 올리면 썸네일과 함께 분석 결과를 보여줍니다.
        * **기록**: 판별 결과가 나오면 하단의 **[기록하기]** 버튼을 눌러 목록에 추가하세요.
    <br><br>
    5. **데이터 관리**:
        * 저장된 목록은 **[점검 누적 목록]** 탭에서 확인 및 CSV 파일로 다운로드할 수 있습니다.
        * **주의**: 브라우저 창을 닫거나 새로고침(F5)을 하면 저장된 목록이 사라지니 미리 다운로드하세요.
    """, unsafe_allow_html=True)
