import streamlit as st

st.set_page_config(page_title="계약 보고 시스템", page_icon="📝", layout="wide")

st.title("📝 엘루이 신규 계약 보고 (테스트)")
st.write("이곳은 대표님이 구상하신 계약 보고 및 등기 컨펌 기능이 들어갈 2번 방입니다!")

# 테스트용 버튼
if st.button("계약서 결재 올리기"):
    st.success("대표님께 결재가 성공적으로 전송되었습니다! (테스트)")
