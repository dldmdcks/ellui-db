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

# --- 💡 대한민국 표준 행정구역 DB (신규 등록과 동일) ---
KOREA_REGION_DATA = {
    "서울특별시": {
        "강남구": ["개포동", "논현동", "대치동", "도곡동", "삼성동", "세곡동", "수서동", "신사동", "압구정동", "역삼동", "율현동", "일원동", "자곡동", "청담동"],
        "강동구": ["강일동", "고덕동", "길동", "둔촌동", "명일동", "상일동", "성내동", "암사동", "천호동"],
        "송파구": ["가락동", "거여동", "마천동", "문정동", "방이동", "삼전동", "석촌동", "송파동", "신천동", "오금동", "잠실동", "장지동", "풍납동"],
        # 필요 시 다른 구 추가 가능 (앱 속도를 위해 현재 송파구 위주 세팅)
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

if user_email == ADMIN_EMAIL:
    user_name = "이응찬 대표"
else:
    user_name = staff_dict.get(user_email, "알수없는 직원")

# 시트 확인/생성
try: 
    ws_contract = ss.worksheet("계약보고")
except: 
    ws_contract = ss.add_worksheet(title="계약보고", rows="100", cols="12")
    ws_contract.append_row(["보고일시", "담당직원", "구분", "주소", "보증금", "월세", "입주일_계약기간", "계약일", "임대인명", "생년월일", "연락처", "특이사항"])

# --- 📝 UI: 계약 보고 폼 ---
st.title("📝 엘루이 신규 계약 보고")
st.write("계약 내용을 입력하고 제출하면 Google 시트에 자동으로 저장되고, 이후 워크(봇)로 알림이 전송됩니다.")

# 오늘 날짜 (계약일 자동 세팅용)
today_str = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y.%m.%d')

with st.form("contract_report_form", clear_on_submit=False):
    st.subheader("📌 계약 기본 정보")
    
    deal_type = st.radio("연결 구분", ["양타", "단타(대표님 공동)", "단타(외부 공동)"], horizontal=True)
    
    st.markdown("📍 **주소 입력 (동/번지/호수 분리)**")
    c_loc1, c_loc2, c_loc3 = st.columns(3)
    sido_opts = list(KOREA_REGION_DATA.keys())
    sido = c_loc1.selectbox("시/도", sido_opts, index=0)
    
    gu_opts = list(KOREA_REGION_DATA[sido].keys()) if sido in KOREA_REGION_DATA else ["전체"]
    gu = c_loc2.selectbox("시/군/구", gu_opts, index=gu_opts.index("송파구") if "송파구" in gu_opts else 0)
    
    dong_opts = KOREA_REGION_DATA[sido][gu] if gu in KOREA_REGION_DATA[sido] else ["직접입력"]
    dong = c_loc3.selectbox("법정동", dong_opts + ["➕직접 입력"], index=dong_opts.index("방이동") if "방이동" in dong_opts else 0)
    
    if dong == "➕직접 입력":
        dong = st.text_input("법정동 직접 입력")

    c_loc4, c_loc5, c_loc6 = st.columns([2, 1, 2])
    bunji = c_loc4.text_input("번지 (예: 28-2)", placeholder="28-2")
    sub_dong = c_loc5.text_input("동 (없으면 빈칸)", placeholder="A동")
    room = c_loc6.text_input("호수 (숫자만)", placeholder="205")

    st.write("---")
    st.markdown("💰 **금액 및 기간**")
    c_mon1, c_mon2 = st.columns(2)
    deposit = c_mon1.text_input("보증금 (원 단위 숫자만 입력)", placeholder="10000000")
    rent = c_mon2.text_input("월세 (원 단위 숫자만 입력, 없으면 0)", placeholder="1000000")
    
    c_date1, c_date2, c_date3 = st.columns(3)
    contract_date = c_date1.text_input("✍️ 계약일 (자동입력)", value=today_str, disabled=True)
    move_in = c_date2.text_input("🗓️ 입주일", placeholder="2026.04.10")
    move_out = c_date3.text_input("🗓️ 퇴실일 (만기일)", placeholder="2028.04.09")
    
    st.write("---")
    st.subheader("👤 임대인 정보")
    c_info1, c_info2, c_info3 = st.columns(3)
    landlord_name = c_info1.text_input("성함", placeholder="이응찬")
    landlord_birth = c_info2.text_input("생년월일 (6자리)", placeholder="941022")
    
    # 임대인 연락처 안내 문구 동적 변경
    ll_phone_ph = "모를 경우 회사번호(024214988) 입력" if "외부 공동" in deal_type else "01012345678"
    landlord_phone = c_info3.text_input("연락처 (숫자만)", placeholder=ll_phone_ph)
    
    memo = st.text_area("📋 비고 및 특별사항", placeholder="예: [ㅇㅇㅇ부동산 공동중개] 임대인 계좌로 가계약금 100만원 입금 완료")
    
    submitted = st.form_submit_button("🚀 계약 결재 올리기 (데이터 저장)", type="primary", use_container_width=True)
    
    if submitted:
        # 1. 금액 숫자 유효성 검사 (한글 '원' 포함 여부)
        if not deposit.isdigit() or not rent.isdigit():
            st.error("🚨 보증금과 월세는 '원'이나 콤마(,) 없이 **오직 숫자만** 입력해주세요!")
        
        # 2. 보증금 천원 단위 차단 (0원인 경우는 통과, 그 외엔 끝자리 0000 확인)
        elif deposit != "0" and not deposit.endswith("0000"):
            st.error("🚨 보증금 입력이 잘못되었습니다. (천원 단위 불가, 끝이 0000으로 끝나야 합니다.)")
            
        # 3. 필수 항목 검사
        elif not bunji or not room or not landlord_name or not move_in or not move_out:
            st.error("🚨 번지, 호수, 입주/퇴실일, 임대인 성함은 필수 입력 사항입니다!")
            
        else:
            # 주소 합치기
            full_address = f"{sido} {gu} {dong} {bunji}"
            if sub_dong: full_address += f" {sub_dong}"
            full_address += f" {room}호" if not room.endswith("호") else f" {room}"
            
            # 기간 합치기
            contract_period = f"{move_in} ~ {move_out}"
            
            # 연락처 (외부 공동인데 안 적었으면 회사번호 강제 배정)
            final_phone = landlord_phone
            if not final_phone and "외부 공동" in deal_type:
                final_phone = "02-421-4988"
                
            now_kst = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')
            
            # 구글 시트에 새로운 행 추가
            new_row = [
                now_kst, user_name, deal_type, full_address, deposit, rent, 
                contract_period, contract_date, landlord_name, landlord_birth, final_phone, memo
            ]
            ws_contract.append_row(new_row, value_input_option='USER_ENTERED')
            
            st.success("🎉 계약 보고가 성공적으로 저장되었습니다!")
            st.balloons()
