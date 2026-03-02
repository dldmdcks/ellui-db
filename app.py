import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime
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

# --- 💡 새로고침(F5) 로그아웃 방지 로직 ---
if 'connected' not in st.session_state: 
    st.session_state.connected = False

query_params = st.query_params
# 주소창에 토큰이 남아있으면 자동 로그인 처리
if "session_token" in query_params and not st.session_state.connected:
    access_token = query_params["session_token"]
    user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", 
                             headers={"Authorization": f"Bearer {access_token}"}).json()
    if "email" in user_info:
        st.session_state.connected = True
        st.session_state.user_info = user_info

# 최초 구글 로그인 처리
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
        # 주소창에 토큰을 심어서 새로고침 시 유지되도록 함
        st.query_params["session_token"] = access_token
        st.rerun()

if not st.session_state.connected:
    st.warning("🔒 엘루이 매물관리 시스템입니다. 본인인증 후 이용해주세요.")
    login_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=openid%20email%20profile&access_type=offline&prompt=select_account"
    st.link_button("🔵 Google 계정으로 로그인", login_url, type="primary", use_container_width=True)
    st.stop()

# 3. 데이터베이스 연동 및 시트 생성
@st.cache_resource
def get_ss():
    creds = Credentials.from_authorized_user_info(token_dict)
    return gspread.authorize(creds).open_by_key('121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA')

ss = get_ss()
ws_data = ss.sheet1

# 직원명단 / 수정요청 / 토큰내역 시트 자동 생성
try: ws_staff = ss.worksheet("직원명단")
except: 
    ws_staff = ss.add_worksheet(title="직원명단", rows="100", cols="5")
    ws_staff.append_row(["이메일", "이름", "등록일", "보유토큰"])

try: ws_request = ss.worksheet("수정요청")
except: 
    ws_request = ss.add_worksheet(title="수정요청", rows="100", cols="6")
    ws_request.append_row(["요청일시", "요청직원", "대상주소", "대상호실", "요청내용", "처리상태"])

try: ws_history = ss.worksheet("토큰내역")
except:
    ws_history = ss.add_worksheet(title="토큰내역", rows="100", cols="5")
    ws_history.append_row(["일시", "직원명", "변동량", "잔여토큰", "사유_상세"])

# 권한 체크 및 사용자 매핑
staff_records = ws_staff.get_all_records()
staff_dict = {str(row['이메일']).strip(): row for row in staff_records}
ALLOWED_USERS = [ADMIN_EMAIL] + list(staff_dict.keys())

user_email = st.session_state.user_info.get("email", "")
if user_email not in ALLOWED_USERS:
    st.error(f"⚠️ 승인되지 않은 계정입니다 ({user_email}). 대표님께 권한을 요청하세요.")
    st.stop()

# 💡 실시간 토큰 동기화 완벽 수정 (세션 기억 삭제, 무조건 원본 읽기)
if user_email == ADMIN_EMAIL:
    user_name, user_tokens, staff_row_index = "이응찬 대표", 9999, None
else:
    user_name = staff_dict[user_email]['이름']
    user_tokens = int(staff_dict[user_email].get('보유토큰', 0))
    staff_row_index = list(staff_dict.keys()).index(user_email) + 2 

history_records = ws_history.get_all_values()[1:]

# --- 헬퍼 함수 ---
def clean_numeric(text): return re.sub(r'[^0-9]', '', text)
def clean_bunji(text): return re.sub(r'[^0-9-]', '', text)
def format_phone(text):
    nums = clean_numeric(text)
    if len(nums) == 11: return f"{nums[:3]}-{nums[3:7]}-{nums[7:]}"
    elif len(nums) == 10: return f"{nums[:3]}-{nums[3:6]}-{nums[6:]}"
    return nums

# 토큰 업데이트 및 내역 기록 함수 (세션 동기화 로직 제거 완료)
def update_token(amount, reason):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_token_val = user_tokens + amount
    if staff_row_index:
        ws_staff.update_cell(staff_row_index, 4, new_token_val)
    ws_history.append_row([now, user_name, amount, new_token_val, reason])
    st.cache_resource.clear()

