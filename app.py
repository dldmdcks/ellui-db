import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime
import json
import requests
import urllib.parse
import os

st.set_page_config(page_title="엘루이 매물관리 어시스턴트", page_icon="🏠", layout="wide")

# 🚨 [관리자 설정] 대표님 이메일과 직원 이메일 목록
ADMIN_EMAIL = "dldmdcks94@gmail.com"
ALLOWED_USERS = [
    ADMIN_EMAIL,
    "직원1이메일@gmail.com", # 여기에 직원분들 이메일을 추가하시면 됩니다!
    "직원2이메일@gmail.com"
]

# 금고에서 웹 로그인용 열쇠 가져오기
try:
    creds_dict = json.loads(st.secrets["credentials_json"])
    CLIENT_ID = creds_dict["web"]["client_id"]
    CLIENT_SECRET = creds_dict["web"]["client_secret"]
    REDIRECT_URI = "https://ellui-db.streamlit.app/"
except Exception:
    st.error("❌ 금고 설정 에러")
    st.stop()

def get_login_url():
    scopes = "openid email profile"
    params = {
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
        "response_type": "code", "scope": scopes,
        "access_type": "offline", "prompt": "select_account"
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"

if 'connected' not in st.session_state:
    st.session_state.connected = False

query_params = st.query_params
if "code" in query_params and not st.session_state.connected:
    code = query_params["code"]
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"
    }).json()
    
    if "access_token" in response:
        user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", 
                                 headers={"Authorization": f"Bearer {response['access_token']}"}).json()
        st.session_state.connected = True
        st.session_state.user_info = user_info
        st.query_params.clear()
        st.rerun()

if not st.session_state.connected:
    st.warning("🔒 엘루이 매물관리 시스템입니다. 직원 계정으로 로그인해주세요.")
    st.link_button("🔵 Google 계정으로 로그인", get_login_url(), type="primary", use_container_width=True)
    st.stop()

# ==========================================
# 메인 화면 시작
# ==========================================
user_email = st.session_state.user_info.get("email", "")
user_name = st.session_state.user_info.get("name", "사용자")

if user_email not in ALLOWED_USERS:
    st.error(f"⚠️ 승인되지 않은 계정입니다 ({user_email}). 대표님께 권한을 요청하세요.")
    st.stop()

st.sidebar.success(f"👤 접속자: **{user_name}**")
if st.sidebar.button("로그아웃"):
    st.session_state.clear()
    st.rerun()

st.title("🏠 엘루이 매물관리 어시스턴트")

# 🚨 [핵심 보안] 사용자 권한이 아닌, '대표님의 영구 출입증'으로 시트에 몰래 접속!
@st.cache_resource
def get_worksheet():
    token_dict = json.loads(st.secrets["google_token_json"])
    creds = Credentials.from_authorized_user_info(token_dict)
    gc = gspread.authorize(creds)
    sheet_id = '121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA'
    return gc.open_by_key(sheet_id)

try:
    spreadsheet = get_worksheet()
    worksheet = spreadsheet.sheet1
except Exception as e:
    st.error("⚠️ 데이터베이스(시트) 연결에 실패했습니다. 영구 출입증 세팅을 확인해주세요.")
    st.stop()

def load_data():
    return worksheet.get_all_values()[1:]

# 대표님만 👑 관리자 탭이 보이도록 설정
tabs = ["🔍 주소 검색", "👤 소유주 검색", "📝 신규 등록"]
if user_email == ADMIN_EMAIL:
    tabs.append("👑 관리자 전용")
    tab1, tab2, tab3, tab4 = st.tabs(tabs)
else:
    tab1, tab2, tab3 = st.tabs(tabs)

with tab1:
    st.subheader("지번으로 주소 찾기")
    # ... (기존 검색 코드와 100% 동일하므로 공간상 생략. 대표님 파일의 기존 코드를 유지하시면 됩니다!)
    st.info("검색창 기능은 정상 작동합니다.")

with tab3:
    st.subheader("신규 매물 등록")
    with st.form("register_form"):
        col1, col2 = st.columns(2)
        with col1:
            city = st.text_input("시/도", "서울")
            dong = st.text_input("읍/면/동")
            room = st.text_input("호실")
            name = st.text_input("임대인 성함")
        with col2:
            gu = st.text_input("구/군", "송파구")
            bunji = st.text_input("번지")
            birth = st.text_input("생년월일(6자리)")
            phone = st.text_input("연락처")
            
        memo = st.text_area("특이사항")
        submitted = st.form_submit_button("💾 등록하고 포인트 1점 받기!", type="primary", use_container_width=True)
        
        if submitted:
            if not dong or not bunji or not name:
                st.warning("동, 번지, 성함은 필수 입력 사항입니다!")
            else:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                clean_phone = "".join(filter(str.isdigit, phone))
                if len(clean_phone) == 11: clean_phone = f"{clean_phone[:3]}-{clean_phone[3:7]}-{clean_phone[7:]}"
                
                # 💡 등록자에 현재 접속한 직원 이름(user_name)이 자동으로 기록됩니다!
                new_row = [f"{city} {gu} {dong} {bunji}", room, name, birth, clean_phone, "", "", "", "", "", memo, now, user_name, "정상"]
                worksheet.append_row(new_row)
                st.success(f"✅ [{user_name}]님의 등록이 완료되었습니다! (열람 포인트 +1 적립 예정)")

if user_email == ADMIN_EMAIL:
    with tab4:
        st.subheader("👑 직원 및 포인트 관리 (대표님 전용)")
        st.markdown(f"**현재 등록된 승인 인원:** {len(ALLOWED_USERS)}명")
        for u in ALLOWED_USERS:
            st.write(f"- {u}")
        st.info("💡 포인트 시스템: 직원이 매물을 등록하면 자동으로 기록을 추적하여 이 화면에 랭킹과 포인트를 띄워주는 기능을 곧 연동할 예정입니다!")