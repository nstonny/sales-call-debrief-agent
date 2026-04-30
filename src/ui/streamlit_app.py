import streamlit as st
import requests

API_URL = "http://localhost:8000/api/upload"

st.title("📞 Sales Call Debrief Agent")

uploaded_file = st.file_uploader(
    "Upload a sales call transcript (.txt)",
    type=["txt"],
)

if not uploaded_file:
    st.info("Waiting for file upload...")

company = st.text_input("Company name (optional)")
deal_value = st.number_input(
    "Deal value in € (optional)",
    min_value=0.0,
    value=None,
    placeholder="e.g. 25000",
    format="%.2f",
)

if uploaded_file:
    if st.button("Analyze Call"):
        with st.spinner("Uploading transcript..."):
            form_data = {}
            if company:
                form_data["company"] = company
            if deal_value:
                form_data["deal_value"] = deal_value

            response = requests.post(
                API_URL,
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/plain")},
                data=form_data,
            )

        if response.status_code == 200:
            result = response.json()
            st.success("✅ Transcript uploaded successfully!")
            st.json(result)
        else:
            st.error(f"❌ Upload failed ({response.status_code}): {response.json().get('detail', 'Unknown error')}")
