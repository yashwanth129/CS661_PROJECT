import streamlit as st

st.title("Main App")

st.markdown("""
    <style>
        .full-iframe {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            border: none;
            z-index: 9999;
        }
    </style>
    <iframe src="http://localhost:5000" class="full-iframe"></iframe>
""", unsafe_allow_html=True)
