import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import json
import requests
import urllib.parse
import re
import pandas as pd

# --- 💡 1. UI 다이어트: 탭 잘림 해결 & 폰트 밸런스 조정 ---
st.set_page_config(page_title="엘루이 매물관리 어시스턴트", page_icon="🏠", layout="wide")
st.markdown("""
    <style>
        /* 전체 폰트 크기 축소 */
        html, body, [class*="css"]  { font-size: 14px !important; }
        
        /* 버튼 크기 및 여백 축소 */
        .stButton>button { padding: 0.2rem 0.5rem; min-height: 2rem; }
        
        /* 💡 컨테이너 상단 여백 복구 (탭 글씨 잘림 방지) */
        .block-container { padding-top: 3.5rem; padding-bottom: 2rem; }
        
        /* 사이드바 크기 조정 */
        [data-testid="stSidebar"] { width: 280px !important; }
        
        /* 💡 탭 글자 크기 및 높이 확보 */
        button[data-baseweb="tab"] > div[data-testid="stMarkdownContainer"] > p { font-size: 15px; margin-bottom: 0px; }
        button[data-baseweb="tab"] { height: 3rem; }
    </style>
""", unsafe_allow_html=True)

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

# 트래픽 방어: 데이터 캐싱 (1분 갱신)
@st.cache_data(ttl=60)
def fetch_all_data():
    return ws_data.get_all_values(), ws_staff.get_all_records(), ws_request.get_all_values(), ws_history.get_all_values()

all_data_raw, staff_records, req_all_values, history_all_values = fetch_all_data()

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

MANAGER_BUILDINGS = {}
for r in staff_records:
    buildings = str(r.get('관리건물', '')).split(',')
    for b in buildings:
        b = b.strip()
        if b: MANAGER_BUILDINGS[b] = r['이름']

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

# 💡 자동 토큰 지급 헬퍼 함수
def update_token(target_name, amount, reason):
    if target_name == "이응찬 대표": return # 대표님은 토큰 무한
    target_idx = None
    for i, r in enumerate(staff_records):
        if r['이름'] == target_name:
            target_idx = i + 2
            old_token = int(r.get('보유토큰', 0))
            break
            
    if target_idx:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_token_val = old_token + amount
        ws_staff.update_cell(target_idx, 4, new_token_val)
        ws_history.append_row([now, target_name, amount, new_token_val, reason])

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

pending_reqs_with_idx = [(i+1, r) for i, r in enumerate(req_all_values) if i > 0 and len(r) > 5 and r[5] == '대기중']
pending_req_count = len(pending_reqs_with_idx)
pending_set = {(r[2], r[3]) for _, r in pending_reqs_with_idx}

all_records_raw = all_data_raw[1:]
temp_dict = {}

# 💡 기여도 계산을 위한 내 점수 파악 (사이드바 표시용)
my_month_score = 0
now_date = datetime.now()
this_month_str = now_date.strftime("%Y-%m")

for r in all_records_raw:
    reg = str(r[11]) if len(r) > 11 else ""
    registrar = str(r[12]) if len(r) > 12 else ""
    if registrar == user_name and this_month_str in reg and "2020-" not in reg:
        my_month_score += 5 # 신규 등록 5점

for r in req_all_values[1:]:
    req_date = str(r[0])
    req_user = str(r[1])
    req_stat = str(r[5])
    if req_user == user_name and this_month_str in req_date:
        my_month_score += 3 # 제보 3점
        if req_stat == "처리완료": my_month_score += 1 # 갱신(승인) 시 추가 1점

for i, r in enumerate(all_records_raw):
    row_idx = i + 2 
    status = r[13].strip() if len(r) > 13 else "정상"
    
    if user_email != ADMIN_EMAIL and status in ["비공개", "삭제", "잘못됨"]:
        continue
        
    r_padded = (r + [""]*14)[:14]
    if not r_padded[13]: r_padded[13] = "정상"
    r_padded.append(row_idx)
    
    key = (str(r_padded[0]).replace(" ",""), str(r_padded[1]).replace(" ",""), str(r_padded[2]), str(r_padded[4]))
    temp_dict[key] = r_padded 

