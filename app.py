import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime
import json
import requests
import urllib.parse
import os
from collections import Counter
import pandas as pd

# 1. 웹사이트 기본 설정
st.set_page_config(page_title="엘루이 매물관리 어시스턴트", page_icon="🏠", layout="wide")

# 🚨 [관리자 설정] 대표님 이메일과 직원 이메일 목록
ADMIN_EMAIL = "dldmdcks94@gmail.com"
ALLOWED_USERS = [
    ADMIN_EMAIL,
    "직원1이메일@gmail.com", # 여기에 직원분들 이메일을 추가하시면 됩니다!
    "직원2이메일@gmail.com"
]

# 2. 금고에서 웹 로그인용 열쇠 가져오기
try:
    creds_dict = json.loads(st.secrets["credentials_json"])
    CLIENT_ID = creds_dict["web"]["client_id"]
    CLIENT_SECRET = creds_dict["web"]["client_secret"]
    REDIRECT_URI = "https://ellui-db.streamlit.app/"
except Exception:
    st.error("❌ 금고 설정 에러를 확인해주세요.")
    st.stop()

# 3. 로그인 함수
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

# 4. 로그인 전 화면
if not st.session_state.connected:
    st.warning("🔒 엘루이 매물관리 시스템입니다. 직원 계정으로 로그인해주세요.")
    st.link_button("🔵 Google 계정으로 로그인", get_login_url(), type="primary", use_container_width=True)
    st.stop()

# ==========================================
# 5. 여기서부터 메인 화면 (로그인 성공)
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

# 🚨 대표님의 '영구 출입증'으로 시트에 백그라운드 접속!
@st.cache_resource
def get_worksheet():
    token_dict = json.loads(st.secrets["google_token_json"])
    creds = Credentials.from_authorized_user_info(token_dict)
    gc = gspread.authorize(creds)
    sheet_id = '121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA'
    return gc.open_by_key(sheet_id).sheet1

try:
    worksheet = get_worksheet()
except Exception as e:
    st.error("⚠️ 데이터베이스 연결 실패. 영구 출입증 세팅을 확인해주세요.")
    st.stop()

def load_data():
    return worksheet.get_all_values()[1:]

# 탭 구성 (대표님은 4개, 직원은 3개)
tabs = ["🔍 주소 검색", "👤 소유주 검색", "📝 신규 등록"]
if user_email == ADMIN_EMAIL:
    tabs.append("👑 관리자 전용")
    tab_objs = st.tabs(tabs)
    tab1, tab2, tab3, tab4 = tab_objs
else:
    tab_objs = st.tabs(tabs)
    tab1, tab2, tab3 = tab_objs

# --- [탭 1] 주소 검색 복구 ---
with tab1:
    st.subheader("지번으로 주소 찾기")
    col1, col2 = st.columns(2)
    with col1:
        search_dong = st.text_input("동 (예: 방이동)", key="dong")
    with col2:
        search_bunji = st.text_input("번지 (예: 28-2)", key="bunji")

    if st.button("주소 검색", type="primary", use_container_width=True):
        dong = search_dong.replace(" ", "")
        bunji = search_bunji.replace(" ", "")
        if not dong and not bunji:
            st.warning("동이나 번지 중 하나는 꼭 입력해주세요!")
        else:
            records = load_data()
            results = [row for row in records if len(row) > 2 and (dong in row[0].replace(" ", "")) and (bunji in row[0].replace(" ", ""))]
            if not results:
                st.info("조건에 맞는 매물이 없습니다.")
            else:
                st.success(f"총 {len(results)}개의 매물을 찾았습니다!")
                for row in results:
                    room_str = row[1] if "호" in row[1] else f"{row[1]}호"
                    with st.expander(f"📍 {row[0]} | {room_str} (소유주: {row[2]})"):
                        reg_date = row[11] if len(row) > 11 and row[11].strip() else "기록 없음"
                        st.markdown(f"* **👤 소유주:** {row[2]} ({row[3]})\n* **📞 연락처:** {row[4]}\n* **📝 특이사항:** {row[10]}\n* **⏰ 등록일:** {reg_date}")

