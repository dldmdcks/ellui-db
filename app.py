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
        
        /* 컨테이너 상단 여백 복구 (탭 글씨 잘림 방지) */
        .block-container { padding-top: 3.5rem; padding-bottom: 2rem; }
        
        /* 사이드바 크기 조정 */
        [data-testid="stSidebar"] { width: 280px !important; }
        
        /* 탭 글자 크기 및 높이 확보 */
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
    # 대표님이 알려주신 새로운 시트의 gid를 정확히 타겟팅합니다.
    ss = gspread.authorize(creds).open_by_key('121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA')
    return ss

ss = get_ss()
ws_data = ss.get_worksheet_by_id(1969836502) # 새 시트 탭 연결

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

# 자동 토큰 지급 헬퍼 함수
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

# 기여도 계산을 위한 내 점수 파악 (사이드바 표시용)
my_month_score = 0
now_date = datetime.now()
this_month_str = now_date.strftime("%Y-%m")

for r in all_records_raw:
    # 새로운 양식: 등록일시=23, 등록자=24
    reg = str(r[23]) if len(r) > 23 else ""
    registrar = str(r[24]) if len(r) > 24 else ""
    if registrar == user_name and this_month_str in reg and "2020-" not in reg:
        my_month_score += 5 # 신규 등록 5점

for r in req_all_values[1:]:
    req_date = str(r[0])
    req_user = str(r[1])
    req_stat = str(r[5])
    if req_user == user_name and this_month_str in req_date:
        my_month_score += 3 # 제보 3점
        if req_stat in ["처리완료", "자동처리"]: my_month_score += 1 # 갱신(승인/자동처리) 시 추가 1점

for i, r in enumerate(all_records_raw):
    row_idx = i + 2 
    # 새로운 양식: 상태=25
    status = r[25].strip() if len(r) > 25 else "정상"
    
    if user_email != ADMIN_EMAIL and status in ["비공개", "삭제", "잘못됨"]:
        continue
        
    # 새로운 26개 열 구조에 맞게 빈칸 채우기
    r_padded = (r + [""]*26)[:26]
    if not r_padded[25]: r_padded[25] = "정상"
    r_padded.append(row_idx) # row_idx는 26번째(마지막)
    
    # 중복방지 키 (법정동, 본번, 부번, 동, 호실, 이름, 생년월일)
    key = (str(r_padded[2]).replace(" ",""), str(r_padded[3]), str(r_padded[4]), str(r_padded[7]), str(r_padded[8]), str(r_padded[9]), str(r_padded[10]))
    temp_dict[key] = r_padded 

all_records = list(temp_dict.values())
all_records.reverse()

# --- 사이드바 (가이드라인 줄바꿈 및 폰트 개선) ---
st.sidebar.markdown(f"### 👤 {user_name}")

# 내 토큰 표시
st.sidebar.markdown(f"**보유 토큰:** `{user_tokens} 개`")
# CSS로 줄바꿈 및 글자 크기, 마진 조절
st.sidebar.markdown("""
<div style='font-size: 13px; color: #4a4a4a; margin-top: -5px;'>
    👉 신규 매물 등록 <b>+3</b><br>
    👉 오류 제보 승인 <b>+1</b>
</div>
""", unsafe_allow_html=True)

st.sidebar.write("") # 여백

