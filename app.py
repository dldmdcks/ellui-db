import streamlit as st
import gspread
from datetime import datetime
from streamlit_google_auth import Authenticate
import os

# 1. 웹사이트 기본 설정
st.set_page_config(page_title="엘루이 매물관리 어시스턴트", page_icon="🏠", layout="centered")

# --- 🚨 [핵심 해결] 기존 파일이 있든 없든 무조건 최신 열쇠로 덮어쓰기! ---
with open('credentials.json', 'w', encoding='utf-8') as f:
    f.write(st.secrets["credentials_json"])
# -----------------------------------------------------------------

# 2. 구글 로그인 및 권한 설정
ALLOWED_USERS = ["dldmdcks94@gmail.com"]

authenticator = Authenticate(
    secret_credentials_path='credentials.json',
    cookie_name='ellui_cookie',
    cookie_key='ellui_secret_key',
    redirect_uri='https://ellui-db.streamlit.app/'
)

# 로그인 체크 및 버튼 표시
authenticator.check_authentification()
authenticator.login()

# 3. 로그인 성공 시 메인 프로그램 실행
if st.session_state.get('connected'):
    user_info = st.session_state.get('user_info')
    user_email = user_info.get('email') if user_info else ""
    
    if user_email not in ALLOWED_USERS:
        st.error(f"⚠️ 접속 권한이 없습니다. 대표님께 등록을 요청하세요. ({user_email})")
        st.stop()

    st.sidebar.success(f"✅ 인증완료: **{user_info.get('name')}** 님")
    if st.sidebar.button("로그아웃"):
        authenticator.logout()

    st.title("🏠 엘루이 매물관리 어시스턴트")

    # --- 구글 시트 연결 ---
    @st.cache_resource
    def init_connection():
        # 💡 안내: 로그인이 뚫리고 나면 이 부분에서 에러가 날 수 있습니다!
        # (로봇 직원 계정 연결이라는 다음 단계가 필요하기 때문입니다)
        gc = gspread.oauth(credentials_filename='credentials.json')
        sheet_id = '121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA'
        return gc.open_by_key(sheet_id).sheet1

    try:
        worksheet = init_connection()
    except Exception as e:
        st.error(f"⚠️ 구글 시트 연결 실패 (정상적인 다음 단계입니다): {e}")
        st.stop()

    def load_data():
        return worksheet.get_all_values()[1:]

    # --- 검색 및 등록 탭 (기존 기능 100% 유지) ---
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

# 4. 로그인 전 화면
else:
    st.warning("🔒 보안 구역입니다. 엘루이 매물관리 시스템을 이용하시려면 구글 계정으로 본인인증이 필요합니다.")