# 24시간 이내 열람 여부 확인 로직
def is_unlocked_recently(addr, room):
    if user_email == ADMIN_EMAIL: return True
    now = datetime.now()
    search_str = f"({addr} {room})"
    for r in reversed(history_records):
        if len(r) > 4 and r[1] == user_name and search_str in r[4] and str(r[2]) == "-1":
            try:
                record_time = datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S')
                if (now - record_time).total_seconds() <= 86400: # 24시간 = 86400초
                    return True
            except: continue
    return False

# 대기중인 요청 데이터 확보 (인덱스 포함)
req_all_values = ws_request.get_all_values()
pending_reqs_with_idx = [(i+1, r) for i, r in enumerate(req_all_values) if i > 0 and len(r) > 5 and r[5] == '대기중']
pending_req_count = len(pending_reqs_with_idx)

# 메인 DB 가져오기 및 비공개 필터링 (V5 핵심)
all_records_raw = ws_data.get_all_values()[1:]
all_records = []
for r in all_records_raw:
    if len(r) > 12:
        status = r[13].strip() if len(r) > 13 else "정상"
        # 직원은 '비공개' 매물 아예 못 보게 숨김
        if user_email != ADMIN_EMAIL and status == "비공개":
            continue
        r_padded = (r + [""]*14)[:14]
        if not r_padded[13]: r_padded[13] = "정상"
        all_records.append(r_padded)
        
all_records.reverse() # 최신순 정렬

# --- 사이드바 ---
st.sidebar.markdown(f"### 👤 접속자: {user_name}")
st.sidebar.metric(label="내 보유 열람권(토큰)", value=f"{user_tokens} 개")

with st.sidebar.expander("📜 내 토큰 이용 내역 보기"):
    my_history = [r for r in history_records if r[1] == user_name]
    if my_history:
        df_my_hist = pd.DataFrame(my_history, columns=["일시", "직원명", "변동", "잔여", "사유"])
        st.dataframe(df_my_hist[["일시", "변동", "사유"]].tail(10).iloc[::-1], hide_index=True)
    else:
        st.write("내역이 없습니다.")

# 포상 안내 문구 추가
st.sidebar.caption("🎁 우수 DB 정화 직원에겐 대표님의 특별 토큰이 수시로 지급됩니다.")
st.sidebar.write("---")

if user_email == ADMIN_EMAIL and pending_req_count > 0:
    st.sidebar.error(f"🚨 대기중인 수정 요청: {pending_req_count}건")
    st.sidebar.write("---")

if st.sidebar.button("로그아웃"):
    st.query_params.clear()
    st.session_state.clear()
    st.rerun()

# --- 검색 결과 세션 유지 (화면 튕김 방지) ---
if "addr_search_res" not in st.session_state: st.session_state.addr_search_res = None
if "owner_search_res" not in st.session_state: st.session_state.owner_search_res = None

tabs_list = ["🔍 주소 검색", "👤 소유주 검색", "📝 신규 등록"]
if user_email == ADMIN_EMAIL: tabs_list.append("👑 관리자 전용")
tabs = st.tabs(tabs_list)

