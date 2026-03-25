import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import json

# 🚨 [보안 방어막] 로그인 안 한 유저는 로비로 쫓아내기
if "connected" not in st.session_state or not st.session_state.connected:
    st.switch_page("app.py")

st.set_page_config(page_title="계약 보고 시스템", page_icon="📝", layout="wide")

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

# 직원 이름 가져오기 로직
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

# 💡 '계약보고' 시트가 없으면 자동으로 만들기
try: 
    ws_contract = ss.worksheet("계약보고")
except: 
    ws_contract = ss.add_worksheet(title="계약보고", rows="100", cols="12")
    ws_contract.append_row(["보고일시", "담당직원", "구분", "주소", "보증금", "월세", "입주일_계약기간", "계약일", "임대인명", "생년월일", "연락처", "특이사항"])

# --- 📝 UI: 계약 보고 폼 ---
st.title("📝 엘루이 신규 계약 보고")
st.write("계약 내용을 입력하고 제출하면 구글 시트에 자동 저장되며, 추후 사내 메신저(봇)로 알림이 전송됩니다.")

with st.form("contract_report_form", clear_on_submit=True):
    st.subheader("📌 계약 기본 정보")
    c1, c2 = st.columns([1, 3])
    deal_type = c1.radio("계약 구분", ["양타", "단타(대표님 공동)", "단타(외부 공동)"], horizontal=True)
    address = c2.text_input("📍 계약 주소 (동, 번지, 호수)", placeholder="예: 잠실동 249-3 303호")
    
    c3, c4 = st.columns(2)
    deposit = c3.text_input("💰 보증금", placeholder="예: 1억 5천 3백만원 (또는 2000만원)")
    rent = c4.text_input("💸 월세", placeholder="예: 12만원 (없으면 0원)")
    
    c5, c6 = st.columns(2)
    move_in_date = c5.text_input("🗓️ 입주일 (또는 계약기간)", placeholder="예: 26.04.27 ~ 28.04.26")
    contract_date = c6.text_input("✍️ 계약일", placeholder="예: 26.03.25 또는 협의")
    
    st.write("---")
    st.subheader("👤 임대인 정보")
    c7, c8, c9 = st.columns(3)
    landlord_name = c7.text_input("성함")
    landlord_birth = c8.text_input("생년월일 (6자리)", placeholder="예: 940101")
    landlord_phone = c9.text_input("연락처", placeholder="예: 010-1234-5678")
    
    memo = st.text_area("📋 비고 및 특이사항", placeholder="예: 임대인 계좌로 가계약금 100만원 입금 완료")
    
    submitted = st.form_submit_button("🚀 계약 결재 올리기 (데이터 저장)", type="primary", use_container_width=True)
    
    if submitted:
        if not address or not landlord_name:
            st.error("🚨 주소와 임대인 성함은 필수 입력 사항입니다!")
        else:
            now_kst = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')
            
            # 구글 시트에 새로운 행 추가
            new_row = [
                now_kst, user_name, deal_type, address, deposit, rent, 
                move_in_date, contract_date, landlord_name, landlord_birth, landlord_phone, memo
            ]
            ws_contract.append_row(new_row, value_input_option='USER_ENTERED')
            
            st.success("🎉 계약 보고가 구글 시트에 성공적으로 저장되었습니다!")
            st.balloons()
            
            # TODO: 워크 봇 연동 (여기에 추후 메신저 API 코드가 들어갈 예정입니다)
            st.info("💡 (준비 중) 추후 이 단계에서 워크 봇(메신저)으로 '새 계약 알림'이 자동 발송됩니다.")