# --- [탭 2] 소유주 검색 복구 ---
with tab2:
    st.subheader("이름/생년월일로 소유주 찾기")
    col3, col4 = st.columns(2)
    with col3:
        search_name = st.text_input("성함", key="name_search")
    with col4:
        search_birth = st.text_input("생년월일(6자리)", key="birth_search")

    if st.button("소유주 검색", type="primary", use_container_width=True):
        name = search_name.replace(" ", "")
        birth = search_birth.replace(" ", "")
        if not name and not birth:
            st.warning("성함이나 생년월일을 입력해주세요!")
        else:
            records = load_data()
            results = [row for row in records if len(row) > 3 and (not name or name in row[2].replace(" ", "")) and (not birth or birth == row[3].replace(" ", ""))]
            if not results:
                st.info("조건에 맞는 소유주가 없습니다.")
            else:
                st.success(f"총 {len(results)}개의 매물을 찾았습니다!")
                for row in results:
                    room_str = row[1] if "호" in row[1] else f"{row[1]}호"
                    with st.expander(f"👤 {row[2]} | 📍 {row[0]} {room_str}"):
                        reg_date = row[11] if len(row) > 11 and row[11].strip() else "기록 없음"
                        st.markdown(f"* **📞 연락처:** {row[4]}\n* **📝 특이사항:** {row[10]}\n* **⏰ 등록일:** {reg_date}")

# --- [탭 3] 신규 등록 ---
with tab3:
    st.subheader("신규 매물 등록 (포인트 적립)")
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
                
                # 등록자에 현재 접속한 직원 이름(user_name)이 자동으로 기록됩니다!
                new_row = [f"{city} {gu} {dong} {bunji}", room, name, birth, clean_phone, "", "", "", "", "", memo, now, user_name, "정상"]
                try:
                    worksheet.append_row(new_row)
                    st.success(f"✅ [{user_name}]님의 등록이 완료되었습니다! (포인트 +1 적립 완료 💰)")
                    # 캐시 초기화를 위해 재실행 (포인트 실시간 반영)
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

# --- [탭 4] 관리자 전용 (포인트 시스템) ---
if user_email == ADMIN_EMAIL:
    with tab4:
        st.subheader("👑 엘루이 직원 열람권 포인트 현황")
        st.write("---")
        
        records = load_data()
        point_list = []
        
        # 13번째 열(index 12)에 있는 '등록자 이름'을 가져와서 개수를 셉니다.
        for row in records:
            if len(row) > 12:
                registrar = row[12].strip()
                if registrar and registrar not in ["시스템(웹)", "등록자"]: 
                    point_list.append(registrar)
                    
        # 포인트 랭킹 계산
        point_counts = Counter(point_list)
        
        if point_counts:
            # 예쁘게 표(데이터프레임)로 만들기
            df_points = pd.DataFrame(point_counts.items(), columns=["직원 이름", "누적 포인트 (등록 건수)"])
            df_points = df_points.sort_values(by="누적 포인트 (등록 건수)", ascending=False).reset_index(drop=True)
            df_points.index = df_points.index + 1  # 순위 1부터 시작
            
            # 메달 달아주기
            st.markdown("### 🏆 이달의 포인트 랭킹")
            col1, col2, col3 = st.columns(3)
            ranks = list(point_counts.most_common(3))
            
            with col1:
                if len(ranks) > 0: st.success(f"🥇 1위: {ranks[0][0]} ({ranks[0][1]}점)")
            with col2:
                if len(ranks) > 1: st.info(f"🥈 2위: {ranks[1][0]} ({ranks[1][1]}점)")
            with col3:
                if len(ranks) > 2: st.warning(f"🥉 3위: {ranks[2][0]} ({ranks[2][1]}점)")
                
            st.dataframe(df_points, use_container_width=True)
        else:
            st.info("아직 앱을 통해 매물을 등록한 직원이 없습니다. 첫 등록을 기다립니다!")