import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import json
import requests
import urllib.parse
import re
import pandas as pd

# 1. 웹사이트 기본 설정
st.set_page_config(page_title="엘루이 매물관리 어시스턴트", page_icon="🏠", layout="wide")
ADMIN_EMAIL = "dldmdcks94@gmail.com"

# 2. 로그인 및 DB 연결 설정
try:
    creds_dict = json.loads(st.secrets["credentials_json"])
    token_dict = json.loads(st.secrets["google_token_json"])
    CLIENT_ID = creds_dict["web"]["client_id"]
    CLIENT_SECRET = creds_dict["web"]["client_secret"]
    REDIRECT_URI = "https://ellui-db.streamlit.app/"
except Exception:
    st.error("❌ 금고 설정(Secrets)을 확인해주세요.")
    st.stop()

# 새로고침(F5) 로그아웃 방지 로직
if 'connected' not in st.session_state: 
    st.session_state.connected = False

query_params = st.query_params
if "session_token" in query_params and not st.session_state.connected:
    access_token = query_params["session_token"]
    user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", 
                             headers={"Authorization": f"Bearer {access_token}"}).json()
    if "email" in user_info:
        st.session_state.connected = True
        st.session_state.user_info = user_info

if "code" in query_params and not st.session_state.connected:
    code = query_params["code"]
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"
    }).json()
    if "access_token" in response:
        access_token = response['access_token']
        user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", 
                                 headers={"Authorization": f"Bearer {access_token}"}).json()
        st.session_state.connected = True
        st.session_state.user_info = user_info
        st.query_params["session_token"] = access_token
        st.rerun()

if not st.session_state.connected:
    st.warning("🔒 엘루이 매물관리 시스템입니다. 본인인증 후 이용해주세요.")
    login_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=openid%20email%20profile&access_type=offline&prompt=select_account"
    st.link_button("🔵 Google 계정으로 로그인", login_url, type="primary", use_container_width=True)
    st.stop()

# 3. 데이터베이스 연동 및 시트 객체 생성
@st.cache_resource
def get_ss():
    creds = Credentials.from_authorized_user_info(token_dict)
    return gspread.authorize(creds).open_by_key('121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA')

ss = get_ss()
ws_data = ss.sheet1

try: ws_staff = ss.worksheet("직원명단")
except: 
    ws_staff = ss.add_worksheet(title="직원명단", rows="100", cols="6")
    ws_staff.append_row(["이메일", "이름", "등록일", "보유토큰", "관리건물"])

try: ws_request = ss.worksheet("수정요청")
except: 
    ws_request = ss.add_worksheet(title="수정요청", rows="100", cols="6")
    ws_request.append_row(["요청일시", "요청직원", "대상주소", "대상호실", "요청내용", "처리상태"])

try: ws_history = ss.worksheet("토큰내역")
except:
    ws_history = ss.add_worksheet(title="토큰내역", rows="100", cols="5")
    ws_history.append_row(["일시", "직원명", "변동량", "잔여토큰", "사유_상세"])

# --- 💡 트래픽 방어: 데이터 캐싱 (1분마다 갱신 또는 변경 시 갱신) ---
@st.cache_data(ttl=60)
def fetch_all_data():
    return ws_data.get_all_values(), ws_staff.get_all_records(), ws_request.get_all_values(), ws_history.get_all_values()

all_data_raw, staff_records, req_all_values, history_all_values = fetch_all_data()

# 권한 체크 및 사용자 매핑
staff_dict = {str(row['이메일']).strip(): row for row in staff_records}
ALLOWED_USERS = [ADMIN_EMAIL] + list(staff_dict.keys())

user_email = st.session_state.user_info.get("email", "")
if user_email not in ALLOWED_USERS:
    st.error(f"⚠️ 승인되지 않은 계정입니다 ({user_email}). 대표님께 권한을 요청하세요.")
    st.stop()

if user_email == ADMIN_EMAIL:
    user_name, user_tokens, staff_row_index = "이응찬 대표", 9999, None
else:
    user_name = staff_dict[user_email]['이름']
    user_tokens = int(staff_dict[user_email].get('보유토큰', 0))
    staff_row_index = list(staff_dict.keys()).index(user_email) + 2 

