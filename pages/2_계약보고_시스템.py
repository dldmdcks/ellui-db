import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import json
import re
import requests

# 🚨 [보안 방어막] 로그인 안 한 유저는 로비로 쫓아내기
if "connected" not in st.session_state or not st.session_state.connected:
    st.switch_page("app.py")

st.set_page_config(page_title="계약 보고 시스템", page_icon="📝", layout="wide")

# --- 💡 대한민국 표준 행정구역 DB (전국 풀버전!) ---
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

# --- 💡 날짜 포맷 검증 함수 (YYYY.MM.DD) ---
def is_valid_date_format(date_str):
    return bool(re.match(r'^\d{4}\.\d{2}\.\d{2}$', str(date_str).strip()))

# --- 💡 DB 연결 및 시트 세팅 ---
try:
    token_dict = json.loads(st.secrets["google_token_json"])
except Exception:
    st.error("❌ 금고 설정(Secrets)을 확인해주세요.")
    st.stop()

@st.cache_resource
def get_ss():
    creds = Credentials.from_authorized_user_info(token_dict)
    return gspread.authorize(creds).open_by_key('121-C5OIQpOnTtDbgSLgiq_Qdf5WoHhhIpNkRCWy5hKA')

ss = get_ss()

# 직원 이름 세팅
try:
    ws_staff = ss.worksheet("직원명단")
    staff_records = ws_staff.get_all_records()
    staff_dict = {str(row['이메일']).strip(): row['이름'] for row in staff_records}
except:
    staff_dict = {}

ADMIN_EMAIL = "dldmdcks94@gmail.com"
user_email = st.session_state.user_info.get("email", "")
user_name = "이응찬 대표" if user_email == ADMIN_EMAIL else staff_dict.get(user_email, "알수없는 직원")

# 💡 메인 DB 연동을 위해 컬럼을 완벽히 쪼갠 새로운 시트 생성
try: 
    ws_contract = ss.worksheet("계약보고_DB")
except: 
    ws_contract = ss.add_worksheet(title="계약보고_DB", rows="100", cols="19")
    ws_contract.append_row([
        "보고일시", "담당직원", "구분", 
        "시도", "시군구", "법정동", "본번", "부번", "동", "호수", 
        "보증금", "월세", "입주일", "만기일", "계약일", 
        "임대인명", "생년월일", "연락처", "특이사항"
    ])

# --- 📝 UI: 계약 보고 폼 ---
st.title("📝 엘루이 신규 계약 보고")
st.write("계약 내용을 입력하면 메인 DB와 동일한 규격으로 자동 분류되어 저장됩니다.")

today_str = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y.%m.%d')

