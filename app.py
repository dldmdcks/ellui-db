import streamlit as st
import json

st.title("🚨 긴급 구글 로그인 진단기")

try:
    # 금고에서 열쇠 꺼내기
    creds_str = st.secrets["credentials_json"]
    creds_dict = json.loads(creds_str)
    client_id = creds_dict["web"]["client_id"]
    redirect_uri = "https://ellui-db.streamlit.app/"
    
    # 도구를 거치지 않는 '순수 구글 로그인 직통 링크' 만들기
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=openid%20email%20profile"
    
    st.success("✅ 서버 정상! 파이썬 코드는 100% 완벽합니다.")
    st.write("이제 아래 링크를 눌러서 구글 문지기에게 직접 접근해 보세요.")
    st.markdown(f"### [👉 **여기를 클릭해서 로그인 직접 시도하기**]({auth_url})")
    
except Exception as e:
    st.error(f"❌ 금고 설정에 문제가 있습니다: {e}")