history_records = history_all_values[1:]

# --- 💡 전담 관리 건물 매핑 ---
MANAGER_BUILDINGS = {}
for r in staff_records:
    buildings = str(r.get('관리건물', '')).split(',')
    for b in buildings:
        b = b.strip()
        if b: MANAGER_BUILDINGS[b] = r['이름']

# --- 헬퍼 함수 모음 ---
def clean_numeric(text): return re.sub(r'[^0-9]', '', str(text))
def clean_bunji(text): return re.sub(r'[^0-9-]', '', str(text))
def extract_room_number(room_str):
    nums = clean_numeric(room_str)
    return int(nums) if nums else 99999
def format_phone(text):
    nums = clean_numeric(text)
    if len(nums) == 11: return f"{nums[:3]}-{nums[3:7]}-{nums[7:]}"
    elif len(nums) == 10: return f"{nums[:3]}-{nums[3:6]}-{nums[6:]}"
    return nums

def extract_tags(memo):
    tags = []
    if not memo: return ""
    m = str(memo).strip()
    if any(k in m for k in ["애완", "반려", "강아지", "고양이"]): tags.append("🐶애완")
    if "주차" in m: tags.append("🚗주차")
    if "전입" in m: tags.append("✅전입")
    if "대출" in m: tags.append("🏦대출")
    return " ".join(tags)

def update_token(amount, reason):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_token_val = user_tokens + amount
    if staff_row_index:
        ws_staff.update_cell(staff_row_index, 4, new_token_val)
    ws_history.append_row([now, user_name, amount, new_token_val, reason])
    st.cache_data.clear() # 캐시 초기화 (트래픽 방어용)
    st.cache_resource.clear()

def is_unlocked_recently(addr, room):
    if user_email == ADMIN_EMAIL: return True
    now = datetime.now()
    search_str = f"({addr} {room})"
    for r in reversed(history_records):
        if len(r) > 4 and r[1] == user_name and search_str in r[4] and str(r[2]) == "-1":
            try:
                record_time = datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S')
                if (now - record_time).total_seconds() <= 86400: return True
            except: continue
    return False

# --- 💡 수정요청 중인 매물 파악 (Lock 용도) ---
pending_reqs_with_idx = [(i+1, r) for i, r in enumerate(req_all_values) if i > 0 and len(r) > 5 and r[5] == '대기중']
pending_req_count = len(pending_reqs_with_idx)
pending_set = {(r[2], r[3]) for _, r in pending_reqs_with_idx}

# --- 💡 메인 DB 가져오기 & 최신 데이터 필터링(중복 제거) ---
all_records_raw = all_data_raw[1:]
temp_dict = {}

for i, r in enumerate(all_records_raw):
    row_idx = i + 2 
    status = r[13].strip() if len(r) > 13 else "정상"
    
    # 일반 직원은 '비공개'와 '잘못됨(삭제)' 매물을 아예 못 봄
    if user_email != ADMIN_EMAIL and status in ["비공개", "삭제", "잘못됨"]:
        continue
        
    r_padded = (r + [""]*14)[:14]
    if not r_padded[13]: r_padded[13] = "정상"
    r_padded.append(row_idx)
    
    key = (str(r_padded[0]).replace(" ",""), str(r_padded[1]).replace(" ",""), str(r_padded[2]), str(r_padded[4]))
    temp_dict[key] = r_padded 

all_records = list(temp_dict.values())
all_records.reverse()

# --- 사이드바 ---
st.sidebar.markdown(f"### 👤 {user_name}")
st.sidebar.metric(label="내 보유 토큰", value=f"{user_tokens} 개")
st.sidebar.caption("💡 매달 기여도에 따라서 토큰 지급")
st.sidebar.write("---")

with st.sidebar.expander("📜 내 토큰 이용 내역"):
    my_history = [r for r in history_records if r[1] == user_name]
    if my_history:
        df_my_hist = pd.DataFrame(my_history, columns=["일시", "직원명", "변동", "잔여", "사유"])
        st.dataframe(df_my_hist[["일시", "변동", "사유"]].tail(10).iloc[::-1], hide_index=True)
    else: st.write("내역이 없습니다.")

