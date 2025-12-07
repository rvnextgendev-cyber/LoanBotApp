import os
import requests
import streamlit as st

API_URL = os.getenv("LOANBOT_API_URL", "http://localhost:8000")


def main():
    st.set_page_config(page_title="LoanBot", layout="wide")
    st.title("LoanBot - multi-turn intake")

    if "session_id" not in st.session_state:
        st.session_state.session_id = ""
    if "last_question" not in st.session_state:
        st.session_state.last_question = None
    if "prefetched" not in st.session_state:
        st.session_state.prefetched = False

    # Prefetch first assistant prompt so users see the starting question immediately.
    if not st.session_state.prefetched and not st.session_state.session_id:
        try:
            resp = requests.post(
                f"{API_URL}/chat/llm-next",
                json={"session_id": "", "user_reply": None},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            st.session_state.session_id = data["session_id"]
            st.session_state.last_question = data.get("next_question")
        except Exception as exc:
            st.session_state.last_question = f"Unable to fetch initial question: {exc}"
        finally:
            st.session_state.prefetched = True

    st.session_state.session_id = st.text_input(
        "Session ID (leave blank to start new)",
        value=st.session_state.session_id,
        placeholder="auto-generate on first send",
    )

    if st.session_state.last_question:
        st.info(f"Assistant: {st.session_state.last_question}")

    user_reply = st.text_area("Your message", height=120)
    if st.button("Send"):
        payload = {"session_id": st.session_state.session_id, "user_reply": user_reply}
        resp = requests.post(f"{API_URL}/chat/llm-next", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        st.session_state.session_id = data["session_id"]
        st.session_state.last_question = data.get("next_question") or "Done."
        st.write("**Assistant:**", st.session_state.last_question)
        st.write("**Collected:**", data.get("collected"))
        if data.get("completed"):
            st.success(f"Loan saved with id {data['loan']['id']}")
    st.divider()
    st.code(
        "Run FastAPI: uvicorn app.main:app --reload\nRun Streamlit: streamlit run streamlit_app/loan_ui.py",
        language="bash",
    )


if __name__ == "__main__":
    main()
