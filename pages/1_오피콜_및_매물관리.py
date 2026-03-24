import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import json
import requests
import re
import pandas as pd

# 🚨 [보안 방어막] 로그인을 거치지 않고 몰래 들어오면 메인 로비(app.py)로 강제 이동!
if "connected" not in st.session_state or not st.session_state.connected:
    st.switch_page("app.py")

# --- 💡 1. UI 다이어트 & 설정 ---
st.set_page_config(page_title="오피콜 & 매물관리", page_icon="🏢", layout="wide")
st.markdown("""
    <style>
        html, body, [class*="css"]  { font-size: 14px !important; }
        .stButton>button { padding: 0.2rem 0.5rem; min-height: 2rem; }
        .block-container { padding-top: 3.5rem; padding-bottom: 2rem; }
        [data-testid="stSidebar"] { width: 280px !important; }
        button[data-baseweb="tab"] > div[data-testid="stMarkdownContainer"] > p { font-size: 15px; margin-bottom: 0px; }
        button[data-baseweb="tab"] { height: 3rem; }
        .locked-tab { text-align: center; padding: 50px; background-color: #f8f9fa; border-radius: 10px; border: 2px dashed #ff4b4b; margin-top: 20px;}
    </style>
""", unsafe_allow_html=True)

ADMIN_EMAIL = "dldmdcks94@gmail.com"

