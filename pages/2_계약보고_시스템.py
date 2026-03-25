import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import json
import re

# 🚨 [보안 방어막] 로그인 안 한 유저는 로비로 쫓아내기
if "connected" not in st.session_state or not st.session_state.connected:
    st.switch_page("app.py")

st.set_page_config(page_title="계약 보고 시스템", page_icon="📝", layout="wide")

# --- 💡 대한민국 표준 행정구역 DB ---
KOREA_REGION_DATA = {
    "서울특별시": {
        "강남구": ["개포동", "논현동", "대치동", "도곡동", "삼성동", "세곡동", "수서동", "신사동", "압구정동", "역삼동", "율현동", "일원동", "자곡동", "청담동"],
        "강동구": ["강일동", "고덕동", "길동", "둔촌동", "명일동", "상일동", "성내동", "암사동", "천호동"],
        "송파구": ["가락동", "거여동", "마천동", "문정동", "방이동", "삼전동", "석촌동", "송파동", "신천동", "오금동", "잠실동", "장지동", "풍납동"],
    },
    "경기도": {"하남시": ["감일동", "위례동", "학암동"], "성남시": ["위례동", "창곡동"]},
}

# --- 💡 DB 연결 및 시트 세팅 ---
try:
    token_dict = json.loads(st.secrets["google_token_json"])
except Exception:
    st.error("❌ 금고 설정(Secrets)을 확인해주세요.")
    st.stop()

@st.cache_resource
def get_ss():
    creds = Credentials.from_authorized_user_info(token_dict)
    return gspread.authorize(creds).open_by_key('121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA')

ss = get_ss()

# 직원 이름 세팅
try:
    ws_staff = ss.worksheet("직원명단")
    staff_records = ws_staff.get_all_records()
    staff_dict = {str(row['이메일']).strip(): row['이름'] for row in staff_records}
except:
    staff_dict = {}

ADMIN_EMAIL = "dldmdcks94@gmail.com"
user_email = st.session_state.user_info.get("email", "")
user_name = "이응찬 대표" if user_email == ADMIN_EMAIL else staff_dict.get(user_email, "알수없는 직원")

# 💡 [핵심 패치] 메인 DB 연동을 위해 컬럼을 완벽히 쪼갠 새로운 시트 생성
try: 
    ws_contract = ss.worksheet("계약보고_DB")
except: 
    ws_contract = ss.add_worksheet(title="계약보고_DB", rows="100", cols="19")
    # 메인 DB와 동기화하기 좋게 주소와 날짜를 철저히 분리
    ws_contract.append_row([
        "보고일시", "담당직원", "구분", 
        "시도", "시군구", "법정동", "본번", "부번", "동", "호수", 
        "보증금", "월세", "입주일", "만기일", "계약일", 
        "임대인명", "생년월일", "연락처", "특이사항"
    ])

# --- 📝 UI: 계약 보고 폼 ---
st.title("📝 엘루이 신규 계약 보고")
st.write("계약 내용을 입력하면 메인 DB와 동일한 규격으로 자동 분류되어 저장됩니다.")

today_str = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y.%m.%d')

