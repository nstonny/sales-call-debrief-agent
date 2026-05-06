import streamlit as st
import requests

API_URL = "http://localhost:8000/api/upload"


def render_dashboard(result: dict) -> None:
    """Renders a structured debrief dashboard from the API response."""
    analysis = result.get("analysis") or {}

    st.divider()
    st.subheader("📋 Call Summary")

    # --- Call metadata row ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rep", result.get("rep_name") or "—")
    col2.metric("Contact", f"{result.get('contact_name') or '—'} ({result.get('contact_title') or '—'})")
    col3.metric("Deal Stage", (result.get("deal_stage") or "—").capitalize())
    col4.metric("Company", result.get("company") or "—")

    # --- Score + sentiment row ---
    score = analysis.get("score")
    sentiment = (analysis.get("sentiment") or "").lower()
    deal_value = result.get("deal_value")

    col5, col6, col7 = st.columns(3)
    col5.metric("🏆 Score", f"{score:.1f} / 10" if score is not None else "—")
    col6.metric("💬 Sentiment", sentiment.capitalize() if sentiment else "—")
    col7.metric("💶 Deal Value", f"€{deal_value:,.0f}" if deal_value else "—")

    # --- Sentiment colour banner ---
    summary = analysis.get("summary")
    if summary:
        if sentiment == "positive":
            st.success(summary)
        elif sentiment == "negative":
            st.error(summary)
        else:
            st.info(summary)

    st.divider()

    # --- Three coaching columns ---
    col_s, col_a, col_act = st.columns(3)

    with col_s:
        st.markdown("### ✅ Strengths")
        for item in analysis.get("strengths") or []:
            st.markdown(f"- {item}")

    with col_a:
        st.markdown("### 🔧 Areas for Improvement")
        for item in analysis.get("areas_for_improvement") or []:
            st.markdown(f"- {item}")

    with col_act:
        st.markdown("### 📌 Action Items")
        for item in analysis.get("action_items") or []:
            st.markdown(f"- {item}")

    st.divider()

    # --- Objections + next steps row ---
    col_obj, col_next = st.columns(2)

    with col_obj:
        st.markdown("### 🚧 Objections Raised")
        objections = analysis.get("objections_raised") or []
        if objections:
            for item in objections:
                st.markdown(f"- {item}")
        else:
            st.markdown("_None raised_")

    with col_next:
        st.markdown("### 🔜 Next Steps")
        next_steps = analysis.get("next_steps")
        st.markdown(next_steps if next_steps else "_None agreed_")

    # --- Competitor + call ID footer ---
    competitor = analysis.get("competitor_mentioned")
    if competitor and competitor.lower() not in ("none", "null", "n/a"):
        st.warning(f"⚠️ Competitor mentioned: **{competitor}**")

    with st.expander("🔍 Raw response"):
        st.json(result)


st.title("📞 Sales Call Debrief Agent")

uploaded_file = st.file_uploader(
    "Upload a sales call transcript (.txt)",
    type=["txt"],
    accept_multiple_files=False,
)

# --- Clear input fields when a new file is uploaded ---
# session_state persists across Streamlit reruns. We compare the current
# filename to the last one we saw; if it changed, reset company and deal_value.
if "last_filename" not in st.session_state:
    st.session_state.last_filename = None

if uploaded_file and uploaded_file.name != st.session_state.last_filename:
    st.session_state.last_filename = uploaded_file.name
    st.session_state.company = ""
    st.session_state.deal_value = None

if not uploaded_file:
    st.info("Waiting for file upload...")

# key= links each widget to session_state so the reset above takes effect
company = st.text_input("Company name (optional)", key="company")
deal_value = st.number_input(
    "Deal value in € (optional)",
    min_value=0.0,
    value=st.session_state.get("deal_value", None),
    placeholder="e.g. 25000",
    format="%.2f",
    key="deal_value",
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
            st.success("✅ Transcript analysed successfully!")
            render_dashboard(result)
        else:
            st.error(f"❌ Upload failed ({response.status_code}): {response.json().get('detail', 'Unknown error')}")