all_records = list(temp_dict.values())
all_records.reverse()

# --- 💡 사이드바 (가이드라인 폰트 확대) ---
st.sidebar.markdown(f"### 👤 {user_name}")

# 내 토큰 표시
st.sidebar.markdown(f"**보유 토큰:** `{user_tokens} 개`")
# 💡 CSS로 글자 크기와 색상을 명확하게 지정하여 한 단계 더 키움
st.sidebar.markdown("<p style='font-size: 13px; color: #4a4a4a; margin-top: -10px;'>👉 신규 매물 등록 +3  |  오류 제보 승인 +1</p>", unsafe_allow_html=True)

st.sidebar.write("") # 여백

# 내 기여도 표시
st.sidebar.markdown(f"**이번 달 기여도:** `{my_month_score} 점`")
# 💡 CSS로 글자 크기와 색상을 명확하게 지정
st.sidebar.markdown("<p style='font-size: 13px; color: #4a4a4a; margin-top: -10px;'>🏆 신규등록 5점 | 오류제보 3점 | 정보갱신 1점</p>", unsafe_allow_html=True)

st.sidebar.write("---")

if user_email == ADMIN_EMAIL:
    if pending_req_count > 0:
        st.sidebar.error(f"🚨 대기 중인 수정 요청: {pending_req_count}건")
        st.sidebar.write("---")
        
    with st.sidebar.expander("👁️ 전체 직원 토큰 내역 (관리자용)"):
        if history_records:
            df_hist = pd.DataFrame(history_records, columns=["일시", "직원명", "변동", "잔여", "사유"])
            st.dataframe(df_hist[["일시", "직원명", "변동", "사유"]].tail(15).iloc[::-1], hide_index=True)
        else: st.write("내역이 없습니다.")