# 내 기여도 표시
st.sidebar.markdown(f"**이번 달 기여도:** `{my_month_score} 점`")
# CSS로 줄바꿈 및 글자 크기 조절
st.sidebar.markdown("""
<div style='font-size: 13px; color: #4a4a4a; margin-top: -5px;'>
    🏆 신규등록 <b>5점</b><br>
    🏆 오류제보 <b>3점</b><br>
    🏆 정보갱신 <b>1점</b>
</div>
""", unsafe_allow_html=True)

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
        res = []
        for r in all_records:
            # 검색을 위한 대상 문자열 조합 (법정동+건물명, 번지-부번, 동+호실)
            d_target = str(r[2]).replace(" ","") + str(r[6]).replace(" ","") 
            b_target = f"{r[3]}-{r[4]}" if str(r[4]) != "0" else str(r[3])
            room_target = str(r[7]).replace(" ","") + str(r[8]).replace(" ","")
            
            if (d.replace(" ","") in d_target) and (b.replace(" ","") in b_target) and (r_search.replace(" ","") in room_target):
                res.append(r)
                
        res.sort(key=lambda x: extract_room_number(x[8])) # 호실 기준으로 정렬
        st.session_state.addr_search_res = res
    
    if st.session_state.addr_search_res is not None:
        st.caption(f"검색 결과: {len(st.session_state.addr_search_res)}건")
        
        for idx, row in enumerate(st.session_state.addr_search_res):
            # 26열 데이터 완벽 해체
            city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, reg_date, registrar, status, row_idx = row
            
            # 주소 합치기 (화면 표시 및 제보 확인용)
            addr_str = f"{city} {gu} {dong} {bon}" + (f"-{bu}" if bu and bu != "0" else "")
            if bldg: addr_str += f" {bldg}"
            room_str = f"{d_dong} {room}" if d_dong and d_dong != "동없음" else f"{room}"
            
            manager_name = next((m for b, m in MANAGER_BUILDINGS.items() if f" {b} " in f" {addr_str} "), None)
            is_manager_locked = manager_name and manager_name != user_name and user_email != ADMIN_EMAIL
            
            status_text = f" 🚨[{status}]" if status in ["비공개", "잘못됨", "삭제"] else ""
            old_tag = " | 🗄️ 기존 누적 DB" if "2020-" in str(reg_date) else ""
            m_tag = f" | 👑 {manager_name} 관리매물" if manager_name else ""
            hash_tags = extract_tags(memo)
            
            st.markdown(f"**📍 {addr_str} | {room_str}{old_tag}{status_text}{m_tag}**")
            if hash_tags: st.caption(f"✨ {hash_tags}")
            
            if is_manager_locked:
                st.error(f"🔒 {manager_name} 전담 매물입니다. (열람 불가)")
                st.write("---")
                continue
                
            is_pending = (addr_str, room_str) in pending_set
            if is_pending and user_email != ADMIN_EMAIL:
                st.warning("⏳ 정보 확인/수정요청 중인 매물입니다. (열람 일시중지)")
                st.write("---")
                continue

            unlock_key = f"unlock_addr_{addr_str}_{room_str}"
            toggle_key = f"toggle_addr_{idx}"
            is_no_phone = ("연락처 없음" in str(phone))
            free_unlock = is_unlocked_recently(addr_str, room_str)
            
            is_unlocked = free_unlock or st.session_state.get(unlock_key, False)
            
            if is_no_phone:
                if st.button("📞 연락처 없음 / 추가하기", key=f"btn_no_ph_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                
                if st.session_state.get(toggle_key, False):
                    with st.form(f"report_{idx}", clear_on_submit=True):
                        new_phone = st.text_input("알아낸 진짜 연락처 입력")
                        if st.form_submit_button("🏆 제보하고 자동 반영 (토큰+1)"):
                            if new_phone:
                                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                # 26번 칸이 상태
                                ws_data.update_cell(row_idx, 26, "비공개")
                                new_row = [city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, format_phone(new_phone), b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, now_str, user_name, "정상"]
                                ws_data.append_row(new_row)
                                ws_request.append_row([now_str, user_name, addr_str, room_str, f"[연락처 갱신] {new_phone}", "자동처리"])
                                update_token(user_name, 1, f"연락처 자동 반영 ({addr_str} {room_str})")
                                
                                st.cache_data.clear()
                                st.success("✅ 연락처가 최신화되고 토큰이 지급되었습니다!")
                                st.rerun()
            elif is_unlocked:
                if st.button("🔓 재열람가능", key=f"btn_re_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                
                if st.session_state.get(toggle_key, False):
                    st.info(f"**용도:** {b_type}\n\n**소유주:** {name}({birth}) | **연락처:** {phone}\n\n**보증/월세:** {deposit}/{rent} | **만기:** {end_date}\n\n**특이사항:** {memo}")
                    
                    if "2020-" in str(reg_date):
                        if st.button("✅ 현 소유주 일치 확인 (최신 DB로 갱신)", key=f"upd_2020_{idx}"):
                            # 24: 등록일시, 25: 등록자
                            ws_data.update_cell(row_idx, 24, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                            ws_data.update_cell(row_idx, 25, user_name)
                            ws_history.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, 0, user_tokens, "과거 DB 갱신"])
                            st.cache_data.clear()
                            st.success("최신 데이터로 갱신 완료! 기여도 +1점 획득!")
                            st.rerun()
                            
                    with st.form(f"edit_addr_{idx}", clear_on_submit=True):
                        edit_memo = st.text_input("수정 요청 내용 (예: 보증금 2천으로 변경됨)")
                        call_date = st.text_input("확인 통화일 (예: 3월 3일 오후 2시)")
                        
                        if st.form_submit_button("🛠️ 데이터 수정 자동 반영"):
                            if edit_memo and call_date:
                                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                full_reason = f"[{call_date} 통화] {edit_memo}"
                                
                                ws_data.update_cell(row_idx, 26, "비공개")
                                new_memo = f"{memo}\n👉 변경사항: {full_reason}".strip()
                                new_row = [city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, new_memo, now_str, user_name, "정상"]
                                ws_data.append_row(new_row)
                                
                                ws_request.append_row([now_str, user_name, addr_str, room_str, full_reason, "자동처리"])
                                update_token(user_name, 1, f"정보 자동 수정 ({addr_str} {room_str})")
                                
                                st.cache_data.clear()
                                st.success("✅ 데이터가 갱신되고 기존 내역은 비공개로 보존됩니다! (토큰 +1)")
                                st.rerun()
                            else:
                                st.warning("수정 내용과 통화일을 모두 입력해주세요.")
            else:
                if st.button("🔓 상세정보 열람 (토큰 1개)", key=f"btn_addr_{idx}"):
                    if user_tokens >= 1:
                        update_token(user_name, -1, f"매물 열람 ({addr_str} {room_str})")
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
        # 9: 이름, 10: 생년월일
        res = [r for r in all_records if (sn in str(r[9])) and (not sb or sb == str(r[10]))]
        res.sort(key=lambda x: extract_room_number(x[8])) # 8: 호실
        st.session_state.owner_search_res = res
        
    if st.session_state.owner_search_res is not None:
        st.caption(f"검색 결과: {len(st.session_state.owner_search_res)}건")
        for idx, row in enumerate(st.session_state.owner_search_res):
            city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, reg_date, registrar, status, row_idx = row
            
            addr_str = f"{city} {gu} {dong} {bon}" + (f"-{bu}" if bu and bu != "0" else "")
            if bldg: addr_str += f" {bldg}"
            room_str = f"{d_dong} {room}" if d_dong and d_dong != "동없음" else f"{room}"
            
            manager_name = next((m for b, m in MANAGER_BUILDINGS.items() if f" {b} " in f" {addr_str} "), None)
            is_manager_locked = manager_name and manager_name != user_name and user_email != ADMIN_EMAIL
            status_text = f" 🚨[{status}]" if status in ["비공개", "잘못됨", "삭제"] else ""
            m_tag = f" | 👑 {manager_name} 관리매물" if manager_name else ""
            
            st.markdown(f"**👤 {name}({birth}) | 📍 {addr_str} {room_str}{status_text}{m_tag}**")
            
            if is_manager_locked:
                st.error(f"🔒 {manager_name} 전담 매물입니다.")
                st.write("---")
                continue
                
            is_pending = (addr_str, room_str) in pending_set
            if is_pending and user_email != ADMIN_EMAIL:
                st.warning("⏳ 수정요청 중 (열람 일시중지)")
                st.write("---")
                continue

            unlock_key = f"unlock_own_{addr_str}_{room_str}"
            toggle_key = f"toggle_own_{idx}"
            is_no_phone = ("연락처 없음" in str(phone))
            free_unlock = is_unlocked_recently(addr_str, room_str)
            is_unlocked = free_unlock or st.session_state.get(unlock_key, False)
            
            if is_no_phone:
                if st.button("📞 연락처 없음 / 추가하기", key=f"btn_own_no_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                if st.session_state.get(toggle_key, False):
                    with st.form(f"report_own_{idx}", clear_on_submit=True):
                        new_phone = st.text_input("진짜 연락처 입력")
                        if st.form_submit_button("🏆 제보하고 자동 반영 (토큰+1)"):
                            if new_phone:
                                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                ws_data.update_cell(row_idx, 26, "비공개")
                                new_row = [city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, format_phone(new_phone), b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, now_str, user_name, "정상"]
                                ws_data.append_row(new_row)
                                ws_request.append_row([now_str, user_name, addr_str, room_str, f"[연락처 갱신] {new_phone}", "자동처리"])
                                update_token(user_name, 1, f"연락처 자동 반영 ({addr_str} {room_str})")
                                st.cache_data.clear()
                                st.success("✅ 연락처 최신화 완료!")
                                st.rerun()
            elif is_unlocked:
                if st.button("🔓 재열람가능", key=f"btn_re_own_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                if st.session_state.get(toggle_key, False):
                    st.info(f"**용도:** {b_type}\n\n**연락처:** {phone} | **만기/보증/월세:** {end_date} / {deposit} / {rent}\n\n**특이사항:** {memo}")
                    
                    if "2020-" in str(reg_date):
                        if st.button("✅ 현 소유주 일치 확인 (갱신)", key=f"upd_2020_own_{idx}"):
                            ws_data.update_cell(row_idx, 24, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                            ws_data.update_cell(row_idx, 25, user_name)
                            ws_history.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, 0, user_tokens, "과거 DB 갱신"])
                            st.cache_data.clear()
                            st.success("갱신 완료! 기여도 +1점 획득!")
                            st.rerun()

                    with st.form(f"edit_own_{idx}", clear_on_submit=True):
                        edit_memo = st.text_input("수정 요청 내용 (예: 보증금 2천으로 변경됨)")
                        call_date = st.text_input("확인 통화일 (예: 3월 3일 오후 2시)")
                        
                        if st.form_submit_button("🛠️ 데이터 수정 자동 반영"):
                            if edit_memo and call_date:
                                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                full_reason = f"[{call_date} 통화] {edit_memo}"
                                
                                ws_data.update_cell(row_idx, 26, "비공개")
                                new_memo = f"{memo}\n👉 변경사항: {full_reason}".strip()
                                new_row = [city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, new_memo, now_str, user_name, "정상"]
                                ws_data.append_row(new_row)
                                
                                ws_request.append_row([now_str, user_name, addr_str, room_str, full_reason, "자동처리"])
                                update_token(user_name, 1, f"정보 자동 수정 ({addr_str} {room_str})")
                                
                                st.cache_data.clear()
                                st.success("✅ 데이터가 갱신되고 기존 내역은 비공개로 보존됩니다! (토큰 +1)")
                                st.rerun()
                            else:
                                st.warning("수정 내용과 통화일을 입력해주세요.")
            else:
                if st.button("🔓 상세정보 열람 (토큰 1개)", key=f"btn_own_{idx}"):
                    if user_tokens >= 1:
                        update_token(user_name, -1, f"매물 열람 ({addr_str} {room_str})")
                        st.session_state[unlock_key] = True
                        st.session_state[toggle_key] = True
                        st.rerun()
                    else: st.error("토큰 부족")
            st.write("---")

# --- [탭 3] 신규 등록 ---
with tabs[2]:
    st.subheader("📝 신규 등록 (완료 시 +3 토큰 / +5점)")
    
    if "reg_city" not in st.session_state: st.session_state.reg_city = "서울특별시"
    if "reg_dong" not in st.session_state: st.session_state.reg_dong = ""
    if "reg_bunji" not in st.session_state: st.session_state.reg_bunji = ""
    if "reg_sub_dong" not in st.session_state: st.session_state.reg_sub_dong = "0"
    if "reg_deposit" not in st.session_state: st.session_state.reg_deposit = ""
    if "reg_rent" not in st.session_state: st.session_state.reg_rent = ""
    if "reg_gu" not in st.session_state: st.session_state.reg_gu = "송파구"
    if "reg_room" not in st.session_state: st.session_state.reg_room = ""
    if "reg_name" not in st.session_state: st.session_state.reg_name = ""
    if "reg_birth" not in st.session_state: st.session_state.reg_birth = ""
    if "reg_phone" not in st.session_state: st.session_state.reg_phone = ""
    if "reg_end_date" not in st.session_state: st.session_state.reg_end_date = ""
    if "reg_memo" not in st.session_state: st.session_state.reg_memo = ""

    with st.form("reg_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.reg_city = st.text_input("시/도", st.session_state.reg_city)
            st.session_state.reg_dong = st.text_input("읍/면/동 (필수)", value=st.session_state.reg_dong, placeholder="방이동")
            st.session_state.reg_bunji = st.text_input("번지 (필수)", value=st.session_state.reg_bunji, placeholder="28-2")
            st.session_state.reg_sub_dong = st.text_input("번지 뒤 '동' (없으면 0)", value=st.session_state.reg_sub_dong)
            st.session_state.reg_deposit = st.text_input("보증금 (만원)", value=st.session_state.reg_deposit)
            st.session_state.reg_rent = st.text_input("월세 (만원)", value=st.session_state.reg_rent)
        with col2:
            st.session_state.reg_gu = st.text_input("구/군", st.session_state.reg_gu)
            st.session_state.reg_room = st.text_input("호실 (필수, 숫자만)", value=st.session_state.reg_room, placeholder="101")
            st.session_state.reg_name = st.text_input("임대인 성함 (필수)", value=st.session_state.reg_name)
            st.session_state.reg_birth = st.text_input("생년월일 (필수, 숫자만)", value=st.session_state.reg_birth, placeholder="940101")
            st.session_state.reg_phone = st.text_input("연락처 (필수, 숫자만)", value=st.session_state.reg_phone, placeholder="01012345678")
            st.session_state.reg_end_date = st.text_input("현 만기일", value=st.session_state.reg_end_date, placeholder="2026-05-30")
        st.session_state.reg_memo = st.text_area("특이사항", value=st.session_state.reg_memo)
        
        submit_btn = st.form_submit_button("💾 데이터 등록", type="primary", use_container_width=True)

    if submit_btn:
        f_dong = st.session_state.reg_dong
        f_bunji = st.session_state.reg_bunji
        f_room = st.session_state.reg_room
        f_name = st.session_state.reg_name
        f_birth = st.session_state.reg_birth
        f_phone = st.session_state.reg_phone

        has_error = False
        
        if not f_dong or not f_bunji or not f_name or not f_room or not f_birth or not f_phone:
            st.error("🚨 필수 항목(읍/면/동, 번지, 호실, 성함, 생년월일, 연락처)을 모두 입력해주세요.")
            has_error = True
            
        if f_room and not f_room.isdigit():
            st.error("🚨 '호실'은 숫자만 입력해야 합니다. (예: 101호 -> 101)")
            has_error = True
            
        if f_birth and not f_birth.isdigit():
            st.error("🚨 '생년월일'은 숫자만 입력해야 합니다. (예: 940101)")
            has_error = True
            
        if f_phone and not f_phone.isdigit():
            st.error("🚨 '연락처'는 숫자만 입력해야 합니다. (예: 01012345678)")
            has_error = True

        if not has_error:
            # 본번/부번 쪼개기
            if "-" in f_bunji:
                bon, bu = f_bunji.split("-", 1)
            else:
                bon, bu = f_bunji, "0"
            
            # 동/호수 세팅
            d_dong = "동없음" if st.session_state.reg_sub_dong == "0" else (f"{st.session_state.reg_sub_dong}동" if not st.session_state.reg_sub_dong.endswith("동") else st.session_state.reg_sub_dong)
            r_ho = f"{f_room}호" if not f_room.endswith("호") else f_room
            
            # 중복 체크용
            dup_addr = f"{st.session_state.reg_city} {st.session_state.reg_gu} {f_dong} {bon}" + (f"-{bu}" if bu != "0" else "")
            dup_room = f"{d_dong} {r_ho}" if d_dong != "동없음" else r_ho
            
            duplicate = []
            for r in all_records:
                city, gu, dong, r_bon, r_bu, road, bldg, r_ddong, r_room, r_name, r_birth, r_phone, r_btype, r_appr, r_viol, r_land, r_rooma, r_biz, r_dep, r_rent, r_fee, r_end, r_memo, r_reg, r_registrar, r_status, r_idx = r
                c_addr = f"{city} {gu} {dong} {r_bon}" + (f"-{r_bu}" if r_bu and r_bu != "0" else "")
                c_room = f"{r_ddong} {r_room}" if r_ddong and r_ddong != "동없음" else r_room
                if c_addr == dup_addr and c_room == dup_room and r_status != "잘못됨":
                    duplicate.append(r)
            
            if duplicate:
                st.error(f"❌ 이미 등록된 매물입니다! (정보 변경 시 검색 후 [🛠️ 수정요청] 요망)")
            else:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # 26개 열 구조
                new_row = [
                    st.session_state.reg_city, st.session_state.reg_gu, f_dong, bon, bu, 
                    "", "", d_dong, r_ho, f_name, f_birth, format_phone(f_phone), 
                    "미분류", "", "정상", "", "", "", 
                    st.session_state.reg_deposit, st.session_state.reg_rent, "", 
                    st.session_state.reg_end_date, st.session_state.reg_memo, now, user_name, "정상"
                ]
                ws_data.append_row(new_row)
                
                update_token(user_name, 3, f"신규 등록 ({dup_addr} {dup_room})")
                
                for key in ["reg_dong", "reg_bunji", "reg_room", "reg_name", "reg_birth", "reg_phone", "reg_deposit", "reg_rent", "reg_end_date", "reg_memo"]:
                    st.session_state[key] = ""
                st.session_state.reg_sub_dong = "0"
                
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
        
        cnt_new, cnt_renew, cnt_req_ok, cnt_req_hide = 0, 0, 0, 0
        
        for r in history_records:
            if len(r) > 4:
                h_date, h_name, h_reason = str(r[0]), str(r[1]), str(r[4])
                in_period = False
                if filter_period == "이번 달" and this_month_str in h_date: in_period = True
                elif filter_period == "올해 누적" and this_year_str in h_date: in_period = True
                elif filter_period == "전체 누적": in_period = True
                
                if in_period:
                    if "신규 등록" in h_reason:
                        cnt_new += 1
                        if h_name in staff_stats: staff_stats[h_name]["신규등록"] += 1
                    elif "과거 DB 갱신" in h_reason:
                        cnt_renew += 1
                        
        for r in req_all_values[1:]:
            req_date, req_user, req_stat = str(r[0]), str(r[1]), str(r[5])
            
            in_period = False
            if filter_period == "이번 달" and this_month_str in req_date: in_period = True
            elif filter_period == "올해 누적" and this_year_str in req_date: in_period = True
            elif filter_period == "전체 누적": in_period = True
            
            if in_period:
                if req_stat in ["처리완료", "자동처리"]:
                    cnt_req_ok += 1
                    if req_user in staff_stats: 
                        staff_stats[req_user]["오류제보"] += 1
                        staff_stats[req_user]["살려낸DB"] += 1
                elif req_stat == "비공개":
                    cnt_req_hide += 1
                    if req_user in staff_stats: 
                        staff_stats[req_user]["오류제보"] += 1
                        staff_stats[req_user]["살려낸DB"] += 1

        st.markdown("##### 📊 엘루이 DB 자산 통계 (중복 제거됨)")
        colA, colB, colC, colD = st.columns(4)
        colA.metric(f"[{filter_period}] 🆕 신규 등록", f"{cnt_new} 건")
        colB.metric(f"[{filter_period}] 🔄 단순 갱신", f"{cnt_renew} 건")
        colC.metric(f"[{filter_period}] 🛠️ 수정 승인/자동반영", f"{cnt_req_ok} 건")
        colD.metric(f"[{filter_period}] 🔒 비공개 처리", f"{cnt_req_hide} 건")
        st.write("---")
        
        st.markdown("##### 🏆 직원별 기여도 랭킹 (5:3:1 점수제)")
        df_stats = pd.DataFrame.from_dict(staff_stats, orient='index').reset_index()
        df_stats.columns = ["직원명", "신규 (5점)", "제보 (3점)", "갱신승인 (1점)"]
        df_stats["총 기여도 점수"] = (df_stats["신규 (5점)"] * 5) + (df_stats["제보 (3점)"] * 3) + (df_stats["갱신승인 (1점)"] * 1)
        df_stats = df_stats.sort_values(by="총 기여도 점수", ascending=False)
        st.dataframe(df_stats, use_container_width=True, hide_index=True)

        st.write("---")
        st.write("#### 🚨 직원 수정 요청 처리 (수동 승인 대기건)")
        if pending_reqs_with_idx:
            for row_idx, r_req in pending_reqs_with_idx:
                with st.container():
                    req_emp_name = r_req[1]
                    st.info(f"**[요청: {req_emp_name}]** 📍 {r_req[2]} {r_req[3]}  |  사유: {r_req[4]}")
                    cA, cB, cC = st.columns(3)
                    
                    if cA.button("✅ 수정 완료 (토큰+1 지급)", key=f"ok_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "처리완료")
                        # 매물 찾아 갱신
                        for m_idx, m_row in enumerate(all_records_raw):
                            # 기존 구조의 주소 조합 재구성 비교
                            m_addr = f"{m_row[0]} {m_row[1]} {m_row[2]} {m_row[3]}" + (f"-{m_row[4]}" if m_row[4] and m_row[4] != "0" else "")
                            if m_row[5]: m_addr += f" {m_row[5]}"
                            m_room = f"{m_row[7]} {m_row[8]}" if m_row[7] and m_row[7] != "동없음" else m_row[8]
                            if m_addr == r_req[2] and m_room == r_req[3]:
                                ws_data.update_cell(m_idx + 2, 24, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        update_token(req_emp_name, 1, f"수정요청 승인 포상 ({r_req[2]} {r_req[3]})")
                        st.cache_data.clear() 
                        st.rerun()
                        
                    if cB.button("🔒 비공개 처리 (토큰+1 지급)", key=f"hide_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "비공개")
                        for m_idx, m_row in enumerate(all_records_raw):
                            m_addr = f"{m_row[0]} {m_row[1]} {m_row[2]} {m_row[3]}" + (f"-{m_row[4]}" if m_row[4] and m_row[4] != "0" else "")
                            if m_row[5]: m_addr += f" {m_row[5]}"
                            m_room = f"{m_row[7]} {m_row[8]}" if m_row[7] and m_row[7] != "동없음" else m_row[8]
                            if m_addr == r_req[2] and m_room == r_req[3]:
                                ws_data.update_cell(m_idx + 2, 26, "비공개")
                        update_token(req_emp_name, 1, f"비공개 제보 포상 ({r_req[2]} {r_req[3]})")
                        st.cache_data.clear()
                        st.rerun()
                        
                    if cC.button("🗑️ 영구 삭제 (잘못됨/반려)", key=f"del_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "삭제")
                        for m_idx, m_row in enumerate(all_records_raw):
                            m_addr = f"{m_row[0]} {m_row[1]} {m_row[2]} {m_row[3]}" + (f"-{m_row[4]}" if m_row[4] and m_row[4] != "0" else "")
                            if m_row[5]: m_addr += f" {m_row[5]}"
                            m_room = f"{m_row[7]} {m_row[8]}" if m_row[7] and m_row[7] != "동없음" else m_row[8]
                            if m_addr == r_req[2] and m_room == r_req[3]:
                                ws_data.update_cell(m_idx + 2, 26, "잘못됨")
                        st.cache_data.clear()
                        st.rerun()
                st.write("---")
        else: st.info("대기 중인 수동 승인 요청이 없습니다.")
        
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