# --- [탭 1] 주소 검색 ---
with tabs[0]:
    st.subheader("지번으로 주소 찾기 (상세조회 시 토큰 1개 차감)")
    c1, c2 = st.columns(2); d = c1.text_input("동 (예: 방이동)", key="t1_dong"); b = c2.text_input("번지 (예: 28-2)", key="t1_bunji")
    
    if st.button("주소 검색", use_container_width=True, type="primary"):
        st.session_state.addr_search_res = [r for r in all_records if len(r) > 12 and (d.replace(" ","") in r[0].replace(" ","")) and (b.replace(" ","") in r[0].replace(" ",""))]
    
    if st.session_state.addr_search_res is not None:
        st.success(f"검색 결과: 최신순 {len(st.session_state.addr_search_res)}건")
        for idx, row in enumerate(st.session_state.addr_search_res):
            addr, room, name, birth, phone, deposit, rent, end_date, _, _, memo, reg_date, registrar, status = (row + [""]*14)[:14]
            
            with st.container():
                # 대표님 화면에만 비공개 딱지 보임
                status_tag = " 🚨[비공개 매물]" if status == "비공개" else ""
                st.markdown(f"#### 📍 {addr} | {room}{status_tag} | 📅 {reg_date[:10]}")
                unlock_key = f"unlock_addr_{addr}_{room}"
                
                free_unlock = is_unlocked_recently(addr, room)
                is_open = free_unlock or st.session_state.get(unlock_key, False)
                
                if is_open:
                    if free_unlock and not st.session_state.get(unlock_key, False) and user_email != ADMIN_EMAIL:
                        st.caption("⏳ 최근 24시간 내 열람 기록이 확인되어 토큰 차감 없이 무료로 개방되었습니다.")
                    st.info(f"**소유주:** {name} ({birth})\n\n**연락처:** {phone}\n\n**보증금/월세:** {deposit}/{rent}\n\n**만기일:** {end_date}\n\n**특이사항:** {memo}")
                    with st.form(f"edit_addr_{idx}", clear_on_submit=True):
                        edit_memo = st.text_input("수정 요청 사유 (예: 연락처 변경)", key=f"req_{idx}")
                        # 꿀팁 안내 문구 추가
                        st.caption("💡 꿀팁: 변경된 진짜 연락처 등 정확한 정보를 함께 남겨주시면, 대표님이 확인 후 [포상 토큰 +1개]를 즉시 지급해 드립니다!")
                        if st.form_submit_button("🛠 대표님께 수정 요청하기"):
                            if edit_memo:
                                ws_request.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, addr, room, edit_memo, "대기중"])
                                st.success("요청이 전송되었습니다!")
                else:
                    if st.button(f"🔓 상세 정보 열람 (토큰 1개 차감)", key=f"btn_addr_{idx}"):
                        if user_tokens >= 1:
                            update_token(-1, f"매물 열람 ({addr} {room})")
                            st.session_state[unlock_key] = True
                            st.rerun()
                        else:
                            st.error("보유한 열람권(토큰)이 부족합니다.")
                st.write("---")

# --- [탭 2] 소유주 검색 ---
with tabs[1]:
    st.subheader("소유주 매물 검색 (상세조회 시 토큰 1개 차감)")
    c3, c4 = st.columns(2); sn = c3.text_input("소유주 성함", key="t2_name"); sb = c4.text_input("생년월일(6자리)", key="t2_birth")
    
    if st.button("소유주 검색", use_container_width=True, type="primary"):
        st.session_state.owner_search_res = [r for r in all_records if len(r) > 12 and (sn in r[2]) and (not sb or sb == r[3])]
        
    if st.session_state.owner_search_res is not None:
        st.success(f"검색 결과: 최신순 {len(st.session_state.owner_search_res)}건")
        for idx, row in enumerate(st.session_state.owner_search_res):
            addr, room, name, birth, phone, deposit, rent, end_date, _, _, memo, reg_date, registrar, status = (row + [""]*14)[:14]
            
            with st.container():
                status_tag = " 🚨[비공개 매물]" if status == "비공개" else ""
                st.markdown(f"#### 👤 {name} ({birth}) | 📍 {addr} {room}{status_tag}")
                unlock_key = f"unlock_own_{addr}_{room}"
                
                free_unlock = is_unlocked_recently(addr, room)
                is_open = free_unlock or st.session_state.get(unlock_key, False)
                
                if is_open:
                    if free_unlock and not st.session_state.get(unlock_key, False) and user_email != ADMIN_EMAIL:
                        st.caption("⏳ 최근 24시간 내 열람 기록이 확인되어 토큰 차감 없이 무료로 개방되었습니다.")
                    st.info(f"**연락처:** {phone}  |  **특이사항:** {memo}  |  **만기/보증/월세:** {end_date} / {deposit} / {rent}")
                    
                    with st.form(f"edit_own_{idx}", clear_on_submit=True):
                        edit_memo = st.text_input("수정 요청 사유 (예: 번호 오기재)", key=f"req_own_{idx}")
                        # 꿀팁 안내 문구 추가
                        st.caption("💡 꿀팁: 변경된 진짜 연락처 등 정확한 정보를 함께 남겨주시면, 대표님이 확인 후 [포상 토큰 +1개]를 즉시 지급해 드립니다!")
                        if st.form_submit_button("🛠 대표님께 수정 요청하기"):
                            if edit_memo:
                                ws_request.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_name, addr, room, edit_memo, "대기중"])
                                st.success("요청이 전송되었습니다!")
                else:
                    if st.button(f"🔓 상세 정보 열람 (토큰 1개 차감)", key=f"btn_own_{idx}"):
                        if user_tokens >= 1:
                            update_token(-1, f"매물 열람 ({addr} {room})")
                            st.session_state[unlock_key] = True
                            st.rerun()
                        else:
                            st.error("보유한 열람권(토큰)이 부족합니다.")
                st.write("---")

