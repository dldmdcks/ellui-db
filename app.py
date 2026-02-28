import streamlit as st
import gspread
from datetime import datetime

# 1. 웹사이트 기본 설정
st.set_page_config(page_title="엘루이 매물관리 어시스턴트", page_icon="🏠", layout="centered")
st.title("🏠 엘루이 매물관리 어시스턴트")

# 2. 구글 시트 연결
@st.cache_resource
def init_connection():
    gc = gspread.oauth(credentials_filename='credentials.json', authorized_user_filename='token.json')
    sheet_id = '121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA'
    return gc.open_by_key(sheet_id).sheet1

try:
    worksheet = init_connection()
except Exception as e:
    st.error(f"구글 시트 연결 실패: {e}")
    st.stop()

def load_data():
    return worksheet.get_all_values()[1:]

# 3. 탭 3개 만들기 (탭 이름도 주소 검색으로 변경)
tab1, tab2, tab3 = st.tabs(["🔍 주소 검색", "👤 소유주 검색", "📝 신규 등록"])

# ==========================================
# [탭 1] 주소 검색
# ==========================================
with tab1:
    st.subheader("지번으로 주소 찾기") # 부제목 변경
    col1, col2 = st.columns(2)
    with col1:
        search_dong = st.text_input("동 (예: 방이동)", key="dong")
    with col2:
        search_bunji = st.text_input("번지 (예: 28-2)", key="bunji")

    # 버튼 이름 변경
    if st.button("주소 검색", type="primary", use_container_width=True):
        dong = search_dong.replace(" ", "")
        bunji = search_bunji.replace(" ", "")
        
        if not dong and not bunji:
            st.warning("동이나 번지 중 하나는 꼭 입력해주세요!")
        else:
            records = load_data()
            results = []
            for row in records:
                if len(row) > 2:
                    db_addr = row[0].replace(" ", "")
                    if (dong in db_addr) and (bunji in db_addr):
                        results.append(row)
            
            if not results:
                st.info("조건에 맞는 매물이 없습니다.")
            else:
                st.success(f"총 {len(results)}개의 매물을 찾았습니다!")
                for row in results:
                    room_str = row[1] if "호" in row[1] else f"{row[1]}호"
                    with st.expander(f"📍 {row[0]} | {room_str} (소유주: {row[2]})"):
                        reg_date = row[11] if len(row) > 11 and row[11].strip() else "기록 없음"
                        st.markdown(f"""
                        * **👤 소유주:** {row[2]} ({row[3]})
                        * **📞 연락처:** {row[4]}
                        * **📝 특이사항:** {row[10]}
                        * **⏰ 등록일:** {reg_date}
                        """)

# ==========================================
# [탭 2] 소유주 검색
# ==========================================
with tab2:
    st.subheader("이름/생년월일로 소유주 찾기")
    col3, col4 = st.columns(2)
    with col3:
        search_name = st.text_input("성함", key="name")
    with col4:
        search_birth = st.text_input("생년월일(6자리)", key="birth")

    if st.button("소유주 검색", type="primary", use_container_width=True):
        name = search_name.replace("  ", "")
        birth = search_birth.replace(" ", "")
        
        if not name and not birth:
            st.warning("성함이나 생년월일을 입력해주세요!")
        else:
            records = load_data()
            results = []
            for row in records:
                if len(row) > 3:
                    db_name = row[2].replace(" ", "")
                    db_birth = row[3].replace(" ", "")
                    
                    match = True
                    if name and name not in db_name: match = False
                    if birth and birth != db_birth: match = False
                    
                    if match:
                        results.append(row)
            
            if not results:
                st.info("조건에 맞는 소유주가 없습니다.")
            else:
                st.success(f"총 {len(results)}개의 매물을 찾았습니다!")
                for row in results:
                    room_str = row[1] if "호" in row[1] else f"{row[1]}호"
                    with st.expander(f"👤 {row[2]} | 📍 {row[0]} {room_str}"):
                        reg_date = row[11] if len(row) > 11 and row[11].strip() else "기록 없음"
                        st.markdown(f"""
                        * **📞 연락처:** {row[4]}
                        * **📝 특이사항:** {row[10]}
                        * **⏰ 등록일:** {reg_date}
                        """)

# ==========================================
# [탭 3] 신규 등록
# ==========================================
with tab3:
    st.subheader("신규 매물 등록")
    with st.form("register_form"):
        city = st.text_input("1. 시/도 (예: 서울)", "서울")
        gu = st.text_input("2. 구/군 (예: 송파구)", "송파구")
        dong = st.text_input("3. 읍/면/동 (예: 방이동)")
        bunji = st.text_input("4. 번지 (예: 28-2)")
        room = st.text_input("5. 호실 (예: 101호)")
        name = st.text_input("6. 임대인 성함")
        birth = st.text_input("7. 생년월일 (6자리)")
        phone = st.text_input("8. 연락처 (숫자만)")
        memo = st.text_area("9. 특이사항")
        
        # 버튼 이름 깔끔하게 변경
        submitted = st.form_submit_button("💾 등록하기", type="primary", use_container_width=True)
        
        if submitted:
            if not dong or not bunji or not room or not name:
                st.warning("동, 번지, 호실, 성함은 필수 입력 사항입니다!")
            else:
                clean_city = city.replace("서울특별시", "서울").replace("경기도", "경기").strip()
                clean_addr = f"{clean_city} {gu.strip()} {dong.strip()} {bunji.strip()}".strip()
                
                clean_phone = "".join(filter(str.isdigit, phone))
                if len(clean_phone) == 11: 
                    clean_phone = f"{clean_phone[:3]}-{clean_phone[3:7]}-{clean_phone[7:]}"
                else: 
                    clean_phone = phone
                    
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                new_row = [clean_addr, room.strip(), name.strip(), birth.strip(), clean_phone, "", "", "", "", "", memo.strip(), now, "시스템(웹)", "정상"]
                
                try:
                    worksheet.append_row(new_row)
                    st.success(f"✅ {name}님의 데이터가 성공적으로 저장되었습니다! (주소: {clean_addr})")
                except Exception as e:
                    st.error(f"저장 실패: {e}")