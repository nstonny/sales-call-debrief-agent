import os

import requests
import streamlit as st

# Overridable so the same code works in both topologies. Compose sets
# DEBRIEF_API_URL to http://api:8000/api, addressing the API by its
# service name -- inside the UI container, "localhost" is the UI container
# itself. The default preserves the native `uv run streamlit` workflow.
API_BASE_URL = os.getenv("DEBRIEF_API_URL", "http://localhost:8000/api")


def render_dashboard(result: dict) -> None:
    """Renders a structured debrief dashboard from the API response."""
    analysis = result.get("analysis") or {}

    st.divider()
    st.subheader("📋 Call Summary")

    # --- Call metadata row ---
    # st.metric() uses large font unsuitable for long names — use markdown labels instead
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("**Rep**")
        st.write(result.get("rep_name") or "—")
    with col2:
        st.markdown("**Contact**")
        contact = result.get("contact_name") or "—"
        title = result.get("contact_title") or ""
        st.write(f"{contact} ({title})" if title else contact)
    with col3:
        st.markdown("**Deal Stage**")
        st.write((result.get("deal_stage") or "—").capitalize())
    with col4:
        st.markdown("**Company**")
        st.write(result.get("company") or "—")

    # --- Score + sentiment row ---
    score = analysis.get("score")
    sentiment = (analysis.get("sentiment") or "").lower()
    deal_value = result.get("deal_value")

    col5, col6, col7 = st.columns(3)
    with col5:
        st.markdown("**🏆 Score**")
        st.write(f"{score:.1f} / 5" if score is not None else "—")
    with col6:
        st.markdown("**💬 Sentiment**")
        st.write(sentiment.capitalize() if sentiment else "—")
    with col7:
        st.markdown("**💶 Deal Value**")
        st.write(f"€{deal_value:,.0f}" if deal_value else "—")

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


@st.cache_data(ttl=30)
def fetch_transcript_list() -> list[str]:
    """Filenames of sample transcripts available server-side, via the API."""
    response = requests.get(f"{API_BASE_URL}/transcripts", timeout=10)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=30)
def fetch_transcript_content(filename: str) -> str:
    """Raw text of a sample transcript, via the API, for the preview panel."""
    response = requests.get(f"{API_BASE_URL}/transcripts/{filename}", timeout=10)
    response.raise_for_status()
    return response.json()["content"]


# --- Sidebar: transcript selection ---
with st.sidebar:
    st.header("📂 Select Transcript")

    selected_filename = None
    try:
        transcripts = fetch_transcript_list()
    except requests.exceptions.RequestException:
        st.error("❌ Could not reach the API. Is it running?")
        transcripts = []

    if not transcripts:
        st.info("No sample transcripts found.")
    else:
        selected_filename = st.selectbox("Choose a sales call transcript", options=transcripts)

    # Clear input fields when a different transcript is selected
    if "last_filename" not in st.session_state:
        st.session_state.last_filename = None

    if selected_filename and selected_filename != st.session_state.last_filename:
        st.session_state.last_filename = selected_filename
        st.session_state.company = ""
        st.session_state.deal_value = None

    if selected_filename:
        with st.expander("🔍 Preview transcript"):
            try:
                st.text(fetch_transcript_content(selected_filename))
            except requests.exceptions.RequestException:
                st.error("Could not load transcript preview.")

    company = st.text_input("Company name (optional)", key="company")
    deal_value = st.number_input(
        "Deal value in € (optional)",
        min_value=0.0,
        value=st.session_state.get("deal_value", None),
        placeholder="e.g. 25000",
        format="%.2f",
        key="deal_value",
    )

    analyse_clicked = st.button("Analyze Call", disabled=not selected_filename)


# --- Main area: title + results ---
st.title("📞 Sales Call Debrief Agent")

if analyse_clicked and selected_filename:
    with st.spinner("Analysing transcript..."):
        payload = {}
        if company:
            payload["company"] = company
        if deal_value:
            payload["deal_value"] = deal_value

        response = requests.post(
            f"{API_BASE_URL}/transcripts/{selected_filename}/analyze",
            json=payload,
        )

    if response.status_code == 200:
        result = response.json()
        st.success("✅ Transcript analysed successfully!")
        render_dashboard(result)
    else:
        try:
            detail = response.json().get("detail", "Unknown error")
        except Exception:
            detail = response.text or "Unknown error — server returned no response body"
        st.error(f"❌ Analysis failed ({response.status_code}): {detail}")
elif not selected_filename:
    st.markdown(
        """
        ### Welcome 👋
        Select a sales call transcript from the sidebar to get started.

        The agent will automatically:
        - Extract call metadata (rep, contact, deal stage)
        - Score the call and assess sentiment
        - Identify strengths, coaching points and action items
        - Flag objections and competitor mentions
        """
    )