# --- 💡 대한민국 표준 행정구역 DB ---
KOREA_REGION_DATA = {
    "서울특별시": {
        "강남구": ["개포동", "논현동", "대치동", "도곡동", "삼성동", "세곡동", "수서동", "신사동", "압구정동", "역삼동", "율현동", "일원동", "자곡동", "청담동"],
        "강동구": ["강일동", "고덕동", "길동", "둔촌동", "명일동", "상일동", "성내동", "암사동", "천호동"],
        "강북구": ["미아동", "번동", "수유동", "우이동"],
        "강서구": ["가양동", "개화동", "공항동", "과해동", "내발산동", "등촌동", "마곡동", "방화동", "염창동", "오곡동", "오쇠동", "외발산동", "화곡동"],
        "관악구": ["남현동", "봉천동", "신림동"],
        "광진구": ["광장동", "구의동", "군자동", "능동", "자양동", "중곡동", "화양동"],
        "구로구": ["가리봉동", "개봉동", "고척동", "구로동", "궁동", "수궁동", "신도림동", "오류동", "온수동", "천왕동", "항동"],
        "금천구": ["가산동", "독산동", "시흥동"],
        "노원구": ["공릉동", "상계동", "월계동", "중계동", "하계동"],
        "도봉구": ["도봉동", "방학동", "쌍문동", "창동"],
        "동대문구": ["답십리동", "신설동", "용두동", "이문동", "장안동", "전농동", "제기동", "청량리동", "회기동", "휘경동"],
        "동작구": ["노량진동", "대방동", "동작동", "본동", "사당동", "상도동", "신대방동", "흑석동"],
        "마포구": ["공덕동", "구수동", "노고산동", "당인동", "대흥동", "도화동", "동교동", "마포동", "망원동", "상수동", "상암동", "서교동", "성산동", "신공덕동", "신수동", "신정동", "아현동", "연남동", "염리동", "용강동", "중동", "창전동", "토정동", "하중동", "합정동"],
        "서대문구": ["남가좌동", "냉천동", "대신동", "대현동", "미근동", "봉원동", "북가좌동", "북아현동", "신촌동", "연희동", "영천동", "옥천동", "창천동", "천연동", "충정로2가", "충정로3가", "합동", "현저동", "홍은동", "홍제동"],
        "서초구": ["내곡동", "반포동", "방배동", "서초동", "신원동", "양재동", "염곡동", "우면동", "원지동", "잠원동"],
        "성동구": ["금호동1가", "금호동2가", "금호동3가", "금호동4가", "도선동", "마장동", "사근동", "상왕십리동", "성수1가1동", "성수1가2동", "성수2가1동", "성수2가3동", "송정동", "옥수동", "용답동", "응봉동", "하왕십리동", "행당동"],
        "성북구": ["길음동", "돈암동", "동선동", "동소문동", "보문동", "삼선동", "상월곡동", "석관동", "성북동", "안암동", "장위동", "정릉동", "종암동", "하월곡동"],
        "송파구": ["가락동", "거여동", "마천동", "문정동", "방이동", "삼전동", "석촌동", "송파동", "신천동", "오금동", "잠실동", "장지동", "풍납동"],
        "양천구": ["목동", "신월동", "신정동"],
        "영등포구": ["당산동", "대림동", "도림동", "문래동", "신길동", "양평동", "여의도동", "영등포동"],
        "용산구": ["갈월동", "남영동", "도원동", "동빙고동", "동자동", "문배동", "보광동", "산천동", "서계동", "서빙고동", "신계동", "신창동", "용문동", "용산동", "원효로", "이촌동", "이태원동", "주성동", "청암동", "청파동", "한강로", "한남동", "효창동", "후암동"],
        "은평구": ["갈현동", "구산동", "녹번동", "대조동", "불광동", "수색동", "신사동", "역촌동", "응암동", "증산동", "진관동"],
        "종로구": ["가회동", "견지동", "경운동", "공평동", "관수동", "관철동", "관훈동", "교남동", "교북동", "구기동", "궁정동", "권농동", "낙원동", "내수동", "내자동", "누상동", "누하동", "당주동", "도렴동", "돈의동", "동숭동", "명륜1가", "명륜2가", "명륜3가", "명륜4가", "묘동", "무악동", "봉익동", "부암동", "사직동", "삼청동", "서린동", "세종로", "소격동", "송월동", "송현동", "수송동", "숭인동", "신교동", "신문로1가", "신문로2가", "신영동", "안국동", "연건동", "연지동", "예지동", "옥인동", "와룡동", "운니동", "원남동", "원서동", "이화동", "익선동", "인사동", "인의동", "장사동", "재동", "적선동", "종로1가", "종로2가", "종로3가", "종로4가", "종로5가", "종로6가", "중학동", "창성동", "창신동", "청운동", "청진동", "체부동", "충신동", "통의동", "통인동", "팔판동", "평동", "평창동", "필운동", "행촌동", "혜화동", "홍파동", "화동", "효자동", "효제동", "훈정동"],
        "중구": ["광희동", "남대문로", "남산동", "남창동", "남학동", "다동", "만리동", "명동", "무교동", "무학동", "묵정동", "방산동", "봉래동", "북창동", "산림동", "삼각동", "서소문동", "소공동", "수표동", "수하동", "순화동", "신당동", "쌍림동", "예관동", "예장동", "오장동", "을지로", "의주로", "인현동", "입정동", "장교동", "장충동", "저동", "정동", "주교동", "주자동", "중림동", "초동", "충무로", "충정로1가", "태평로", "필동", "황학동", "회현동", "흥인동"],
        "중랑구": ["망우동", "면목동", "묵동", "상봉동", "신내동", "중화동"]
    },
    "경기도": {"수원시": [], "성남시": [], "고양시": [], "용인시": [], "부천시": [], "안산시": [], "안양시": [], "남양주시": [], "화성시": [], "평택시": [], "의정부시": [], "시흥시": [], "파주시": [], "광명시": [], "김포시": [], "군포시": [], "광주시": [], "이천시": [], "양주시": [], "오산시": [], "구리시": [], "안성시": [], "포천시": [], "의왕시": [], "하남시": [], "여주시": [], "양평군": [], "동두천시": [], "과천시": [], "가평군": [], "연천군": []},
    "인천광역시": {"계양구": [], "미추홀구": [], "남동구": [], "동구": [], "부평구": [], "서구": [], "연수구": [], "중구": [], "강화군": [], "옹진군": []},
    "부산광역시": {"강서구": [], "금정구": [], "기장군": [], "남구": [], "동구": [], "동래구": [], "부산진구": [], "북구": [], "사상구": [], "사하구": [], "서구": [], "수영구": [], "연제구": [], "영도구": [], "중구": []},
    "대구광역시": {"남구": [], "달서구": [], "달성군": [], "동구": [], "북구": [], "서구": [], "수성구": [], "중구": [], "군위군": []},
    "광주광역시": {"광산구": [], "남구": [], "동구": [], "북구": [], "서구": []},
    "대전광역시": {"대덕구": [], "동구": [], "서구": [], "유성구": [], "중구": []},
    "울산광역시": {"남구": [], "동구": [], "북구": [], "중구": [], "울주군": []},
    "세종특별자치시": {"세종시": []},
    "강원특별자치도": {"춘천시": [], "원주시": [], "강릉시": [], "동해시": [], "태백시": [], "속초시": [], "삼척시": [], "홍천군": [], "횡성군": [], "영월군": [], "평창군": [], "정선군": [], "철원군": [], "화천군": [], "양구군": [], "인제군": [], "고성군": [], "양양군": []},
    "충청북도": {"청주시": [], "충주시": [], "제천시": [], "보은군": [], "옥천군": [], "영동군": [], "증평군": [], "진천군": [], "괴산군": [], "음성군": [], "단양군": []},
    "충청남도": {"천안시": [], "공주시": [], "보령시": [], "아산시": [], "서산시": [], "논산시": [], "계룡시": [], "당진시": [], "금산군": [], "부여군": [], "서천군": [], "청양군": [], "홍성군": [], "예산군": [], "태안군": []},
    "전북특별자치도": {"전주시": [], "군산시": [], "익산시": [], "정읍시": [], "남원시": [], "김제시": [], "완주군": [], "진안군": [], "무주군": [], "장수군": [], "임실군": [], "순창군": [], "고창군": [], "부안군": []},
    "전라남도": {"목포시": [], "여수시": [], "순천시": [], "나주시": [], "광양시": [], "담양군": [], "곡성군": [], "구례군": [], "고흥군": [], "보성군": [], "화순군": [], "장흥군": [], "강진군": [], "해남군": [], "영암군": [], "무안군": [], "함평군": [], "영광군": [], "장성군": [], "완도군": [], "진도군": [], "신안군": []},
    "경상북도": {"포항시": [], "경주시": [], "김천시": [], "안동시": [], "구미시": [], "영주시": [], "영천시": [], "상주시": [], "문경시": [], "경산시": [], "의성군": [], "청송군": [], "영양군": [], "영덕군": [], "청도군": [], "고령군": [], "성주군": [], "칠곡군": [], "예천군": [], "봉화군": [], "울진군": [], "울릉군": []},
    "경상남도": {"창원시": [], "진주시": [], "통영시": [], "사천시": [], "김해시": [], "밀양시": [], "거제시": [], "양산시": [], "의령군": [], "함안군": [], "창녕군": [], "고성군": [], "남해군": [], "하동군": [], "산청군": [], "함양군": [], "거창군": [], "합천군": []},
    "제주특별자치도": {"제주시": [], "서귀포시": []}
}

