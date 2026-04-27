import streamlit as st

st.title("📞 Sales Call Debrief Agent")

uploaded_file = st.file_uploader(
    "Upload a sales call transcript",
    type=["txt", "pdf", "docx"]
)

if uploaded_file:
    if st.button("Analyze Call"):
        with st.spinner("Processing transcript..."):
            st.write("Transcript uploaded successfully!")
else:
    st.write("Waiting for file upload...")