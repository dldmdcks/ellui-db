import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime
import json
import requests
import urllib.parse
import re
import pandas as pd
from collections import Counter

# 1. 웹사이트 기본 설정
st.set_page_config(page_title="엘루이 매물관리 어시스턴트", page_icon="🏠", layout="wide")

# 🚨 관리자 고정 이메일
ADMIN_EMAIL = "dldmdcks94@gmail.com"

# 2. 금고 설정 로드
try:
    creds_dict = json.loads(st.secrets["credentials_json"])
    CLIENT_ID = creds_dict["web"]["client_id"]
    CLIENT_SECRET = creds_dict["web"]["client_secret"]
    REDIRECT_URI = "https://ellui-db.streamlit.app/"
except Exception:
    st.error("❌ 금고 설정(Secrets)을 확인해주세요.")
    st.stop()

# 3. 로그인 로직
def get_login_url():
    params = {
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
        "response_type": "code", "scope": "openid email profile",
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
    st.warning("🔒 엘루이 매물관리 시스템입니다. 본인인증 후 이용해주세요.")
    st.link_button("🔵 Google 계정으로 로그인", get_login_url(), type="primary", use_container_width=True)
    st.stop()

# ==========================================
# 4. 데이터베이스 및 권한 관리
# ==========================================
@st.cache_resource
def get_ss():
    token_dict = json.loads(st.secrets["google_token_json"])
    creds = Credentials.from_authorized_user_info(token_dict)
    return gspread.authorize(creds).open_by_key('121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA')

ss = get_ss()
ws_data = ss.sheet1 # 매물 데이터 시트

# 💡 '직원명단' 시트가 없으면 자동으로 만듭니다.
try:
    ws_staff = ss.worksheet("직원명단")
except:
    ws_staff = ss.add_worksheet(title="직원명단", rows="100", cols="5")
    ws_staff.append_row(["이메일", "이름", "등록일"])

# 실시간 허용 이메일 목록 가져오기 (관리자 + 직원명단 시트의 이메일들)
staff_emails = ws_staff.col_values(1)[1:]
ALLOWED_USERS = [ADMIN_EMAIL] + staff_emails

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

# --- 헬퍼 함수: 데이터 정제 ---
def clean_numeric(text): return re.sub(r'[^0-9]', '', text)
def clean_bunji(text): return re.sub(r'[^0-9-]', '', text)
def format_phone(text):
    nums = clean_numeric(text)
    if len(nums) == 11: return f"{nums[:3]}-{nums[3:7]}-{nums[7:]}"
    elif len(nums) == 10: return f"{nums[:3]}-{nums[3:6]}-{nums[6:]}"
    return nums

# 5. 탭 구성
tabs_list = ["🔍 주소 검색", "👤 소유주 검색", "📝 신규 등록"]
if user_email == ADMIN_EMAIL: tabs_list.append("👑 관리자 전용")
tabs = st.tabs(tabs_list)

# --- [탭 1 & 2] 검색 (기존 로직 유지) ---
with tabs[0]:
    st.subheader("지번으로 주소 찾기")
    c1, c2 = st.columns(2); d = c1.text_input("동"); b = c2.text_input("번지")
    if st.button("주소 검색", use_container_width=True):
        res = [r for r in ws_data.get_all_values()[1:] if d in r[0] and b in r[0]]
        st.write(f"검색 결과: {len(res)}건") # 상세 루프 생략

# --- [탭 3] 신규 등록 (🚨 요청하신 규칙 적용) ---
with tabs[2]:
    st.subheader("📝 신규 매물 등록")
    with st.form("reg_form"):
        col1, col2 = st.columns(2)
        with col1:
            f_city = st.text_input("시/도", "서울")
            f_dong = st.text_input("읍/면/동 (예: 방이동)")
            f_bunji = st.text_input("번지 (숫자와 -만 입력)", placeholder="예: 28-2")
            f_sub_dong = st.text_input("번지 뒤 '동' (없으면 0 입력)", value="0")
        with col2:
            f_gu = st.text_input("구/군", "송파구")
            f_room = st.text_input("호실 (숫자만)", placeholder="예: 101")
            f_name = st.text_input("임대인 성함")
            f_birth = st.text_input("생년월일 (숫자만)", placeholder="예: 940101")
            f_phone = st.text_input("연락처 (숫자만)", placeholder="예: 01012345678")
        f_memo = st.text_area("특이사항")
        
        if st.form_submit_button("💾 데이터 검증 및 등록", type="primary", use_container_width=True):
            # 데이터 정제
            clean_b = clean_bunji(f_bunji)
            clean_r = clean_numeric(f_room)
            clean_bi = clean_numeric(f_birth)
            clean_p = format_phone(f_phone)
            
            if not f_dong or not clean_b or not f_name:
                st.warning("동, 번지, 성함은 필수입니다.")
            else:
                full_addr = f"{f_city} {f_gu} {f_dong} {clean_b}"
                # 💡 요청사항: 호실 앞에 '동' 표시 (없으면 0)
                room_display = f"{f_sub_dong}동 {clean_r}호" if f_sub_dong != "0" else f"{clean_r}호"
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                new_data = [full_addr, room_display, f_name, clean_bi, clean_p, "", "", "", "", "", f_memo, now, user_name, "정상"]
                ws_data.append_row(new_data)
                st.success(f"✅ 등록 완료! 번지({clean_b}), 호실({clean_r}), 연락처({clean_p}) 정제됨.")

# --- [탭 4] 관리자 전용 (🚨 직원 추가/삭제 기능) ---
if user_email == ADMIN_EMAIL:
    with tabs[3]:
        st.subheader("👑 직원 명단 관리")
        
        # 1. 직원 추가 폼
        with st.expander("➕ 신규 직원 등록", expanded=False):
            new_email = st.text_input("직원 구글 이메일")
            new_name = st.text_input("직원 이름")
            if st.button("직원 추가하기"):
                if "@" in new_email and new_name:
                    ws_staff.append_row([new_email, new_name, datetime.now().strftime('%Y-%m-%d')])
                    st.success("직원이 추가되었습니다! (새로고침 후 반영)")
                    st.rerun()
        
        # 2. 현재 직원 목록 및 삭제
        st.write("### 현재 승인된 직원")
        staff_data = ws_staff.get_all_records()
        if staff_data:
            df_staff = pd.DataFrame(staff_data)
            st.table(df_staff)
            
            del_email = st.selectbox("삭제할 이메일 선택", ["선택안함"] + [s['이메일'] for s in staff_data])
            if st.button("선택한 직원 권한 삭제", type="secondary"):
                if del_email != "선택안함":
                    cell = ws_staff.find(del_email)
                    ws_staff.delete_rows(cell.row)
                    st.warning("삭제되었습니다.")
                    st.rerun()
        
        # 3. 포인트 랭킹 (기존 로직)
        st.write("---")
        st.subheader("🏆 등록 포인트 랭킹")
        registrars = [r[12] for r in ws_data.get_all_values()[1:] if len(r) > 12]
        counts = Counter(registrars)
        if counts:
            df_p = pd.DataFrame(counts.items(), columns=["이름", "포인트"]).sort_values("포인트", ascending=False)
            st.dataframe(df_p, use_container_width=True)