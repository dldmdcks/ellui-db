import streamlit as st
import gspread
from datetime import datetime
import json
import requests
import os

# 1. 웹사이트 기본 설정
st.set_page_config(page_title="엘루이 매물관리 어시스턴트", page_icon="🏠", layout="centered")

ALLOWED_USERS = ["dldmdcks94@gmail.com"]

# 2. 금고에서 열쇠 정보 가져오기
try:
    creds_str = st.secrets["credentials_json"]
    creds_dict = json.loads(creds_str)
    CLIENT_ID = creds_dict["web"]["client_id"]
    CLIENT_SECRET = creds_dict["web"]["client_secret"]
    REDIRECT_URI = "https://ellui-db.streamlit.app/"
except Exception as e:
    st.error("❌ 금고 설정 에러를 확인해주세요.")
    st.stop()

# 3. 로그인 URL 생성 함수
def get_login_url():
    return f"https://accounts.google.com/o/oauth2/v2/auth?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=openid%20email%20profile"

# 4. 로그인 상태 확인 (세션)
if 'connected' not in st.session_state:
    st.session_state.connected = False

# 5. 구글 로그인 결과(code) 처리
query_params = st.query_params
if "code" in query_params and not st.session_state.connected:
    code = query_params["code"]
    # 구글에 토큰(입장권) 요청
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    response = requests.post(token_url, data=data)
    tokens = response.json()
    
    if "access_token" in tokens:
        # 유저 정보 가져오기
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        user_response = requests.get(userinfo_url, headers=headers)
        user_info = user_response.json()
        
        st.session_state.connected = True
        st.session_state.user_info = user_info
        
        # 주소창 깔끔하게 정리 후 새로고침
        st.query_params.clear()
        st.rerun()

# 6. 로그인 전 화면 (버튼 표시)
if not st.session_state.connected:
    st.warning("🔒 보안 구역입니다. 엘루이 매물관리 시스템을 이용하시려면 본인인증이 필요합니다.")
    login_url = get_login_url()
    
    # 🚨 [핵심 해결] 링크(a) 안에 버튼(button)을 넣지 않고, 링크 자체를 버튼 모양으로 꾸몄습니다!
    st.markdown(f'''
        <div style="display: flex; justify-content: center; margin-top: 20px;">
            <a href="{login_url}" target="_top" style="background-color: #4285F4; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                🔵 Google 계정으로 로그인
            </a>
        </div>
    ''', unsafe_allow_html=True)
    st.stop()

# ==========================================
# 7. 여기서부터는 로그인 성공 시 보여질 메인 화면
# ==========================================
user_info = st.session_state.user_info
user_email = user_info.get("email", "")

# 권한 체크
if user_email not in ALLOWED_USERS:
    st.error(f"⚠️ 접속 권한이 없습니다. 대표님께 등록을 요청하세요. ({user_email})")
    st.stop()

# 사이드바 (로그아웃 기능)
st.sidebar.success(f"✅ 인증완료: **{user_info.get('name', '사용자')}** 님")
if st.sidebar.button("로그아웃"):
    st.session_state.clear()
    st.rerun()

st.title("🏠 엘루이 매물관리 어시스턴트")

# 구글 시트 연결을 위한 임시 파일 생성
if not os.path.exists('credentials.json'):
    with open('credentials.json', 'w', encoding='utf-8') as f:
        f.write(st.secrets["credentials_json"])

@st.cache_resource
def init_connection():
    gc = gspread.oauth(credentials_filename='credentials.json')
    sheet_id = '121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA'
    return gc.open_by_key(sheet_id).sheet1

try:
    worksheet = init_connection()
except Exception as e:
    st.error(f"⚠️ 구글 시트 연결 대기중 (정상입니다): {e}")
    st.stop()

def load_data():
    return worksheet.get_all_values()[1:]

# 메인 탭 기능 
tab1, tab2, tab3 = st.tabs(["🔍 주소 검색", "👤 소유주 검색", "📝 신규 등록"])

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

with tab3:
    st.subheader("신규 매물 등록")
    with st.form("register_form"):
        city = st.text_input("1. 시/도", "서울")
        gu = st.text_input("2. 구/군", "송파구")
        dong = st.text_input("3. 읍/면/동")
        bunji = st.text_input("4. 번지")
        room = st.text_input("5. 호실")
        name = st.text_input("6. 임대인 성함")
        birth = st.text_input("7. 생년월일")
        phone = st.text_input("8. 연락처")
        memo = st.text_area("9. 특이사항")
        submitted = st.form_submit_button("💾 등록하기", type="primary", use_container_width=True)
        
        if submitted:
            if not dong or not bunji or not room or not name:
                st.warning("동, 번지, 호실, 성함은 필수 입력 사항입니다!")
            else:
                clean_addr = f"{city.replace('서울특별시','서울')} {gu} {dong} {bunji}".strip()
                clean_phone = "".join(filter(str.isdigit, phone))
                if len(clean_phone) == 11: clean_phone = f"{clean_phone[:3]}-{clean_phone[3:7]}-{clean_phone[7:]}"
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                new_row = [clean_addr, room, name, birth, clean_phone, "", "", "", "", "", memo, now, "시스템(웹)", "정상"]
                try:
                    worksheet.append_row(new_row)
                    st.success(f"✅ {name}님의 데이터가 저장되었습니다!")
                except Exception as e:
                    st.error(f"저장 실패: {e}")