else:
    with st.sidebar.expander("📜 내 토큰 이용 내역"):
        my_history = [r for r in history_records if r[1] == user_name]
        if my_history:
            df_my_hist = pd.DataFrame(my_history, columns=["일시", "직원명", "변동", "잔여", "사유"])
            st.dataframe(df_my_hist[["일시", "변동", "사유"]].tail(10).iloc[::-1], hide_index=True)
        else: st.write("내역이 없습니다.")

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
    with st.form("search_addr_form"):
        c1, c2, c3 = st.columns([2, 2, 1])
        d = c1.text_input("동/건물명", key="t1_dong", placeholder="방이동")
        b = c2.text_input("번지", key="t1_bunji", placeholder="28-2")
        r_search = c3.text_input("호실", key="t1_room", placeholder="101")
        
        submitted = st.form_submit_button("주소 검색", type="primary", use_container_width=True)
        
    if submitted:
        res = [
            r for r in all_records 
            if (d.replace(" ","") in r[0].replace(" ","")) 
            and (b.replace(" ","") in r[0].replace(" ",""))
            and (r_search in r[1])
        ]
        res.sort(key=lambda x: extract_room_number(x[1]))
        st.session_state.addr_search_res = res
    
    if st.session_state.addr_search_res is not None:
        st.caption(f"검색 결과: {len(st.session_state.addr_search_res)}건")
        
        for idx, row in enumerate(st.session_state.addr_search_res):
            addr, room, name, birth, phone, deposit, rent, end_date, _, _, memo, reg_date, registrar, status, row_idx = row
            
            manager_name = next((m for b, m in MANAGER_BUILDINGS.items() if b in addr), None)
            is_manager_locked = manager_name and manager_name != user_name and user_email != ADMIN_EMAIL
            
            status_text = f" 🚨[{status}]" if status in ["비공개", "잘못됨", "삭제"] else ""
            old_tag = " | 🗄️ 기존 누적 DB" if "2020-" in str(reg_date) else ""
            m_tag = f" | 👑 {manager_name} 관리매물" if manager_name else ""
            hash_tags = extract_tags(memo)
            
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
                                st.success("제보 완료! 승인 시 토큰 1개 지급")
                                st.rerun()
            elif is_unlocked:
                if st.button("🔓 재열람가능", key=f"btn_re_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                
                if st.session_state.get(toggle_key, False):
                    st.info(f"**소유주:** {name}({birth}) | **연락처:** {phone}\n\n**보증/월세:** {deposit}/{rent} | **만기:** {end_date}\n\n**특이사항:** {memo}")
                    
                    if "2020-" in str(reg_date):
                        if st.button("✅ 현 소유주 일치 확인 (최신 DB로 갱신)", key=f"upd_2020_{idx}"):
                            ws_data.update_cell(row_idx, 12, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                            ws_data.update_cell(row_idx, 13, user_name)
                            st.cache_data.clear()
                            st.success("최신 데이터로 갱신 완료! 기여도 +1점 획득!")
                            st.rerun()
                            
                    with st.form(f"edit_addr_{idx}", clear_on_submit=True):
                        edit_memo = st.text_input("수정 요청 사유 (예: 번호오류)")
                        call_date = st.text_input("확인 통화일 (예: 3월 3일 오후 2시)")
                        
                        if st.form_submit_button("🛠️ 수정요청하기"):
                            if edit_memo and call_date:
                                full_reason = f"[{call_date} 통화] {edit_memo}"
                                ws_request.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, addr, room, full_reason, "대기중"])
                                st.cache_data.clear()
                                st.success("요청 전송 완료! 승인 시 토큰 1개 지급")
                                st.rerun()
                            else:
                                st.warning("사유와 통화일을 모두 입력해주세요.")
            else:
                if st.button("🔓 상세정보 열람 (토큰 1개)", key=f"btn_addr_{idx}"):
                    if user_tokens >= 1:
                        update_token(user_name, -1, f"매물 열람 ({addr} {room})")
                        st.session_state[unlock_key] = True
                        st.session_state[toggle_key] = True 
                        st.rerun()
                    else: st.error("토큰이 부족합니다.")
            st.write("---")

# --- [탭 2] 소유주 검색 ---
with tabs[1]:
    with st.form("search_owner_form"):
        c4, c5 = st.columns(2)
        sn = c4.text_input("성함", key="t2_name")
        sb = c5.text_input("생년월일(6자리)", key="t2_birth")
        submitted_own = st.form_submit_button("소유주 검색", type="primary", use_container_width=True)
        
    if submitted_own:
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
                    
                    if "2020-" in str(reg_date):
                        if st.button("✅ 현 소유주 일치 확인 (갱신)", key=f"upd_2020_own_{idx}"):
                            ws_data.update_cell(row_idx, 12, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                            ws_data.update_cell(row_idx, 13, user_name)
                            st.cache_data.clear()
                            st.success("갱신 완료! 기여도 +1점 획득!")
                            st.rerun()

                    with st.form(f"edit_own_{idx}", clear_on_submit=True):
                        edit_memo = st.text_input("사유")
                        call_date = st.text_input("확인 통화일")
                        
                        if st.form_submit_button("🛠️ 수정요청하기"):
                            if edit_memo and call_date:
                                full_reason = f"[{call_date} 통화] {edit_memo}"
                                ws_request.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, addr, room, full_reason, "대기중"])
                                st.cache_data.clear()
                                st.success("요청 완료!")
                                st.rerun()
                            else:
                                st.warning("사유와 통화일을 입력해주세요.")
            else:
                if st.button("🔓 상세정보 열람 (토큰 1개)", key=f"btn_own_{idx}"):
                    if user_tokens >= 1:
                        update_token(user_name, -1, f"매물 열람 ({addr} {room})")
                        st.session_state[unlock_key] = True
                        st.session_state[toggle_key] = True
                        st.rerun()
                    else: st.error("토큰 부족")
            st.write("---")