if user_email == ADMIN_EMAIL and pending_req_count > 0:
    st.sidebar.error(f"🚨 대기중인 수정 요청: {pending_req_count}건")

st.sidebar.write("---")
if st.sidebar.button("로그아웃"):
    st.query_params.clear()
    st.session_state.clear()
    st.rerun()

if "addr_search_res" not in st.session_state: st.session_state.addr_search_res = None
if "owner_search_res" not in st.session_state: st.session_state.owner_search_res = None

tabs_list = ["🔍 주소 검색", "👤 소유주 검색", "📝 신규 등록"]
if user_email == ADMIN_EMAIL: tabs_list.append("👑 관리자 전용")
tabs = st.tabs(tabs_list)

# --- [탭 1] 주소 검색 ---
with tabs[0]:
    c1, c2, c3 = st.columns([2, 2, 1])
    d = c1.text_input("동/건물명", key="t1_dong", placeholder="방이동")
    b = c2.text_input("번지", key="t1_bunji", placeholder="28-2")
    r_search = c3.text_input("호실", key="t1_room", placeholder="101")
    
    if st.button("주소 검색", use_container_width=True, type="primary"):
        res = [
            r for r in all_records 
            if (d.replace(" ","") in r[0].replace(" ","")) 
            and (b.replace(" ","") in r[0].replace(" ",""))
            and (r_search in r[1])
        ]
        # 💡 호수 기준 오름차순(낮은 층부터) 칼각 정렬
        res.sort(key=lambda x: extract_room_number(x[1]))
        st.session_state.addr_search_res = res
    
    if st.session_state.addr_search_res is not None:
        st.caption(f"검색 결과: {len(st.session_state.addr_search_res)}건")
        
        for idx, row in enumerate(st.session_state.addr_search_res):
            addr, room, name, birth, phone, deposit, rent, end_date, _, _, memo, reg_date, registrar, status, row_idx = row
            
            # 관리 건물 체크
            manager_name = next((m for b, m in MANAGER_BUILDINGS.items() if b in addr), None)
            is_manager_locked = manager_name and manager_name != user_name and user_email != ADMIN_EMAIL
            
            # 상태 및 태그 설정
            status_text = f" 🚨[{status}]" if status in ["비공개", "잘못됨", "삭제"] else ""
            old_tag = " | 🗄️ 기존 누적 DB" if "2020-" in str(reg_date) else ""
            m_tag = f" | 👑 {manager_name} 관리매물" if manager_name else ""
            hash_tags = extract_tags(memo)
            
            # UI 다이어트: 얇은 한 줄 출력
            st.markdown(f"**📍 {addr} | {room}{old_tag}{status_text}{m_tag}**")
            if hash_tags: st.caption(f"✨ {hash_tags}")
            
            if is_manager_locked:
                st.error(f"🔒 {manager_name} 전담 매물입니다. (열람 불가)")
                st.write("---")
                continue
                
            is_pending = (addr, room) in pending_set
            if is_pending and user_email != ADMIN_EMAIL:
                st.warning("⏳ 정보 확인/수정요청 중인 매물입니다. (열람 일시중지)")
                st.write("---")
                continue

            unlock_key = f"unlock_addr_{addr}_{room}"
            toggle_key = f"toggle_addr_{idx}"
            is_no_phone = ("연락처 없음" in str(phone))
            free_unlock = is_unlocked_recently(addr, room)
            
            is_unlocked = free_unlock or st.session_state.get(unlock_key, False)
            
            if is_no_phone:
                if st.button("📞 연락처 없음 / 추가하기", key=f"btn_no_ph_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                
                if st.session_state.get(toggle_key, False):
                    with st.form(f"report_{idx}", clear_on_submit=True):
                        new_phone = st.text_input("알아낸 진짜 연락처 입력")
                        if st.form_submit_button("🏆 제보하고 토큰받기"):
                            if new_phone:
                                ws_request.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, addr, room, f"[제보] {new_phone}", "대기중"])
                                st.cache_data.clear()
                                st.success("제보 완료! 승인 시 토큰 지급")
                                st.rerun()
            elif is_unlocked:
                # 💡 아코디언 방식 (재열람)
                if st.button("🔓 재열람가능", key=f"btn_re_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                
                if st.session_state.get(toggle_key, False):
                    st.info(f"**소유주:** {name}({birth}) | **연락처:** {phone}\n\n**보증/월세:** {deposit}/{rent} | **만기:** {end_date}\n\n**특이사항:** {memo}")
                    
                    with st.form(f"edit_addr_{idx}", clear_on_submit=True):
                        edit_memo = st.text_input("수정 요청 사유 (예: 번호오류)", key=f"req_{idx}")
                        if st.form_submit_button("🛠️ 수정요청하기"):
                            if edit_memo:
                                ws_request.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, addr, room, edit_memo, "대기중"])
                                st.cache_data.clear()
                                st.success("요청 전송됨!")
                                st.rerun()
            else:
                if st.button("🔓 상세정보 열람 (토큰 1개)", key=f"btn_addr_{idx}"):
                    if user_tokens >= 1:
                        update_token(-1, f"매물 열람 ({addr} {room})")
                        st.session_state[unlock_key] = True
                        st.session_state[toggle_key] = True # 열람 즉시 펼치기
                        st.rerun()
                    else: st.error("토큰이 부족합니다.")
            st.write("---")