# --- 2. 데이터베이스 연동 및 시트 객체 생성 ---
try:
    token_dict = json.loads(st.secrets["google_token_json"])
except Exception:
    st.error("❌ 금고 설정(Secrets)을 확인해주세요.")
    st.stop()

@st.cache_resource
def get_ss():
    creds = Credentials.from_authorized_user_info(token_dict)
    ss = gspread.authorize(creds).open_by_key('121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA')
    return ss

ss = get_ss()
ws_data = ss.get_worksheet_by_id(1969836502) 

# 시트 확인 및 자동 생성
try: ws_staff = ss.worksheet("직원명단")
except: pass
try: ws_request = ss.worksheet("수정요청")
except: pass
try: ws_history = ss.worksheet("토큰내역")
except: pass
try: ws_settings = ss.worksheet("환경설정")
except: pass

@st.cache_data(ttl=60)
def fetch_all_data():
    return ws_data.get_all_values(), ws_staff.get_all_records(), ws_request.get_all_values(), ws_history.get_all_values(), ws_settings.get_all_values()

all_data_raw, staff_records, req_all_values, history_all_values, settings_all_values = fetch_all_data()

staff_dict = {str(row['이메일']).strip(): row for row in staff_records}
ALLOWED_USERS = [ADMIN_EMAIL] + list(staff_dict.keys())

# 인증 정보 가져오기
user_email = st.session_state.user_info.get("email", "")
if user_email not in ALLOWED_USERS:
    st.error(f"⚠️ 승인되지 않은 계정입니다 ({user_email}). 대표님께 권한을 요청하세요.")
    st.stop()

# --- 🕒 오전 8시 리셋 및 할당량 로직 ---
now_kst = datetime.utcnow() + timedelta(hours=9)
if now_kst.hour >= 8:
    today_shift = now_kst.strftime("%Y-%m-%d")
else:
    today_shift = (now_kst - timedelta(days=1)).strftime("%Y-%m-%d")

if user_email == ADMIN_EMAIL:
    user_name, user_tokens, staff_row_index = "이응찬 대표", 9999, None
    is_locked = False
    has_vip = True
    quota_done = 5
else:
    user_name = staff_dict[user_email]['이름']
    user_tokens = int(staff_dict[user_email].get('보유토큰', 0))
    staff_row_index = list(staff_dict.keys()).index(user_email) + 2 
    
    last_shift = str(staff_dict[user_email].get('최근할당일', ''))
    quota_done = int(staff_dict[user_email].get('할당진행도', 0)) if str(staff_dict[user_email].get('할당진행도', '')).isdigit() else 0
    
    if last_shift != today_shift:
        ws_staff.update_cell(staff_row_index, 7, today_shift)
        ws_staff.update_cell(staff_row_index, 8, 0)
        ws_staff.update_cell(staff_row_index, 9, 0) 
        quota_done = 0
        st.cache_data.clear()
        
    has_vip = (str(staff_dict[user_email].get('VIP권한', 'X')) == 'O')
    is_locked = (quota_done < 5)

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
def is_valid_date_format(date_str):
    return bool(re.match(r'^\d{4}\.\d{2}\.\d{2}$', str(date_str).strip()))

def update_token(target_name, amount, reason):
    if target_name == "이응찬 대표": return
    target_idx = None
    for i, r in enumerate(staff_records):
        if r['이름'] == target_name:
            target_idx = i + 2
            old_token = int(r.get('보유토큰', 0)) if str(r.get('보유토큰', '')).isdigit() else 0
            break
            
    if target_idx:
        now_str = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')
        new_token_val = old_token + amount
        ws_staff.update_cell(target_idx, 4, new_token_val)
        ws_history.append_row([now_str, target_name, amount, new_token_val, reason], value_input_option='USER_ENTERED')

def is_unlocked_recently(addr, room):
    if user_email == ADMIN_EMAIL: return True
    now = datetime.now()
    search_str = f"({addr} {room})"
    for r in reversed(history_records):
        if len(r) > 4 and r[1] == user_name and search_str in r[4] and str(r[2]) == "-1":
            try:
                record_time = datetime.strptime(r[0].replace("'", ""), '%Y-%m-%d %H:%M:%S')
                if (now - record_time).total_seconds() <= 86400: return True
            except: continue
    return False

# --- 데이터 전처리 ---
pending_reqs_with_idx = [(i+1, r) for i, r in enumerate(req_all_values) if i > 0 and len(r) > 5 and r[5] == '대기중']
pending_req_count = len(pending_reqs_with_idx)

all_records_raw = all_data_raw[1:]
temp_dict = {}
my_month_score = 0
this_month_str = now_kst.strftime("%Y-%m")

for r in all_records_raw:
    reg = str(r[23]) if len(r) > 23 else ""
    registrar = str(r[24]) if len(r) > 24 else ""
    if registrar == user_name and this_month_str in reg and "2020-" not in reg:
        my_month_score += 5 