# --- [탭 3] 신규 등록 ---
with tabs[2]:
    st.subheader("📝 신규 등록 (완료 시 +3 토큰 / +5점)")
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
                
                duplicate = [r for r in all_records if r[0] == full_addr and r[1] == room_final and r[13] != "잘못됨"]
                if duplicate:
                    st.error(f"❌ 이미 등록된 매물입니다! (정보 변경 시 검색 후 [🛠️ 수정요청] 요망)")
                else:
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    new_row = [full_addr, room_final, f_name, f_birth, format_phone(f_phone), f_deposit, f_rent, f_end_date, "", "미분류", f_memo, now, user_name, "정상"]
                    ws_data.append_row(new_row)
                    
                    update_token(user_name, 3, f"신규 등록 ({full_addr} {room_final})")
                    st.cache_data.clear() 
                    st.success("✅ 신규 매물 등록 완료! 토큰 +3개 / 기여도 +5점 자동 지급!")
                    st.rerun()

# --- [탭 4] 관리자 전용 ---
if user_email == ADMIN_EMAIL:
    with tabs[3]:
        c_title, c_btn = st.columns([4, 1])
        c_title.subheader("👑 관리자 종합 대시보드")
        if c_btn.button("🔄 최신 데이터 불러오기"):
            st.cache_data.clear()
            st.rerun()
            
        now_date = datetime.now()
        this_month_str = now_date.strftime("%Y-%m")
        this_year_str = now_date.strftime("%Y")
        
        filter_period = st.radio("통계 기간 선택", ["이번 달", "올해 누적", "전체 누적"], horizontal=True)
        
        staff_stats = {r['이름']: {"신규등록": 0, "오류제보": 0, "살려낸DB": 0} for r in staff_records}
        new_db_cnt, up_db_cnt, del_db_cnt = 0, 0, 0
        
        for r in all_records_raw:
            reg = str(r[11]) if len(r) > 11 else ""
            stat = str(r[13]) if len(r) > 13 else "정상"
            registrar = str(r[12]) if len(r) > 12 else ""
            
            in_period = False
            if filter_period == "이번 달" and this_month_str in reg: in_period = True
            elif filter_period == "올해 누적" and this_year_str in reg: in_period = True
            elif filter_period == "전체 누적": in_period = True
            
            if in_period:
                if stat == "잘못됨": 
                    del_db_cnt += 1
                elif "2020-" not in reg:
                    new_db_cnt += 1
                    if registrar in staff_stats:
                        staff_stats[registrar]["신규등록"] += 1
                        
        for r in req_all_values[1:]:
            req_date = str(r[0])
            req_user = str(r[1])
            req_stat = str(r[5])
            
            in_period = False
            if filter_period == "이번 달" and this_month_str in req_date: in_period = True
            elif filter_period == "올해 누적" and this_year_str in req_date: in_period = True
            elif filter_period == "전체 누적": in_period = True
            
            if in_period and req_user in staff_stats:
                staff_stats[req_user]["오류제보"] += 1
                if req_stat in ["처리완료", "비공개"]: 
                    staff_stats[req_user]["살려낸DB"] += 1

        st.markdown("##### 📊 DB 자산 증식 현황")
        colA, colB, colC = st.columns(3)
        colA.metric(f"[{filter_period}] 확보/갱신된 DB", f"{new_db_cnt} 건")
        colB.metric(f"[{filter_period}] 걸러낸 썩은 DB", f"{del_db_cnt} 건", delta="블랙리스트", delta_color="inverse")
        st.write("---")
        
        st.markdown("##### 🏆 직원별 기여도 랭킹 (5:3:1 점수제)")
        df_stats = pd.DataFrame.from_dict(staff_stats, orient='index').reset_index()
        df_stats.columns = ["직원명", "신규 (5점)", "제보 (3점)", "갱신승인 (1점)"]
        df_stats["총 기여도 점수"] = (df_stats["신규 (5점)"] * 5) + (df_stats["제보 (3점)"] * 3) + (df_stats["갱신승인 (1점)"] * 1)
        df_stats = df_stats.sort_values(by="총 기여도 점수", ascending=False)
        st.dataframe(df_stats, use_container_width=True, hide_index=True)

        st.write("---")
        st.write("#### 🚨 직원 수정 요청 처리 (승인 시 해당 직원 토큰 +1 자동 지급)")
        if pending_reqs_with_idx:
            for row_idx, r_req in pending_reqs_with_idx:
                with st.container():
                    req_emp_name = r_req[1]
                    st.info(f"**[요청: {req_emp_name}]** 📍 {r_req[2]} {r_req[3]}  |  사유: {r_req[4]}")
                    cA, cB, cC = st.columns(3)
                    
                    if cA.button("✅ 수정 완료 (토큰+1 지급)", key=f"ok_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "처리완료")
                        for m_idx, m_row in enumerate(all_records_raw):
                            if m_row[0] == r_req[2] and m_row[1] == r_req[3]:
                                ws_data.update_cell(m_idx + 2, 12, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        update_token(req_emp_name, 1, f"수정요청 승인 포상 ({r_req[2]} {r_req[3]})")
                        st.cache_data.clear() 
                        st.rerun()
                        
                    if cB.button("🔒 비공개 처리 (토큰+1 지급)", key=f"hide_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "비공개")
                        for m_idx, m_row in enumerate(all_records_raw):
                            if m_row[0] == r_req[2] and m_row[1] == r_req[3]:
                                ws_data.update_cell(m_idx + 2, 14, "비공개")
                        update_token(req_emp_name, 1, f"비공개 제보 포상 ({r_req[2]} {r_req[3]})")
                        st.cache_data.clear()
                        st.rerun()
                        
                    if cC.button("🗑️ 영구 삭제 (잘못됨/반려)", key=f"del_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "삭제")
                        for m_idx, m_row in enumerate(all_records_raw):
                            if m_row[0] == r_req[2] and m_row[1] == r_req[3]:
                                ws_data.update_cell(m_idx + 2, 14, "잘못됨")
                        st.cache_data.clear()
                        st.rerun()
                st.write("---")
        else: st.info("대기 중인 요청이 없습니다.")
        
        st.write("---")
        st.write("#### 👥 직원 관리 및 포상")
        
        with st.expander("➕ 신규 직원 등록"):
            with st.form("add_staff_form", clear_on_submit=True):
                new_email = st.text_input("구글 이메일")
                new_n = st.text_input("이름")
                start_token = st.number_input("초기 토큰", value=10)
                submit_staff = st.form_submit_button("권한 부여")
                
                if submit_staff:
                    if "@" in new_email and new_n:
                        ws_staff.append_row([new_email, new_n, datetime.now().strftime('%Y-%m-%d'), start_token, ""])
                        st.cache_data.clear()
                        st.success(f"{new_n}님 등록 완료!")
                        st.rerun()
                        
        with st.expander("🎁 토큰 수동 지급"):
            with st.form("grant_token_form", clear_on_submit=True):
                target_staff = st.selectbox("직원", [row['이름'] for row in staff_records])
                grant_amount = st.number_input("수량", value=1)
                grant_reason = st.text_input("사유")
                submit_grant = st.form_submit_button("지급하기")
                
                if submit_grant:
                    if grant_reason:
                        update_token(target_staff, grant_amount, f"수동포상: {grant_reason}")
                        st.success("지급 완료!")
                        st.rerun() 

        if staff_records: st.dataframe(pd.DataFrame(staff_records), use_container_width=True)