# --- [탭 2] 소유주 검색 ---
with tabs[1]:
    c4, c5 = st.columns(2); sn = c4.text_input("성함", key="t2_name"); sb = c5.text_input("생년월일(6자리)", key="t2_birth")
    if st.button("소유주 검색", use_container_width=True, type="primary"):
        res = [r for r in all_records if (sn in r[2]) and (not sb or sb == r[3])]
        res.sort(key=lambda x: extract_room_number(x[1]))
        st.session_state.owner_search_res = res
        
    if st.session_state.owner_search_res is not None:
        st.caption(f"검색 결과: {len(st.session_state.owner_search_res)}건")
        for idx, row in enumerate(st.session_state.owner_search_res):
            addr, room, name, birth, phone, deposit, rent, end_date, _, _, memo, reg_date, registrar, status, row_idx = row
            
            manager_name = next((m for b, m in MANAGER_BUILDINGS.items() if b in addr), None)
            is_manager_locked = manager_name and manager_name != user_name and user_email != ADMIN_EMAIL
            status_text = f" 🚨[{status}]" if status in ["비공개", "잘못됨", "삭제"] else ""
            m_tag = f" | 👑 {manager_name} 관리매물" if manager_name else ""
            
            st.markdown(f"**👤 {name}({birth}) | 📍 {addr} {room}{status_text}{m_tag}**")
            
            if is_manager_locked:
                st.error(f"🔒 {manager_name} 전담 매물입니다.")
                st.write("---")
                continue
                
            is_pending = (addr, room) in pending_set
            if is_pending and user_email != ADMIN_EMAIL:
                st.warning("⏳ 수정요청 중 (열람 일시중지)")
                st.write("---")
                continue

            unlock_key = f"unlock_own_{addr}_{room}"
            toggle_key = f"toggle_own_{idx}"
            is_no_phone = ("연락처 없음" in str(phone))
            free_unlock = is_unlocked_recently(addr, room)
            is_unlocked = free_unlock or st.session_state.get(unlock_key, False)
            
            if is_no_phone:
                if st.button("📞 연락처 없음 / 추가하기", key=f"btn_own_no_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                if st.session_state.get(toggle_key, False):
                    with st.form(f"report_own_{idx}", clear_on_submit=True):
                        new_phone = st.text_input("진짜 연락처 입력")
                        if st.form_submit_button("🏆 제보하고 토큰받기"):
                            if new_phone:
                                ws_request.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, addr, room, f"[제보] {new_phone}", "대기중"])
                                st.cache_data.clear()
                                st.success("제보 완료!")
                                st.rerun()
            elif is_unlocked:
                if st.button("🔓 재열람가능", key=f"btn_re_own_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                if st.session_state.get(toggle_key, False):
                    st.info(f"**연락처:** {phone} | **만기/보증/월세:** {end_date} / {deposit} / {rent}\n\n**특이사항:** {memo}")
                    with st.form(f"edit_own_{idx}", clear_on_submit=True):
                        edit_memo = st.text_input("사유", key=f"req_own_{idx}")
                        if st.form_submit_button("🛠️ 수정요청하기"):
                            if edit_memo:
                                ws_request.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, addr, room, edit_memo, "대기중"])
                                st.cache_data.clear()
                                st.success("요청 완료!")
                                st.rerun()
            else:
                if st.button("🔓 상세정보 열람 (토큰 1개)", key=f"btn_own_{idx}"):
                    if user_tokens >= 1:
                        update_token(-1, f"매물 열람 ({addr} {room})")
                        st.session_state[unlock_key] = True
                        st.session_state[toggle_key] = True
                        st.rerun()
                    else: st.error("토큰 부족")
            st.write("---")

