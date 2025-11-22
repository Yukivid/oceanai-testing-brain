import streamlit as st
import requests
import json

BACKEND = "http://localhost:8000"

st.set_page_config(
    page_title="🧠 Testing Brain – Checkout QA Assistant",
    layout="wide",
    page_icon="🧠",
)

st.markdown("""
<style>
.main {
    background-color: #f7f9fc;
}
.upload-box {
    border: 2px dashed #7d8aff;
    padding: 20px;
    border-radius: 12px;
    background: #eef0ff;
}
.section-title {
    font-size: 26px;
    font-weight: 700;
    margin-bottom: 10px;
    color: #3949ab;
}
.subtext {
    font-size: 15px;
    color: #555;
}
.test-box {
    padding: 15px;
    background: white;
    border-radius: 10px;
    border-left: 5px solid #5e6bff;
    margin-bottom: 15px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='section-title'>🧠 Testing Brain – Intelligent QA Agent</h1>", unsafe_allow_html=True)
st.write("Upload documentation ➝ Build Knowledge Base ➝ Generate Test Cases ➝ Generate Selenium Scripts")

st.markdown("---")

st.markdown("<h2 class='section-title'>📘 Phase 1 – Build Knowledge Base</h2>", unsafe_allow_html=True)
st.markdown("<p class='subtext'>Upload Product Specs, UI/UX docs, JSON configs and checkout.html page.</p>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("<div class='upload-box'>", unsafe_allow_html=True)
    docs = st.file_uploader(
        "📄 Upload documentation files (PDF, TXT, MD, JSON, HTML)",
        accept_multiple_files=True,
        type=["pdf", "txt", "md", "json", "html"]
    )
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='upload-box'>", unsafe_allow_html=True)
    checkout_html = st.file_uploader(
        "🛒 Upload checkout.html",
        type=["html"]
    )
    st.markdown("</div>", unsafe_allow_html=True)

center = st.columns([3, 1, 3])[1]
with center:
    if st.button("🚀 Build Knowledge Base", use_container_width=True):
        if not docs:
            st.error("Please upload documents first.")
        else:
            files = [("files", (f.name, f.read(), f.type)) for f in docs]
            resp = requests.post(f"{BACKEND}/build_kb", files=files)

            if resp.ok:
                st.success("📚 Knowledge Base built successfully!")
            else:
                st.error("❌ Error building KB: " + resp.text)

st.markdown("---")

st.markdown("<h2 class='section-title'>🧪 Phase 2 – Generate Grounded Test Cases</h2>", unsafe_allow_html=True)
st.markdown("<p class='subtext'>AI generates fully grounded positive and negative test cases based on your docs.</p>", unsafe_allow_html=True)

prompt = st.text_area(
    "💡 Enter your request (example: *Generate test cases for the discount code feature*)",
    height=120,
    placeholder="Type your test generation prompt here..."
)

top_k = st.slider("🔍 Number of context chunks to retrieve", min_value=3, max_value=20, value=8)

if st.button("✨ Generate Test Cases", use_container_width=True):
    if not prompt:
        st.error("Enter a prompt first!")
    else:
        data = {"user_prompt": prompt, "top_k": str(top_k)}
        resp = requests.post(f"{BACKEND}/generate_tests", data=data)

        if resp.ok:
            result = resp.json()
            raw = result.get("llm", "")
            error = result.get("error", "")
            parsed_data = result.get("parsed", None)
            
            is_quota_error = (
                "quota" in raw.lower() or "429" in raw or "quota exceeded" in raw.lower() or
                "quota" in error.lower() or "429" in error or "quota exceeded" in error.lower()
            )
            
            if error or is_quota_error:
                if is_quota_error:
                    st.error("❌ **Quota Exceeded**: Your Gemini API free tier quota has been exceeded.")
                    st.info("💡 **Solutions:**\n"
                           "- Wait a few minutes and try again (free tier has rate limits)\n"
                           "- Check your API usage at: https://ai.dev/usage\n"
                           "- Consider upgrading your API plan if you need higher limits\n"
                           "- Try reducing the number of context chunks (use slider above)")
                    if raw:
                        with st.expander("🔍 Technical Details"):
                            st.code(raw, language="text")
                else:
                    st.error(f"❌ {error}")
                    if raw:
                        st.warning("⚠️ Raw LLM output:")
                        st.code(raw, language="json")
            elif parsed_data:
                st.session_state["generated_tests"] = parsed_data
                st.success(f"✅ Generated {len(parsed_data)} test cases")
            else:
                try:
                    tests = json.loads(raw)
                    st.session_state["generated_tests"] = tests
                    st.success(f"✅ Generated {len(tests)} test cases")
                except:
                    st.warning("⚠️ Could not parse JSON. Showing raw LLM output:")
                    st.code(raw, language="json")
        else:
            st.error("❌ Backend Error: " + resp.text)

if "generated_tests" in st.session_state and st.session_state["generated_tests"]:
    st.subheader("📦 Generated Test Cases")
    tests = st.session_state["generated_tests"]
    
    for idx, t in enumerate(tests):
        st.markdown(f"<div class='test-box'>", unsafe_allow_html=True)
        st.markdown(f"### 🧪 Test Case {idx+1}: {t.get('title','Untitled')}")
        st.write("**Scenario:**", t.get("scenario", ""))
        st.write("**Steps:**")
        steps = t.get("steps", [])
        if isinstance(steps, list):
            for step_idx, step in enumerate(steps, 1):
                st.write(f"{step_idx}. {step}")
        else:
            st.write(steps)
        st.write("**Expected:**", t.get("expected", ""))
        st.write("**Based On:**", t.get("based_on", "Unknown"))
        
        is_selected = False
        if "selected_test" in st.session_state:
            try:
                selected = json.loads(st.session_state["selected_test"])
                is_selected = selected.get("id") == t.get("id") or (
                    selected.get("title") == t.get("title") and 
                    selected.get("scenario") == t.get("scenario")
                )
            except:
                pass
        
        if is_selected:
            st.success("✅ **Currently Selected**")
        else:
            if st.button(f"Select Test Case {idx+1}", key=f"select_tc_{idx}"):
                st.session_state["selected_test"] = json.dumps(t)
                st.session_state["selected_test_index"] = idx
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

st.markdown("<h2 class='section-title'>🤖 Phase 3 – Generate Selenium Automation Script</h2>", unsafe_allow_html=True)
st.markdown("<p class='subtext'>Choose a generated test case and let the AI produce a runnable Selenium script.</p>", unsafe_allow_html=True)

if "selected_test" not in st.session_state:
    st.info("⚠️ Select a test case first (from Phase 2 above).")
else:
    try:
        selected_test = json.loads(st.session_state["selected_test"])
        st.subheader("📌 Selected Test Case")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**Title:** {selected_test.get('title', 'Untitled')}")
            st.markdown(f"**Scenario:** {selected_test.get('scenario', '')}")
            st.markdown(f"**Expected:** {selected_test.get('expected', '')}")
        with col2:
            if st.button("🔄 Change Selection", key="change_selection"):
                st.session_state.pop("selected_test", None)
                st.session_state.pop("selected_test_index", None)
                st.rerun()
        
        with st.expander("📋 View Full Test Case Details"):
            st.json(selected_test)
    except:
        st.error("⚠️ Invalid test case data. Please select a test case again.")
        st.session_state.pop("selected_test", None)

    final_html = st.file_uploader("📥 Upload checkout.html for Selenium script generation", type=["html"])
    
    if "generated_script" in st.session_state and st.session_state["generated_script"]:
        st.subheader("🧩 Generated Selenium Python Script")
        st.code(st.session_state["generated_script"], language="python")
        st.download_button(
            label="📥 Download Script",
            data=st.session_state["generated_script"],
            file_name="selenium_test.py",
            mime="text/x-python",
            key="download_script_main"
        )
        st.markdown("---")
    
    if st.button("🤖 Generate Selenium Script", use_container_width=True, key="generate_selenium_btn"):
        if not final_html:
            st.error("❌ Please upload checkout.html file!")
        elif "selected_test" not in st.session_state:
            st.error("❌ Please select a test case first!")
        else:
            with st.spinner("🤖 Generating Selenium script... This may take a moment."):
                try:
                    # Reset file pointer
                    final_html.seek(0)
                    files = {"checkout_html": (final_html.name, final_html.read(), final_html.type)}
                    data = {"test_case_json": st.session_state["selected_test"]}

                    resp = requests.post(f"{BACKEND}/generate_selenium", data=data, files=files)
                    
                    if resp.ok:
                        result = resp.json()
                        script = result.get("selenium_script", "")
                        
                        if script.startswith("GEMINI ERROR"):
                            st.error(f"❌ {script}")
                        else:
                            st.session_state["generated_script"] = script
                            st.success("✅ Selenium script generated successfully!")
                            st.rerun()  # Rerun to show the script in the section above
                    else:
                        st.error(f"❌ Error generating script: {resp.text}")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