# --- [탭 3] 신규 등록 ---
with tabs[2]:
    st.subheader("📝 신규 매물 등록 (완료 시 토큰 +1 획득)")
    with st.form("reg_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            f_city = st.text_input("시/도", "서울")
            f_dong = st.text_input("읍/면/동 *", placeholder="방이동")
            f_bunji = st.text_input("번지 *", placeholder="28-2")
            f_sub_dong = st.text_input("번지 뒤 '동' (없으면 0)", value="0")
            st.markdown("---")
            f_deposit = st.text_input("보증금 (만원)")
            f_rent = st.text_input("월세 (만원)")
        with col2:
            f_gu = st.text_input("구/군", "송파구")
            f_room = st.text_input("호실 * (숫자만)", placeholder="101")
            f_name = st.text_input("임대인 성함 *")
            f_birth = st.text_input("생년월일 * (숫자만)", placeholder="940101")
            f_phone = st.text_input("연락처 * (숫자만)", placeholder="01012345678")
            st.markdown("---")
            f_end_date = st.text_input("현 임대차 만기일", placeholder="2026-05-30")
        f_memo = st.text_area("특이사항")
        
        if st.form_submit_button("💾 데이터 검증 및 매물 등록", type="primary", use_container_width=True):
            if not f_room.isdigit() or not f_birth.isdigit() or not f_phone.isdigit():
                st.error("⚠️ 호실, 생년월일, 연락처는 오직 '숫자'만 입력 가능합니다.")
            elif not f_dong or not f_bunji or not f_name:
                st.warning("⚠️ 필수 항목(*)을 모두 입력해주세요.")
            else:
                full_addr = f"{f_city} {f_gu} {f_dong} {clean_bunji(f_bunji)}"
                room_final = f"{f_sub_dong}동 {f_room}호" if f_sub_dong != "0" else f"{f_room}호"
                
                # 중복 차단 완화: 과거에 올렸더라도 '비공개' 상태면 중복 통과 (부활 등록 가능)
                duplicate = [r for r in all_records if r[0] == full_addr and r[1] == room_final and r[12] == user_name and r[13] != "비공개"]
                if duplicate:
                    st.error(f"❌ 이미 {user_name}님이 등록하신 매물입니다!")
                else:
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    new_row = [full_addr, room_final, f_name, f_birth, format_phone(f_phone), f_deposit, f_rent, f_end_date, "", "", f_memo, now, user_name, "정상"]
                    ws_data.append_row(new_row)
                    update_token(1, f"신규 매물 등록 ({full_addr} {room_final})")
                    st.success("✅ 매물이 성공적으로 등록되었습니다! 열람 포인트 +1 획득! 💰")
                    st.rerun()

# --- [탭 4] 관리자 전용 ---
if user_email == ADMIN_EMAIL:
    with tabs[3]:
        st.subheader("👑 관리자 종합 대시보드")
        
        # 1. 수정 요청 현황 (원스톱 처리 도입)
        st.write("#### 🚨 직원 수정 요청 원스톱 처리")
        if pending_reqs_with_idx:
            st.warning(f"처리 대기 중인 수정 요청이 {len(pending_reqs_with_idx)}건 있습니다.")
            for row_idx, r_req in pending_reqs_with_idx:
                with st.container():
                    st.info(f"**[요청자: {r_req[1]}]** 📍 {r_req[2]} {r_req[3]}\n\n**사유:** {r_req[4]}")
                    cA, cB, cC = st.columns(3)
                    
                    if cA.button("✅ 수정 완료", key=f"ok_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "처리완료")
                        st.cache_resource.clear()
                        st.rerun()
                        
                    if cB.button("🔒 비공개(보류) 처리", key=f"hide_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "비공개")
                        # 메인 DB에서 찾아 상태를 '비공개'로 덮어쓰기
                        main_vals = ws_data.get_all_values()
                        for m_idx, m_row in enumerate(main_vals):
                            if m_idx > 0 and len(m_row) > 12 and m_row[0] == r_req[2] and m_row[1] == r_req[3]:
                                ws_data.update_cell(m_idx + 1, 14, "비공개")
                        st.cache_resource.clear()
                        st.rerun()
                        
                    if cC.button("🗑️ 요청 삭제", key=f"del_{row_idx}"):
                        ws_request.update_cell(row_idx, 6, "삭제")
                        st.cache_resource.clear()
                        st.rerun()
                st.write("---")
        else:
            st.info("현재 대기 중인 수정 요청이 없습니다.")
            
        st.write("---")
        
        # 2. 직원 관리 및 토큰 수동 지급
        st.write("#### 👥 직원 토큰 관리 및 수동 지급")
        
        c_add, c_grant = st.columns(2)
        with c_add:
            with st.expander("➕ 신규 직원 등록", expanded=False):
                new_email = st.text_input("구글 이메일")
                new_n = st.text_input("직원 실명 (예: 김소장)")
                start_token = st.number_input("초기 지급 토큰 수", value=10, step=1)
                if st.button("직원 권한 부여"):
                    if "@" in new_email and new_n:
                        ws_staff.append_row([new_email, new_n, datetime.now().strftime('%Y-%m-%d'), start_token])
                        ws_history.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), new_n, start_token, start_token, "신규 입사 초기 지급"])
                        st.success(f"{new_n}님이 추가되었습니다!")
                        st.cache_resource.clear()
                        st.rerun()
                        
        with c_grant:
            with st.expander("🎁 기존 직원 토큰 수동 지급/차감", expanded=False):
                target_staff = st.selectbox("대상 직원 선택", [row['이름'] for row in staff_records])
                grant_amount = st.number_input("지급/차감 수량 (차감은 - 입력)", value=1)
                grant_reason = st.text_input("사유 작성 (예: 1001호 번호 수정 포상)")
                if st.button("토큰 적용하기", type="primary"):
                    if grant_reason:
                        for i, r in enumerate(staff_records):
                            if r['이름'] == target_staff:
                                old_token = int(r.get('보유토큰', 0))
                                new_val = old_token + grant_amount
                                ws_staff.update_cell(i + 2, 4, new_val)
                                ws_history.append_row([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), target_staff, grant_amount, new_val, f"관리자 수동 지급: {grant_reason}"])
                                st.success(f"{target_staff}님에게 토큰이 적용되었습니다.")
                                st.cache_resource.clear()
                                st.rerun() 
                                break
                    else:
                        st.warning("지급 사유를 입력해주세요.")
                        
        if staff_records:
            st.dataframe(pd.DataFrame(staff_records), use_container_width=True)
            
        st.write("---")
        
        # 3. 전체 열람 감사(Audit) 로그
        st.write("#### 👁️‍🗨️ 전체 직원 데이터 열람/이용 추적 (최근 50건)")
        if history_records:
            df_all_hist = pd.DataFrame(history_records, columns=["일시", "직원명", "변동량", "잔여토큰", "이용 상세 사유"])
            st.dataframe(df_all_hist.iloc[::-1].head(50), hide_index=True, use_container_width=True)