with st.form("contract_report_form", clear_on_submit=False):
    st.subheader("📌 계약 기본 정보")
    
    deal_type = st.radio("연결 구분", ["양타", "단타"], horizontal=True)
    
    st.markdown("📍 **주소 입력**")
    c_loc1, c_loc2, c_loc3 = st.columns(3)
    sido_opts = list(KOREA_REGION_DATA.keys())
    sido = c_loc1.selectbox("시/도", sido_opts, index=0)
    
    gu_opts = list(KOREA_REGION_DATA[sido].keys()) if sido in KOREA_REGION_DATA else ["전체"]
    gu = c_loc2.selectbox("시/군/구", gu_opts, index=gu_opts.index("송파구") if "송파구" in gu_opts else 0)
    
    dong_opts = KOREA_REGION_DATA[sido][gu] if gu in KOREA_REGION_DATA[sido] else ["직접입력"]
    dong = c_loc3.selectbox("법정동", dong_opts + ["➕직접 입력"], index=dong_opts.index("방이동") if "방이동" in dong_opts else 0)
    if dong == "➕직접 입력": dong = st.text_input("법정동 직접 입력")

    c_loc4, c_loc5, c_loc6 = st.columns([2, 1, 2])
    bunji = c_loc4.text_input("번지 (예: 28-2)", placeholder="28-2")
    sub_dong = c_loc5.text_input("동 (없으면 빈칸)", placeholder="A동")
    room = c_loc6.text_input("호수 (숫자만)", placeholder="205")

    st.write("---")
    st.markdown("💰 **금액 및 기간**")
    c_mon1, c_mon2 = st.columns(2)
    deposit = c_mon1.text_input("보증금 (원 단위 숫자만)", placeholder="10000000")
    rent = c_mon2.text_input("월세 (원 단위 숫자만, 없으면 0)", placeholder="1000000")
    
    c_date1, c_date2, c_date3 = st.columns(3)
    contract_date = c_date1.text_input("✍️ 계약일 (자동입력)", value=today_str, disabled=True)
    move_in = c_date2.text_input("🗓️ 입주일 (YYYY.MM.DD)", placeholder="2026.04.10")
    move_out = c_date3.text_input("🗓️ 퇴실일 (YYYY.MM.DD)", placeholder="2028.04.09")
    
    st.write("---")
    st.subheader("👤 임대인 정보")
    c_info1, c_info2, c_info3 = st.columns(3)
    landlord_name = c_info1.text_input("성함", placeholder="이응찬")
    landlord_birth = c_info2.text_input("생년월일 (6자리 숫자만)", placeholder="941022")
    
    phone_ph = "임차측일 시 024214988 입력" if deal_type == "단타" else "01012345678"
    landlord_phone = c_info3.text_input("연락처 (숫자만 9~11자리)", placeholder=phone_ph)
    
    memo_ph = "예: ㅇㅇㅇ부동산 공동중개" if deal_type == "단타" else "기타 특이사항 입력"
    memo = st.text_area("📋 비고 및 특별사항", placeholder=memo_ph)
    
    submitted = st.form_submit_button("🚀 계약 결재 올리기 (데이터 저장)", type="primary", use_container_width=True)
    
    if submitted:
        # 유효성 검사 모음
        if not deposit.isdigit() or not rent.isdigit():
            st.error("🚨 보증금과 월세는 '원'이나 콤마(,) 없이 오직 숫자만 입력해주세요!")
        elif deposit != "0" and not deposit.endswith("0000"):
            st.error("🚨 보증금 입력이 잘못되었습니다. (끝자리가 0000으로 끝나야 합니다.)")
        elif any(char.isdigit() for char in landlord_name):
            st.error("🚨 임대인 성함에는 숫자를 포함할 수 없습니다.")
        elif not landlord_birth.isdigit() or len(landlord_birth) != 6:
            st.error("🚨 생년월일은 6자리의 숫자만 입력해주세요. (예: 941022)")
        elif not landlord_phone.isdigit() or not (9 <= len(landlord_phone) <= 11):
            st.error("🚨 연락처는 9~11자리의 숫자만 입력해주세요. (하이픈 - 제외)")
        elif not is_valid_date_format(move_in) or not is_valid_date_format(move_out):
            st.error("🚨 입주일과 퇴실일은 반드시 'YYYY.MM.DD' 포맷(예: 2026.04.00)으로 입력해주세요!")
        elif not bunji or not room or not landlord_name or not move_in or not move_out:
            st.error("🚨 번지, 호수, 입주/퇴실일, 임대인 성함은 필수 입력 사항입니다!")
        else:
            if "-" in bunji:
                bon, bu = bunji.split("-", 1)
            else:
                bon, bu = bunji, "0"
                
            d_dong = "동없음" if not sub_dong else (f"{sub_dong}동" if not sub_dong.endswith("동") else sub_dong)
            r_ho = f"{room}호" if not room.endswith("호") else room
                
            now_kst = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')
            
            safe_birth = f"'{landlord_birth}"
            safe_phone = f"'{landlord_phone}"
            
            # 1️⃣ 구글 시트에 저장
            new_row = [
                now_kst, user_name, deal_type, 
                sido, gu, dong, bon, bu, d_dong, r_ho, 
                deposit, rent, move_in, move_out, contract_date, 
                landlord_name, safe_birth, safe_phone, memo
            ]
            ws_contract.append_row(new_row, value_input_option='USER_ENTERED')
            
            # 2️⃣ 카카오워크 봇 알림 발송 🚀
            try:
                webhook_url = "https://kakaowork.com/bots/hook/4a5be71f2c424dfa8a6926ddfbd75ebe"
                
                # 금액 콤마 처리
                formatted_deposit = f"{int(deposit):,}" if deposit.isdigit() else deposit
                formatted_rent = f"{int(rent):,}" if rent.isdigit() else rent
                
                # 💡 [핵심 패치] 주소의 '동' 표시 로직 추가 (비어있으면 안 붙이고, 있으면 '동' 붙이기)
                display_sub_dong = ""
                if sub_dong:
                    display_sub_dong = f" {sub_dong}동" if not sub_dong.endswith("동") else f" {sub_dong}"
                
                # 💡 [핵심 패치] 단톡방 양식 완벽하게 대표님 요청대로 수정!
                msg_text = f"""{deal_type} {user_name}
-주소 : {dong} {bunji}번지{display_sub_dong} {r_ho}
-보증금 : {formatted_deposit}원
-월세 : {formatted_rent}원
-잔금 : {move_in}
-만기 : {move_out}
{memo}"""

                payload = {"text": msg_text}
                res = requests.post(webhook_url, json=payload)
                
                if res.status_code == 200:
                    st.success("🎉 시트 저장 및 카카오워크 단톡방 보고가 완벽하게 완료되었습니다!")
                    st.balloons()
                else:
                    st.warning("⚠️ 시트에는 저장되었으나, 카카오워크 발송에 실패했습니다.")
            except Exception as e:
                st.error(f"⚠️ 카카오워크 연동 에러가 발생했습니다: {e}")