for r in history_records:
    if len(r) > 4 and r[1] == user_name and this_month_str in r[0]:
        if "갱신" in r[4] or "수정" in r[4]:
            if "[아파트]" in r[4] or "[오피스텔]" in r[4]:
                my_month_score += 3
            else:
                my_month_score += 1

for i, r in enumerate(all_records_raw):
    row_idx = i + 2 
    status = r[25].strip() if len(r) > 25 else "정상"
    if user_email != ADMIN_EMAIL and status in ["비공개", "삭제", "잘못됨"]: continue
        
    r_padded = (r + [""]*26)[:26]
    if not r_padded[25]: r_padded[25] = "정상"
    r_padded.append(row_idx)
    
    key = (str(r_padded[2]).replace(" ",""), str(r_padded[3]), str(r_padded[4]), str(r_padded[7]), str(r_padded[8]), str(r_padded[9]), str(r_padded[10]))
    temp_dict[key] = r_padded 

all_records = list(temp_dict.values())
all_records.reverse()

# --- 사이드바 ---
st.sidebar.markdown(f"### 👤 {user_name}")
st.sidebar.markdown(f"**보유 토큰:** `{user_tokens} 개`")
st.sidebar.markdown("""
<div style='font-size: 13px; color: #4a4a4a; margin-top: -5px;'>
    <b style='color:#1E90FF'>[🪙 보유 토큰 안내]</b><br>
    👉 신규 매물 등록 (빌라/상가) <b>+3</b><br>
    👉 일반/소유주 검색 후 갱신 <b>+2</b><br>
    👉 오늘의 오피콜 갱신 (무료) <b>+1</b><br>
    👉 매물 상세정보 열람 <b>-1</b>
</div>
""", unsafe_allow_html=True)
st.sidebar.write("")
st.sidebar.markdown(f"**이번 달 기여도:** `{my_month_score} 점`")
st.sidebar.markdown("""
<div style='font-size: 13px; color: #4a4a4a; margin-top: -5px;'>
    <b style='color:#FF4500'>[🏆 기여도 랭킹 점수]</b><br>
    🥇 신규 매물 발굴 <b>+5점</b><br>
    🥈 아파트/오피스텔 갱신 <b>+3점</b><br>
    🥉 일반 빌라/예전 DB 갱신 <b>+1점</b>
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
    st.switch_page("app.py")

# --- 설정값 불러오기 ---
try:
    target_addresses_str = settings_all_values[1][1] if len(settings_all_values) > 1 else ""
except IndexError:
    target_addresses_str = ""

target_addresses = [a.strip().replace(" ", "") for a in target_addresses_str.split(",") if a.strip()]

# 공통 함수: 수정/갱신 폼 렌더링
def render_edit_form(row_idx, city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, addr_str, room_str, form_key, reward_reason, reward_amount):
    with st.form(f"edit_{form_key}", clear_on_submit=True):
        st.caption("※ 항목을 명확히 나누어 입력해주세요. 기존 내역은 타임라인으로 누적 보존됩니다.")
        c1, c2, c3, c4 = st.columns(4)
        
        type_opts = ["아파트", "오피스텔", "다세대", "다가구", "빌라", "상가", "미분류"]
        t_idx = type_opts.index(b_type) if b_type in type_opts else 0
        new_btype = c1.selectbox("용도", type_opts, index=t_idx)
        
        new_deposit = c2.text_input("보증금 (0원 단위. 예: 10000000)", value=str(deposit))
        new_rent = c3.text_input("월세 (0원 단위)", value=str(rent))
        new_end = c4.text_input("만기일 (예: 2026.04.00)", value=str(end_date), placeholder="2026.04.00")
        
        new_memo_add = st.text_input("추가 특이사항 (예: 보증금 조절 가능, 강아지 환영)")
        
        if st.form_submit_button(f"🛠️ 데이터 갱신 및 자동 반영 (+{reward_amount} 토큰)"):
            if not new_end or not is_valid_date_format(new_end):
                st.error("🚨 만기일은 반드시 'YYYY.MM.DD' 포맷으로 입력해주세요. (예: 2026.04.00)")
                return False
                
            now_kst_dt = datetime.utcnow() + timedelta(hours=9)
            now_str = now_kst_dt.strftime('%Y-%m-%d %H:%M:%S')
            short_date = now_kst_dt.strftime('%y.%m.%d')
            
            ws_data.update_cell(row_idx, 26, "비공개")
            
            added_log = f"[{short_date}] "
            if str(deposit) != new_deposit or str(rent) != new_rent: added_log += f"보/월 {new_deposit}/{new_rent} 변경. "
            if str(end_date) != new_end: added_log += f"만기 {new_end}. "
            if new_memo_add: added_log += new_memo_add
            
            new_full_memo = f"{memo}\n👉 {added_log}".strip() if memo else f"👉 {added_log}"
            
            new_row = [city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, new_btype, appr_date, viol, land_area, room_area, curr_biz, new_deposit, new_rent, fee, new_end, new_full_memo, now_str, user_name, "정상"]
            ws_data.append_row(new_row, value_input_option='USER_ENTERED')
            
            update_token(user_name, reward_amount, f"{reward_reason} ({addr_str} {room_str}) [{new_btype}]")
            st.cache_data.clear()
            st.success(f"✅ 데이터가 최신화되었습니다! (토큰 +{reward_amount})")
            return True
    return False

# --- 💡 탭 구성 (홈 화면과 관리자 탭을 잘라냈습니다!) ---
tab_names = ["🔍 매물 검색", "👤 소유주 검색", "📞 오늘의 오피콜", "📝 신규 등록"]
if has_vip or user_email == ADMIN_EMAIL:
    tab_names.append("⏰ 3개월 이내 만기")

created_tabs = st.tabs(tab_names)
t_search, t_owner, t_call, t_new = created_tabs[0], created_tabs[1], created_tabs[2], created_tabs[3]

if has_vip or user_email == ADMIN_EMAIL:
    t_vip = created_tabs[4]
else:
    t_vip = None

# --- [탭 1] 매물 검색 ---
with t_search:
    if is_locked:
        st.markdown(f"<div class='locked-tab'><h2>🔒 오늘 할당량을 먼저 완수해주세요!</h2><p>오늘의 오피콜 할당량({quota_done}/5건)을 완료해야 검색 기능을 사용할 수 있습니다.</p></div>", unsafe_allow_html=True)
    else:
        c_search1, c_search2, c_search3 = st.columns([1, 1, 1])
        sido_opts = ["전체"] + list(KOREA_REGION_DATA.keys())
        sido_idx = sido_opts.index("서울특별시") if "서울특별시" in sido_opts else 0
        sel_sido = c_search1.selectbox("시/도", sido_opts, index=sido_idx)
        
        gu_opts = ["전체"] + list(KOREA_REGION_DATA[sel_sido].keys()) if sel_sido != "전체" else ["전체"]
        gu_idx = gu_opts.index("송파구") if "송파구" in gu_opts else 0
        sel_sigungu = c_search2.selectbox("시/군/구", gu_opts, index=gu_idx)
        
        dong_opts = ["전체"] + KOREA_REGION_DATA[sel_sido][sel_sigungu] if sel_sigungu != "전체" and sel_sido != "전체" else ["전체"]
        dong_idx = dong_opts.index("방이동") if "방이동" in dong_opts else 0
        sel_dong = c_search3.selectbox("법정동", dong_opts, index=dong_idx)
        
        with st.form("search_addr_form"):
            c_search4, c_search5 = st.columns([2, 1])
            b_search = c_search4.text_input("번지 / 건물명", placeholder="28-2 또는 엘퍼스트")
            r_search = c_search5.text_input("호실", placeholder="101")
            submitted = st.form_submit_button("🔍 주소 검색", type="primary", use_container_width=True)
            
        if submitted:
            res = []
            for r in all_records:
                match_sido = (sel_sido == "전체" or sel_sido == str(r[0]).strip())
                match_sigungu = (sel_sigungu == "전체" or sel_sigungu == str(r[1]).strip())
                match_dong = (sel_dong == "전체" or sel_dong == str(r[2]).strip())
                b_target = (f"{r[3]}-{r[4]}" if str(r[4]) != "0" else str(r[3])) + str(r[6]).replace(" ","")
                match_b = (b_search.replace(" ","") in b_target.replace(" ","")) if b_search else True
                room_target = str(r[7]).replace(" ","") + str(r[8]).replace(" ","")
                match_r = (r_search.replace(" ","") in room_target.replace(" ","")) if r_search else True
                
                if match_sido and match_sigungu and match_dong and match_b and match_r: res.append(r)
            res.sort(key=lambda x: extract_room_number(x[8]))
            st.session_state.addr_search_res = res
        
        if st.session_state.get("addr_search_res"):
            st.caption(f"검색 결과: {len(st.session_state.addr_search_res)}건")
            for idx, row in enumerate(st.session_state.addr_search_res):
                city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, reg_date, registrar, status, row_idx = row
                
                addr_str = f"{city} {gu} {dong} {bon}" + (f"-{bu}" if bu and bu != "0" else "")
                if bldg: addr_str += f" {bldg}"
                room_str = f"{d_dong} {room}" if d_dong and d_dong != "동없음" else f"{room}"
                
                manager_name = next((m for b, m in MANAGER_BUILDINGS.items() if f" {b} " in f" {addr_str} "), None)
                is_manager_locked = manager_name and manager_name != user_name and user_email != ADMIN_EMAIL
                m_tag = f" | 👑 {manager_name} 관리매물" if manager_name else ""
                
                st.markdown(f"**📍 {addr_str} | {room_str} {m_tag}**")
                
                if is_manager_locked:
                    st.error(f"🔒 {manager_name} 전담 매물입니다. (열람 불가)")
                    st.write("---")
                    continue

                unlock_key = f"unlock_addr_{addr_str}_{room_str}"
                toggle_key = f"toggle_addr_{idx}"
                is_unlocked = is_unlocked_recently(addr_str, room_str) or st.session_state.get(unlock_key, False)
                
                if is_unlocked:
                    if st.button("🔓 재열람가능", key=f"btn_re_{idx}"):
                        st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                    if st.session_state.get(toggle_key, False):
                        st.info(f"**용도:** {b_type}\n\n**소유주:** {name}({birth}) | **연락처:** {phone}\n\n**보증/월세:** {deposit}/{rent} | **만기:** {end_date}\n\n**특이사항/히스토리:**\n{memo}")
                        
                        if render_edit_form(row_idx, city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, addr_str, room_str, f"addr_upd_{idx}", "일반 검색 갱신", 2):
                            st.rerun()
                else:
                    if st.button("🔓 상세정보 열람 (토큰 1개)", key=f"btn_addr_{idx}"):
                        if user_tokens >= 1 or user_email == ADMIN_EMAIL:
                            update_token(user_name, -1, f"매물 열람 ({addr_str} {room_str})")
                            st.session_state[unlock_key] = True
                            st.session_state[toggle_key] = True 
                            st.cache_data.clear() 
                            st.rerun()
                        else: st.error("토큰이 부족합니다. [오늘의 오피콜]이나 [신규 등록]을 통해 토큰을 모아주세요.")
                st.write("---")

# --- [탭 2] 소유주 검색 ---
with t_owner:
    if is_locked:
        st.markdown(f"<div class='locked-tab'><h2>🔒 오늘 할당량을 먼저 완수해주세요!</h2><p>오늘의 오피콜 할당량({quota_done}/5건)을 완료해야 검색 기능을 사용할 수 있습니다.</p></div>", unsafe_allow_html=True)
    else:
        with st.form("search_owner_form"):
            c4, c5 = st.columns(2)
            sn = c4.text_input("성함", key="t2_name")
            sb = c5.text_input("생년월일(6자리)", key="t2_birth")
            submitted_own = st.form_submit_button("소유주 검색", type="primary", use_container_width=True)
            
        if submitted_own:
            res = [r for r in all_records if (sn in str(r[9])) and (not sb or sb == str(r[10]))]
            res.sort(key=lambda x: extract_room_number(x[8])) 
            st.session_state.owner_search_res = res
            
        if st.session_state.get("owner_search_res"):
            st.caption(f"검색 결과: {len(st.session_state.owner_search_res)}건")
            for idx, row in enumerate(st.session_state.owner_search_res):
                city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, reg_date, registrar, status, row_idx = row
                
                addr_str = f"{city} {gu} {dong} {bon}" + (f"-{bu}" if bu and bu != "0" else "")
                if bldg: addr_str += f" {bldg}"
                room_str = f"{d_dong} {room}" if d_dong and d_dong != "동없음" else f"{room}"
                
                manager_name = next((m for b, m in MANAGER_BUILDINGS.items() if f" {b} " in f" {addr_str} "), None)
                is_manager_locked = manager_name and manager_name != user_name and user_email != ADMIN_EMAIL
                m_tag = f" | 👑 {manager_name} 관리매물" if manager_name else ""
                
                st.markdown(f"**👤 {name}({birth}) | 📍 {addr_str} {room_str} {m_tag}**")

                if is_manager_locked:
                    st.error(f"🔒 {manager_name} 전담 매물입니다. (열람 불가)")
                    st.write("---")
                    continue

                unlock_key = f"unlock_own_{addr_str}_{room_str}"
                toggle_key = f"toggle_own_{idx}"
                is_unlocked = is_unlocked_recently(addr_str, room_str) or st.session_state.get(unlock_key, False)
                
                if is_unlocked:
                    if st.button("🔓 재열람가능", key=f"btn_re_own_{idx}"):
                        st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                    if st.session_state.get(toggle_key, False):
                        st.info(f"**용도:** {b_type}\n\n**연락처:** {phone} | **만기/보/월:** {end_date} / {deposit} / {rent}\n\n**특이사항/히스토리:**\n{memo}")
                        
                        if render_edit_form(row_idx, city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, addr_str, room_str, f"own_upd_{idx}", "소유주 검색 갱신", 2):
                            st.rerun()
                else:
                    if st.button("🔓 상세정보 열람 (토큰 1개)", key=f"btn_own_{idx}"):
                        if user_tokens >= 1 or user_email == ADMIN_EMAIL:
                            update_token(user_name, -1, f"매물 열람 ({addr_str} {room_str})")
                            st.session_state[unlock_key] = True
                            st.session_state[toggle_key] = True
                            st.cache_data.clear() 
                            st.rerun()
                        else: st.error("토큰 부족")
                st.write("---")

# --- [탭 3] 오늘의 오피콜 ---
with t_call:
    st.subheader(f"📞 오늘의 오피콜 (진행도: {quota_done}/5)")
    
    if quota_done >= 5:
        st.success("🎉 오늘의 오피콜 5건을 모두 완료했습니다! 이제 잠금이 해제되어 자유롭게 매물 검색이 가능합니다.")
        st.info("💡 토큰이 더 필요하시다면 [📝 신규 등록] 탭에서 공실클럽 빌라 매물을 추가하여 +3 토큰을 획득하세요!")
    else:
        st.write("시스템이 배정한 가장 시급한 타겟 매물입니다. 콜을 돌려 DB를 최신화해주세요! (열람 무료)")
        
        target_pool = []
        for r in all_records:
            city, gu, dong, bon, bu = r[0], r[1], r[2], r[3], r[4]
            addr_clean = f"{dong}{bon}" + (f"-{bu}" if bu and bu != "0" else "")
            addr_clean = addr_clean.replace(" ", "")
            
            if today_shift in str(r[23]): continue 
            if "연락처 없음" in str(r[11]) or not str(r[11]).strip(): continue
            
            full_addr_for_mgr = f"{r[0]} {r[1]} {r[2]} {r[3]}" + (f"-{r[4]}" if r[4] and str(r[4]) != "0" else "")
            if str(r[5]): full_addr_for_mgr += f" {r[5]}"
            mgr_name = next((m for b, m in MANAGER_BUILDINGS.items() if f" {b} " in f" {full_addr_for_mgr} "), None)
            if mgr_name and mgr_name != user_name and user_email != ADMIN_EMAIL: continue

            is_target = False
            for ta in target_addresses:
                if ta == addr_clean: 
                    is_target = True
                    break
                    
            if is_target: target_pool.append(r)
            
        target_pool.sort(key=lambda x: str(x[23])) 

        staff_names = sorted([r['이름'] for r in staff_records])
        my_idx = staff_names.index(user_name) if user_name in staff_names else 0
            
        start_idx = (my_idx * 5)
        end_idx = start_idx + (5 - quota_done) 
        my_assigned_pool = target_pool[start_idx:end_idx]
        
        if not my_assigned_pool:
            st.success("🎉 오늘 배정된 타겟 오피스텔 명단이 모두 소진되었습니다! (대표님께 새 타겟을 요청하세요)")
        else:
            for idx, row in enumerate(my_assigned_pool):
                city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, reg_date, registrar, status, row_idx = row
                
                addr_str = f"{city} {gu} {dong} {bon}" + (f"-{bu}" if bu and bu != "0" else "")
                if bldg: addr_str += f" {bldg}"
                room_str = f"{d_dong} {room}" if d_dong and d_dong != "동없음" else f"{room}"
                
                st.markdown(f"**🎯 타겟: {addr_str} {room_str}** (마지막 연락: {reg_date[:10]})")
                st.info(f"**소유주:** {name}({birth}) | **연락처:** {phone}\n\n**기존 보증/월세:** {deposit}/{rent} | **기존 만기:** {end_date}\n\n**히스토리:**\n{memo}")
                
                c_pass, c_space = st.columns([1, 4])
                if c_pass.button("⏭️ 부재중/패스 (토큰+0)", key=f"pass_{row_idx}"):
                    now_str = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')
                    ws_data.update_cell(row_idx, 24, now_str) 
                    ws_data.update_cell(row_idx, 25, user_name) 
                    
                    if user_email != ADMIN_EMAIL:
                        ws_staff.update_cell(staff_row_index, 8, quota_done + 1)
                    st.cache_data.clear()
                    st.rerun()
                    
                if render_edit_form(row_idx, city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, addr_str, room_str, f"task_upd_{idx}", "오피콜 갱신 완료", 1):
                    if user_email != ADMIN_EMAIL:
                        ws_staff.update_cell(staff_row_index, 8, quota_done + 1)
                    st.cache_data.clear()
                    st.rerun()
                st.write("---")

# --- [탭 4] 신규 등록 ---
with t_new:
    st.subheader("📝 신규 등록 (완료 시 +3 토큰 / +5점)")
    
    c_reg1, c_reg2, c_reg3 = st.columns([1, 1, 1])
    reg_sido_opts = list(KOREA_REGION_DATA.keys())
    reg_sido = c_reg1.selectbox("시/도", reg_sido_opts, index=reg_sido_opts.index("서울특별시") if "서울특별시" in reg_sido_opts else 0)
    reg_gu_opts = list(KOREA_REGION_DATA[reg_sido].keys())
    reg_gu = c_reg2.selectbox("시/군/구", reg_gu_opts, index=reg_gu_opts.index("송파구") if "송파구" in reg_gu_opts else 0)
    reg_dong_opts = KOREA_REGION_DATA[reg_sido][reg_gu] + ["➕직접 입력(신규지역)"]
    reg_dong_sel = c_reg3.selectbox("법정동", reg_dong_opts, index=reg_dong_opts.index("방이동") if "방이동" in reg_dong_opts else 0)
    
    with st.form("reg_form", clear_on_submit=True):
        if reg_dong_sel == "➕직접 입력(신규지역)":
            f_dong = st.text_input("법정동 직접 입력 (필수)", placeholder="예: 연남동")
        else: f_dong = reg_dong_sel

        r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
        f_bunji = r1_c1.text_input("번지 (필수)", placeholder="28-2")
        f_sub_dong = r1_c2.text_input("번지 뒤 '동' (없으면 0)", value="0")
        f_room = r1_c3.text_input("호실 (숫자만)", placeholder="101")
        
        f_btype = r1_c4.selectbox("용도 (필수)", ["아파트", "오피스텔", "다세대", "다가구", "빌라", "상가"])
        
        r2_c1, r2_c2, r2_c3 = st.columns(3)
        f_name = r2_c1.text_input("임대인 성함 (필수)")
        f_birth = r2_c2.text_input("생년월일 (숫자만)", placeholder="940101")
        f_phone = r2_c3.text_input("연락처 (숫자만)", placeholder="01012345678")
        
        r3_c1, r3_c2, r3_c3 = st.columns(3)
        f_deposit = r3_c1.text_input("보증금 (0원 단위. 예: 10000000)")
        f_rent = r3_c2.text_input("월세 (0원 단위)")
        f_end = r3_c3.text_input("만기일 (필수 YYYY.MM.DD)", placeholder="2026.04.00")
        
        f_memo = st.text_area("특이사항", placeholder="예: 애완가능, 주차가능 등")
        
        if st.form_submit_button("💾 데이터 등록", type="primary", use_container_width=True):
            if not f_dong or not f_bunji or not f_name or not f_room or not f_birth or not f_phone or not f_end:
                st.error("🚨 필수 항목을 모두 입력해주세요.")
            elif not is_valid_date_format(f_end):
                st.error("🚨 만기일 포맷을 지켜주세요. (예: 2026.04.00)")
            else:
                if "-" in f_bunji: bon, bu = f_bunji.split("-", 1)
                else: bon, bu = f_bunji, "0"
                
                d_dong = "동없음" if f_sub_dong == "0" else (f"{f_sub_dong}동" if not f_sub_dong.endswith("동") else f_sub_dong)
                r_ho = f"{f_room}호" if not f_room.endswith("호") else f_room
                
                is_blocked = False
                accumulated_memo = ""
                
                for r in all_records:
                    city, gu, dong, r_bon, r_bu, road, bldg, r_ddong, r_room, r_name, r_birth, r_phone, r_btype, r_appr, r_viol, r_land, r_rooma, r_biz, r_dep, r_rent, r_fee, r_end, r_memo, r_reg, registrar, r_status, row_idx = r
                    
                    if dong == f_dong and str(r_bon) == str(bon) and str(r_bu) == str(bu) and r_ddong == d_dong and r_room == r_ho and r_status != "잘못됨":
                        
                        if f_btype in ["아파트", "오피스텔"] or r_btype in ["아파트", "오피스텔"]:
                            is_blocked = True
                            break
                        
                        if not accumulated_memo and r_memo:
                            accumulated_memo = str(r_memo)
                
                if is_blocked:
                    st.error("🚨 이미 등록된 아파트/오피스텔입니다. [🔍 매물 검색] 탭에서 정보를 갱신해주세요.")
                else:
                    now_kst_dt = datetime.utcnow() + timedelta(hours=9)
                    now_str = now_kst_dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    final_memo = f_memo
                    if accumulated_memo:
                        final_memo = f"{final_memo}\n------------------\n👉 [과거 히스토리]\n{accumulated_memo}".strip()

                    new_row = [
                        reg_sido, reg_gu, f_dong, bon, bu, 
                        "", "", d_dong, r_ho, f_name, f_birth, format_phone(f_phone), 
                        f_btype, "", "위반 없음", "", "", "", 
                        f_deposit, f_rent, "", f_end, final_memo, now_str, user_name, "정상"
                    ]
                    ws_data.append_row(new_row, value_input_option='USER_ENTERED')
                    
                    update_token(user_name, 3, f"신규 등록 ({f_dong} {bon}-{bu} {r_ho}) [{f_btype}]")
                    st.cache_data.clear() 
                    st.success("✅ 신규 매물 등록 완료! 토큰 +3개 자동 지급!")
                    st.rerun()

# --- [탭 5] VIP ---
if t_vip:
    with t_vip:
        st.subheader("⏰ 3개월 이내 만기 알짜 매물 (VIP 전용)")
        st.write("향후 3개월 이내에 만기가 도래하는 매물 리스트입니다. (열람 시 토큰 -1)")
        
        now = datetime.now()
        three_months_later = now + timedelta(days=90)
        
        vip_res = []
        for r in all_records:
            e_date_str = str(r[21]).strip()
            if is_valid_date_format(e_date_str):
                clean_date_str = e_date_str.replace(".00", ".01").replace(".", "-")
                try:
                    e_date = datetime.strptime(clean_date_str, "%Y-%m-%d")
                    if now <= e_date <= three_months_later:
                        vip_res.append(r)
                except: pass
                
        vip_res.sort(key=lambda x: x[21])
        st.caption(f"조회된 알짜 매물: {len(vip_res)}건")
        
        for idx, row in enumerate(vip_res):
            city, gu, dong, bon, bu, road, bldg, d_dong, room, name, birth, phone, b_type, appr_date, viol, land_area, room_area, curr_biz, deposit, rent, fee, end_date, memo, reg_date, registrar, status, row_idx = row
            
            addr_str = f"{city} {gu} {dong} {bon}" + (f"-{bu}" if bu and bu != "0" else "")
            room_str = f"{d_dong} {room}" if d_dong and d_dong != "동없음" else f"{room}"
            
            st.markdown(f"**🔥 [만기: {end_date}] {addr_str} {room_str}**")
            
            unlock_key = f"unlock_vip_{addr_str}_{room_str}"
            toggle_key = f"toggle_vip_{idx}"
            is_unlocked = is_unlocked_recently(addr_str, room_str) or st.session_state.get(unlock_key, False)
            
            if is_unlocked:
                if st.button("🔓 재열람가능", key=f"btn_re_vip_{idx}"):
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                if st.session_state.get(toggle_key, False):
                    st.info(f"**용도:** {b_type}\n\n**소유주:** {name}({birth}) | **연락처:** {phone}\n\n**보증/월세:** {deposit}/{rent}\n\n**특이사항/히스토리:**\n{memo}")
            else:
                if st.button("🔓 상세정보 열람 (토큰 1개)", key=f"btn_vip_{idx}"):
                    if user_tokens >= 1 or user_email == ADMIN_EMAIL:
                        update_token(user_name, -1, f"VIP 매물 열람 ({addr_str} {room_str})")
                        st.session_state[unlock_key] = True
                        st.session_state[toggle_key] = True 
                        st.cache_data.clear() 
                        st.rerun()
                    else: st.error("토큰이 부족합니다.")
            st.write("---")