with st.form("contract_report_form", clear_on_submit=False):
    st.subheader("📌 계약 기본 정보")
    
    deal_type = st.radio("연결 구분", ["양타", "단타"], horizontal=True)
    
    st.markdown("📍 **주소 입력**")
    c_loc1, c_loc2, c_loc3 = st.columns(3)
    sido_opts = list(KOREA_REGION_DATA.keys())
    sido = c_loc1.selectbox("시/도", sido_opts, index=0)
    
    gu_opts = list(KOREA_REGION_DATA[sido].keys()) if sido in KOREA_REGION_DATA else ["전체"]
    gu = c_loc2.selectbox("시/군/구", gu_opts, index=gu_opts.index("송파구") if "송파구" in gu_opts else 0)
    
    dong_opts = KOREA_REGION_DATA[sido][gu] if gu in KOREA_REGION_DATA[sido] else ["직접입력"]
    dong = c_loc3.selectbox("법정동", dong_opts + ["➕직접 입력"], index=dong_opts.index("방이동") if "방이동" in dong_opts else 0)
    if dong == "➕직접 입력": dong = st.text_input("법정동 직접 입력")

    c_loc4, c_loc5, c_loc6 = st.columns([2, 1, 2])
    bunji = c_loc4.text_input("번지 (예: 28-2)", placeholder="28-2")
    sub_dong = c_loc5.text_input("동 (없으면 빈칸)", placeholder="A동")
    room = c_loc6.text_input("호수 (숫자만)", placeholder="205")

    st.write("---")
    st.markdown("💰 **금액 및 기간**")
    c_mon1, c_mon2 = st.columns(2)
    deposit = c_mon1.text_input("보증금 (원 단위 숫자만)", placeholder="10000000")
    rent = c_mon2.text_input("월세 (원 단위 숫자만, 없으면 0)", placeholder="1000000")
    
    c_date1, c_date2, c_date3 = st.columns(3)
    contract_date = c_date1.text_input("✍️ 계약일 (자동입력)", value=today_str, disabled=True)
    move_in = c_date2.text_input("🗓️ 입주일", placeholder="2026.04.10")
    move_out = c_date3.text_input("🗓️ 퇴실일 (만기일)", placeholder="2028.04.09")
    
    st.write("---")
    st.subheader("👤 임대인 정보")
    c_info1, c_info2, c_info3 = st.columns(3)
    landlord_name = c_info1.text_input("성함", placeholder="이응찬")
    landlord_birth = c_info2.text_input("생년월일 (6자리 숫자만)", placeholder="941022")
    
    # 💡 단타일 경우 힌트(placeholder) 자동 변경
    phone_ph = "임차측일 시 024214988 입력" if deal_type == "단타" else "01012345678"
    landlord_phone = c_info3.text_input("연락처 (숫자만 9~11자리)", placeholder=phone_ph)
    
    # 💡 단타일 경우 힌트(placeholder) 자동 변경
    memo_ph = "예: ㅇㅇㅇ부동산 공동중개" if deal_type == "단타" else "기타 특이사항 입력"
    memo = st.text_area("📋 비고 및 특별사항", placeholder=memo_ph)
    
    submitted = st.form_submit_button("🚀 계약 결재 올리기 (데이터 저장)", type="primary", use_container_width=True)
    
    if submitted:
        # 1. 금액 숫자 확인
        if not deposit.isdigit() or not rent.isdigit():
            st.error("🚨 보증금과 월세는 '원'이나 콤마(,) 없이 오직 숫자만 입력해주세요!")
        # 2. 보증금 천원 단위 차단 (0 제외)
        elif deposit != "0" and not deposit.endswith("0000"):
            st.error("🚨 보증금 입력이 잘못되었습니다. (끝자리가 0000으로 끝나야 합니다.)")
        # 3. 이름 숫자 차단
        elif any(char.isdigit() for char in landlord_name):
            st.error("🚨 임대인 성함에는 숫자를 포함할 수 없습니다.")
        # 4. 생년월일 6자리 숫자 확인
        elif not landlord_birth.isdigit() or len(landlord_birth) != 6:
            st.error("🚨 생년월일은 6자리의 숫자만 입력해주세요. (예: 941022)")
        # 5. 연락처 9~11자리 숫자 확인
        elif not landlord_phone.isdigit() or not (9 <= len(landlord_phone) <= 11):
            st.error("🚨 연락처는 9~11자리의 숫자만 입력해주세요. (하이픈 - 제외)")
        # 6. 필수 항목 누락 검사
        elif not bunji or not room or not landlord_name or not move_in or not move_out:
            st.error("🚨 번지, 호수, 입주/퇴실일, 임대인 성함은 필수 입력 사항입니다!")
        else:
            # 💡 번지 쪼개기 (본번 / 부번)
            if "-" in bunji:
                bon, bu = bunji.split("-", 1)
            else:
                bon, bu = bunji, "0"
                
            # 💡 동/호수 규격화
            d_dong = "동없음" if not sub_dong else (f"{sub_dong}동" if not sub_dong.endswith("동") else sub_dong)
            r_ho = f"{room}호" if not room.endswith("호") else room
                
            now_kst = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')
            
            # 메인 DB와 완벽하게 1:1 대응되는 배열 세팅
            new_row = [
                now_kst, user_name, deal_type, 
                sido, gu, dong, bon, bu, d_dong, r_ho, 
                deposit, rent, move_in, move_out, contract_date, 
                landlord_name, landlord_birth, landlord_phone, memo
            ]
            ws_contract.append_row(new_row, value_input_option='USER_ENTERED')
            
            st.success("🎉 완벽합니다! 계약 데이터가 메인 DB 규격에 맞춰 분리 저장되었습니다!")
            st.balloons()
