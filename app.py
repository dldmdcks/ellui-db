import streamlit as st
import os
import json
import requests

# 🚨 1. 기본 메뉴 숨기기 및 기본 설정 (마법의 망토!)
st.set_page_config(page_title="엘루이 업무포털 홈", page_icon="🏢", layout="wide")
st.markdown("""
    <style>
        /* 스트림릿이 자동으로 만드는 왼쪽 파일 리스트 메뉴를 아예 숨겨버립니다! */
        [data-testid="stSidebarNav"] {display: none;}
        html, body, [class*="css"]  { font-size: 14px !important; }
        .stButton>button { padding: 0.2rem 0.5rem; min-height: 2rem; }
    </style>
""", unsafe_allow_html=True)

ADMIN_EMAIL = "dldmdcks94@gmail.com"

# --- 2. 로그인 시스템 (기존과 동일) ---
try:
    creds_dict = json.loads(st.secrets["credentials_json"])
    token_dict = json.loads(st.secrets["google_token_json"])
    CLIENT_ID = creds_dict["web"]["client_id"]
    CLIENT_SECRET = creds_dict["web"]["client_secret"]
    REDIRECT_URI = creds_dict["web"]["redirect_uris"][0]
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

# --- 3. 로그인 성공 시: 맞춤형 메뉴판 & 홈 화면 보여주기 ---
user_email = st.session_state.user_info.get("email", "")

# 🎯 [핵심] 사이드바 맞춤형 메뉴판 그리기
st.sidebar.subheader("🏢 엘루이 메뉴")

# 누구나 볼 수 있는 공통 메뉴
st.sidebar.page_link("app.py", label="🏠 메인 로비 (홈)", icon="🏠")
st.sidebar.page_link("pages/1_오피콜_및_매물관리.py", label="💼 오피콜 & 매물관리", icon="💼")

# 대표님에게만 보이는 비밀 메뉴 (나중에 2, 3번 방 만들면 여기에 추가됩니다!)
if user_email == ADMIN_EMAIL:
    st.sidebar.write("---")
    st.sidebar.caption("👑 대표님 전용 공간")
    # st.sidebar.page_link("pages/2_관리자_대시보드.py", label="👑 관리자 대시보드", icon="👑")
    # st.sidebar.page_link("pages/3_계약보고_시스템.py", label="🚀 계약/등기 컨펌", icon="🚀")

st.sidebar.write("---")
if st.sidebar.button("로그아웃"):
    st.query_params.clear()
    st.session_state.clear()
    st.rerun()


# 🏠 홈 화면 콘텐츠 (기존 앱의 홈 화면 부분)
st.subheader("🏠 엘루이 업무 포털")
st.info("📢 **[전체 공지사항]**\n\n대출상담사 은행명 / 성함/직책/연락처 알려주시면 아래에 추가해두겠습니다. 2026.03.24")

st.write("---")
st.markdown("#### 🔗 엘루이 내부 업무망")
c_in1, c_in2, c_in3 = st.columns(3)
c_in1.link_button("📊 오피콜 시트", "https://docs.google.com/spreadsheets/d/11WZhFnPPIduKVSy3UG0-L1BrXRdddCBhzQLZGMVBSXc/edit?gid=1257534628#gid=1257534628", use_container_width=True)

st.write("---")
st.markdown("#### 🌐 부동산 필수 사이트")
c1, c2, c3 = st.columns(3)
c1.link_button("🌐 정부24 (건축물대장)", "https://www.gov.kr/portal/main", use_container_width=True)
c2.link_button("📜 인터넷 등기소", "http://www.iros.go.kr/", use_container_width=True)
c3.link_button("📈 공실클럽", "https://www.gongsilclub.com/", use_container_width=True)

c4, c5, c6 = st.columns(3)
c4.link_button("🗺️ 씨리얼 (부동산정보)", "https://seereal.lh.or.kr/", use_container_width=True)
c5.link_button("🔥 도시가스 (코원에너지)", "https://www.skens.com/koone/main/index.do#", use_container_width=True)
c6.link_button("⚖️ 법제처 (국가법령)", "https://www.law.go.kr/LSW/main.html", use_container_width=True)

c7, c8, c9 = st.columns(3)
c7.link_button("📍 밸류맵", "https://www.valueupmap.com/", use_container_width=True)
c8.link_button("🏦 KB부동산", "https://kbland.kr/map?xy=37.5151144,127.1133079,17", use_container_width=True)
c9.link_button("📊 부동산테크", "https://rtech.or.kr/land/landMap.do", use_container_width=True)

c10, c11, c12 = st.columns(3)
c10.link_button("🏠 렌트홈", "https://www.renthome.go.kr/webportal/main/portalMainList.open", use_container_width=True)
c11.link_button("🧮 부동산 계산기", "https://xn--989a00af8jnslv3dba.com/", use_container_width=True)
c12.link_button("💰 홈택스 (기준시가)", "https://hometax.go.kr/websquare/websquare.html?w2xPath=/ui/pp/index_pp.xml&tmIdx=47&tm2lIdx=4712090000&tm3lIdx=4712090300", use_container_width=True)

c13, c14, c15 = st.columns(3)
c13.link_button("📢 공시가격 알리미", "https://www.realtyprice.kr/notice/main/main.do#", use_container_width=True)
c14.link_button("🛡️ HUG 보증보험 확인", "https://khig.khug.or.kr/websquare/popup.html?w2xPath=/cg/ae/CGAE034P02.xml&popupID=help&idx=idx10_16146745922339600.17851819347&w2xHome=/login/&w2xDocumentRoot=", use_container_width=True)
c15.link_button("🏗️ 세움터", "https://www.eais.go.kr/", use_container_width=True)

st.write("---")
st.markdown("#### 🤝 엘루이 제휴 및 협력 업체")
c_p1, c_p2 = st.columns(2)
with c_p1:
    st.markdown("""
    <div style='background-color:#f0f2f6; padding:15px; border-radius:10px;'>
    <b>🧹 청소 전문업체 [하루한집]</b><br>
    • <b>대표:</b> 노종혁<br>
    • <b>연락처:</b> 010-7675-6147 (입주/이사/특수/준공 청소 등)<br>
    • <b>계좌번호:</b> 카카오뱅크 3333-10-7916932 노종혁
    </div>
    """, unsafe_allow_html=True)
with c_p2:
    st.markdown("""
    <div style='background-color:#f0f2f6; padding:15px; border-radius:10px;'>
    <b>🛠️ 전속 수리업체 [집고 송파동점]</b><br>
    • <b>지점장:</b> 신재경<br>
    • <b>연락처:</b> 010-3964-8272 (검증된 기술, 확실한 AS)<br>
    • <b>계좌번호:</b> 카카오뱅크 3333-1709-93139 신재경
    </div>
    """, unsafe_allow_html=True)