# --- [탭 3] 신규 등록 ---
with tabs[2]:
    st.subheader("📝 신규 등록 (완료 시 토큰 +1)")
    with st.form("reg_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            f_city = st.text_input("시/도", "서울")
            f_dong = st.text_input("읍/면/동 *", placeholder="방이동")
            f_bunji = st.text_input("번지 *", placeholder="28-2")
            f_sub_dong = st.text_input("번지 뒤 '동' (없으면 0)", value="0")
            f_deposit = st.text_input("보증금 (만원)")
            f_rent = st.text_input("월세 (만원)")
        with col2:
            f_gu = st.text_input("구/군", "송파구")
            f_room = st.text_input("호실 * (숫자만)", placeholder="101")
            f_name = st.text_input("임대인 성함 *")
            f_birth = st.text_input("생년월일 * (숫자만)", placeholder="940101")
            f_phone = st.text_input("연락처 * (숫자만)", placeholder="01012345678")
            f_end_date = st.text_input("현 만기일", placeholder="2026-05-30")
        f_memo = st.text_area("특이사항")
        
        if st.form_submit_button("💾 데이터 등록", type="primary", use_container_width=True):
            if not f_room.isdigit() or not f_birth.isdigit() or not f_phone.isdigit():
                st.error("⚠️ 호실, 생년월일, 연락처는 숫자만 입력하세요.")
            elif not f_dong or not f_bunji or not f_name:
                st.warning("⚠️ 필수 항목(*) 입력 요망.")
            else:
                full_addr = f"{f_city} {f_gu} {f_dong} {clean_bunji(f_bunji)}"
                room_final = f"{f_sub_dong}동 {f_room}호" if f_sub_dong != "0" else f"{f_room}호"
                
                # '잘못됨(삭제)'이나 '비공개'가 아닌 정상 매물 중에 중복이 있는지 검사
                duplicate = [r for r in all_records if r[0] == full_addr and r[1] == room_final and r[12] == user_name and r[13] == "정상"]
                if duplicate:
                    st.error(f"❌ 이미 등록된 정상 매물입니다!")
                else:
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    new_row = [full_addr, room_final, f_name, f_birth, format_phone(f_phone), f_deposit, f_rent, f_end_date, "", "미분류", f_memo, now, user_name, "정상"]
                    ws_data.append_row(new_row)
                    update_token(1, f"신규 등록 ({full_addr} {room_final})")
                    st.success("✅ 등록 완료! 토큰 +1 💰")
                    st.rerun()

# --- [탭 4] 관리자 전용 ---
if user_email == ADMIN_EMAIL:
    with tabs[3]:
        c_title, c_btn = st.columns([4, 1])
        c_title.subheader("👑 관리자 종합 대시보드")
        if c_btn.button("🔄 최신 데이터 불러오기"):
            st.cache_data.clear()
            st.rerun()
            
        # 💡 통계 대시보드 계산 로직
        now_date = datetime.now()
        this_month_str = now_date.strftime("%Y-%m")
        this_year_str = now_date.strftime("%Y")
        
        new_db_m, up_db_m, del_db_m = 0, 0, 0
        new_db_y, up_db_y, del_db_y = 0, 0, 0
        
        for r in all_records_raw:
            reg = str(r[11]) if len(r) > 11 else ""
            stat = str(r[13]) if len(r) > 13 else "정상"
            
            if stat == "잘못됨": 
                if this_month_str in reg: del_db_m += 1
                if this_year_str in reg: del_db_y += 1
            elif "2020-" not in reg:
                # 2020년이 아닌 최근 데이터
                if this_month_str in reg: new_db_m += 1
                if this_year_str in reg: new_db_y += 1

        st.markdown("##### 📊 DB 자산 증식 현황")
        colA, colB, colC = st.columns(3)
        colA.metric("이번 달 확보/갱신된 DB", f"{new_db_m} 건")
        colB.metric("올해 누적 확보/갱신", f"{new_db_y} 건")
        colC.metric("이번 달 걸러낸 썩은 DB", f"{del_db_m} 건", delta="블랙리스트", delta_color="inverse")
        st.write("---")

        st.write("#### 🚨 직원 수정 요청 처리")
        if pending_reqs_with_idx:
            for row_idx, r_req in pending_reqs_with_idx:
                with st.container():
                    st.info(f"**[요청: {r_req[1]}]** 📍 {r_req[2]} {r_req[3]}  |  사유: {r_req[4]}")
                    cA, cB, cC = st.columns(3)
                    
                    if cA.button("✅ 수정 완료 (최신화)", key=f"ok_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "처리완료")
                        # 승인 시 메인 DB의 해당 매물 날짜를 오늘로 갱신 (부활)
                        for m_idx, m_row in enumerate(all_records_raw):
                            if m_row[0] == r_req[2] and m_row[1] == r_req[3]:
                                ws_data.update_cell(m_idx + 2, 12, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        st.cache_data.clear()
                        st.rerun()
                        
                    if cB.button("🔒 비공개 (숨김)", key=f"hide_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "비공개")
                        for m_idx, m_row in enumerate(all_records_raw):
                            if m_row[0] == r_req[2] and m_row[1] == r_req[3]:
                                ws_data.update_cell(m_idx + 2, 14, "비공개")
                        st.cache_data.clear()
                        st.rerun()
                        
                    if cC.button("🗑️ 영구 삭제 (잘못됨)", key=f"del_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "삭제")
                        # 블랙리스트 처리하여 직원망에서 차단, 재등록 방지
                        for m_idx, m_row in enumerate(all_records_raw):
                            if m_row[0] == r_req[2] and m_row[1] == r_req[3]:
                                ws_data.update_cell(m_idx + 2, 14, "잘못됨")
                        st.cache_data.clear()
                        st.rerun()
                st.write("---")
        else: st.info("대기 중인 요청이 없습니다.")
        
        st.write("---")
        st.write("#### 👥 직원 관리 및 포상")
        c_add, c_grant = st.columns(2)
        with c_add:
            with st.expander("➕ 신규 직원 등록"):
                new_email = st.text_input("구글 이메일")
                new_n = st.text_input("이름")
                start_token = st.number_input("초기 토큰", value=10)
                if st.button("권한 부여"):
                    if "@" in new_email and new_n:
                        ws_staff.append_row([new_email, new_n, datetime.now().strftime('%Y-%m-%d'), start_token, ""])
                        st.cache_data.clear()
                        st.success("추가됨!")
                        st.rerun()
        with c_grant:
            with st.expander("🎁 토큰 수동 지급"):
                target_staff = st.selectbox("직원", [row['이름'] for row in staff_records])
                grant_amount = st.number_input("수량", value=1)
                grant_reason = st.text_input("사유")
                if st.button("지급하기", type="primary"):
                    if grant_reason:
                        for i, r in enumerate(staff_records):
                            if r['이름'] == target_staff:
                                new_val = int(r.get('보유토큰', 0)) + grant_amount
                                ws_staff.update_cell(i + 2, 4, new_val)
                                ws_history.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), target_staff, grant_amount, new_val, f"포상: {grant_reason}"])
                                st.cache_data.clear()
                                st.success("지급 완료!")
                                st.rerun() 
                                break

        if staff_records: st.dataframe(pd.DataFrame(staff_records), use_container_width=True)