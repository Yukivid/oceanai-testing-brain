import os
import json
import re
import time
from typing import List
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from bs4 import BeautifulSoup
import fitz
import google.generativeai as genai
from chromadb import PersistentClient
import numpy as np

# ENV & CONFIG
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_KEY)

EMBED_MODEL = "all-MiniLM-L6-v2"
CHROMA_PATH = "chroma_db"
os.makedirs(CHROMA_PATH, exist_ok=True)


DEFAULT_MODELS = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro", "gemini-1.0-pro"]

def get_available_models():
    """Get list of available Gemini models, excluding experimental ones."""
    try:
        available = []
        excluded_keywords = ["exp", "experimental", "2.5", "2.0"]  
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                model_name = model.name.split('/')[-1]  
                if not any(keyword in model_name.lower() for keyword in excluded_keywords):
                    available.append(model_name)
        return available
    except Exception:
        return DEFAULT_MODELS  

try:
    available_models = get_available_models()
    if available_models:
        preferred = [m for m in DEFAULT_MODELS if m in available_models]
        if preferred:
            GEMINI_MODELS = preferred
        else:
            GEMINI_MODELS = [m for m in available_models if not any(kw in m.lower() for kw in ["exp", "experimental", "2.5", "2.0"])][:3]
    else:
        GEMINI_MODELS = DEFAULT_MODELS
except Exception:
    GEMINI_MODELS = DEFAULT_MODELS 

GEMINI_MODEL = GEMINI_MODELS[0]  

MAX_CONTEXT_CHARS_FIRST = 2000
MAX_CONTEXT_CHARS_RETRY = 1000
MAX_CONTEXT_CHARS_FINAL = 500
MAX_HTML_CHARS = 3000
MAX_LLM_TOKENS = 2000 

# INIT
client = PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection(name="docs", metadata={"hnsw:space": "cosine"})
embedder = SentenceTransformer(EMBED_MODEL)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Utilities
def read_pdf(raw: bytes) -> str:
    doc = fitz.open(stream=raw, filetype="pdf")
    texts = [p.get_text("text") for p in doc]
    return "\n".join(texts)

def chunk_text(text: str, size: int = 350, overlap: int = 80) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i+size]))
        i += size - overlap
    return chunks

def embed_texts(texts: List[str]) -> np.ndarray:
    emb = embedder.encode(texts, convert_to_numpy=True)
    return emb

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def extractive_summary(text: str, max_chars: int = 700, sentences_limit: int = 30) -> str:
    sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if s.strip()]
    if not sentences:
        return text[:max_chars]
    sentences = sentences[:sentences_limit]
    sent_embs = embed_texts(sentences)
    doc_emb = embed_texts([" ".join(sentences)])[0]
    sims = [cosine_sim(doc_emb, se) for se in sent_embs]
    ranked = sorted(zip(sims, sentences), key=lambda x: x[0], reverse=True)
    out = ""
    for sim, s in ranked:
        if len(out) + len(s) + 2 <= max_chars:
            out += (". " + s) if out else s
        else:
            break
    return out + ("..." if len(out) < len(text) else "")

# Gemini safe wrapper with model fallback and retry logic
def call_llm(prompt: str, max_tokens: int = MAX_LLM_TOKENS, max_retries: int = 3) -> str:
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    
    last_error = None
    for model_name in GEMINI_MODELS:
        for retry in range(max_retries):
            try:
                model = genai.GenerativeModel(model_name)
                
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.1,
                        top_p=0.95
                    ),
                    safety_settings=safety_settings
                )

                if getattr(response, "candidates", None) and len(response.candidates) > 0:
                    cand = response.candidates[0]
                    finish_reason = getattr(cand, "finish_reason", None)
                    
                    # Check for safety blocks
                    if finish_reason == 2:  # SAFETY
                        return "GEMINI ERROR: Safety filter blocked."
                    elif finish_reason == 3:  # RECITATION
                        return "GEMINI ERROR: Content recitation blocked."
                    elif finish_reason == 4:  # OTHER
                        return "GEMINI ERROR: Generation blocked for other reasons."
                    
                    if getattr(getattr(cand, "content", None), "parts", None):
                        text_out = ""
                        for part in cand.content.parts:
                            if hasattr(part, "text") and part.text:
                                text_out += part.text
                        if text_out.strip():
                            return text_out.strip()

                if hasattr(response, "text") and response.text:
                    return response.text.strip()

                return "GEMINI ERROR: Empty response from LLM."
                
            except Exception as e:
                error_msg = str(e)
                last_error = error_msg
                
                if "429" in error_msg or "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                    retry_delay = 5  
                    if "retry in" in error_msg.lower():
                        try:
                            import re
                            delay_match = re.search(r'retry in ([\d.]+)s', error_msg.lower())
                            if delay_match:
                                retry_delay = float(delay_match.group(1)) + 1  # Add 1 second buffer
                        except:
                            pass
                    
                    if retry < max_retries - 1:
                        wait_time = retry_delay * (2 ** retry)
                        time.sleep(min(wait_time, 60))  
                        continue  
                    else:
                        break
                
                if "404" in error_msg or "not found" in error_msg.lower() or "not supported" in error_msg.lower():
                    break  
                
                if "free_tier" in error_msg.lower() and "limit: 0" in error_msg.lower():
                    break  
                return f"GEMINI ERROR: {error_msg}"
    
    if "429" in str(last_error) or "quota" in str(last_error).lower():
        return f"GEMINI ERROR: Quota exceeded. Please wait a few minutes and try again, or check your API billing/quota settings. Last error: {last_error}"
    return f"GEMINI ERROR: All models failed. Last error: {last_error}"

# BUILD KB
@app.post("/build_kb")
async def build_kb(files: List[UploadFile] = File(...)):
    docs, ids, metas, embs = [], [], [], []
    for f in files:
        raw = await f.read()
        ext = f.filename.lower().split(".")[-1]
        if ext == "pdf":
            text = read_pdf(raw)
        elif ext in ("html", "htm"):
            text = raw.decode("utf-8", errors="ignore")
        elif ext == "json":
            try:
                text = json.dumps(json.loads(raw), indent=2)
            except:
                text = raw.decode("utf-8", errors="ignore")
        else:
            text = raw.decode("utf-8", errors="ignore")
        chunks = chunk_text(text)
        chunk_embs = embed_texts(chunks)
        for idx, (chunk, emb) in enumerate(zip(chunks, chunk_embs)):
            docs.append(chunk)
            embs.append(emb)
            ids.append(f"{f.filename}_chunk_{idx}")
            metas.append({"source_document": f.filename, "chunk_index": idx})
    collection.add(documents=docs, embeddings=[e.tolist() for e in embs], metadatas=metas, ids=ids)
    return {"status": "success", "stored_chunks": len(docs)}

# RETRIEVE helper
def retrieve_for_query(query: str, top_k: int = 3):
    q_emb = embed_texts([query])[0].tolist()
    results = collection.query(query_embeddings=[q_emb], n_results=top_k, include=["documents", "metadatas"])
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    return docs, metas

# GENERATE SCENARIOS (model-safe wording)
def extract_json_from_text(text: str) -> str:
    """Extract JSON from text, handling markdown code blocks."""
    text = text.strip()
    
    json_match = re.search(r'```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    
    json_match = re.search(r'(\[.*?\]|\{.*?\})', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    
    return text

@app.post("/generate_tests")
async def generate_tests(user_prompt: str = Form(...), top_k: int = Form(3)):
    top_k = min(max(1, int(top_k)), 8)

    docs, metas = retrieve_for_query(user_prompt, top_k=top_k)

    aggregated = ""
    for d, m in zip(docs, metas):
        aggregated += f"### Source: {m.get('source_document','unknown')}\n{d}\n\n"

    attempts = [
        {"max_chars": MAX_CONTEXT_CHARS_FIRST},
        {"max_chars": MAX_CONTEXT_CHARS_RETRY},
        {"max_chars": MAX_CONTEXT_CHARS_FINAL},
    ]

    last_error = None
    for attempt in attempts:
        ctx = aggregated[: attempt["max_chars"]]
        if len(ctx.strip()) < 20:
            ctx = extractive_summary(aggregated, max_chars=attempt["max_chars"])

        # SAFE prompt: clear and structured
        prompt = f"""You are a test case generator. Based on the reference documentation below, generate test cases as a JSON array.

Reference Documentation:
{ctx}

User Request: {user_prompt}

Generate a JSON array of test case objects. Each object must have these exact fields:
- "id": unique identifier (string)
- "title": brief test case title (string)
- "scenario": description of the scenario (string)
- "steps": array of step strings
- "expected": expected outcome (string)
- "based_on": source document reference (string)

Important:
- Generate both positive and negative test cases based on the user request
- Use only information from the reference documentation
- Return ONLY valid JSON array, no markdown, no explanations
- Ensure the JSON is properly formatted and parseable

Example format:
[
  {{
    "id": "TC001",
    "title": "Valid discount code application",
    "scenario": "User applies a valid discount code",
    "steps": ["Navigate to checkout", "Enter discount code", "Apply code"],
    "expected": "Discount is applied successfully",
    "based_on": "discount_policy.pdf"
  }}
]

Now generate the test cases:"""

        llm_out = call_llm(prompt, max_tokens=MAX_LLM_TOKENS)
        if llm_out.startswith("GEMINI ERROR"):
            last_error = llm_out
            if "quota" in llm_out.lower() or "429" in llm_out:
                break
            continue

        try:
            json_text = extract_json_from_text(llm_out)
            parsed = json.loads(json_text)
            if isinstance(parsed, list) and len(parsed) > 0:
                return {"llm": json.dumps(parsed, indent=2), "parsed": parsed, "parsed_count": len(parsed)}
            else:
                return {"llm": llm_out, "error": "JSON array is empty or invalid."}
        except json.JSONDecodeError as e:
            if attempt == attempts[-1]:
                return {"llm": llm_out, "error": f"Could not parse JSON: {str(e)}"}
            continue

    err_msg = last_error or "Unknown LLM failure"
    return {"llm": err_msg, "error": "All attempts failed. Try simplifying your request or reduce retrieval depth."}

# GENERATE SELENIUM (robust)
@app.post("/generate_selenium")
async def generate_selenium(test_case_json: str = Form(...), checkout_html: UploadFile = File(...)):
    try:
        raw_html = (await checkout_html.read()).decode("utf-8", errors="ignore")
        raw_html = raw_html[:MAX_HTML_CHARS]

        soup = BeautifulSoup(raw_html, "lxml")
        selectors = []
        seen_selectors = set()
        
        for tag in soup.find_all(True):
            if tag.get("id"):
                sel = f"#{tag.get('id')}"
                if sel not in seen_selectors:
                    selectors.append({
                        "selector": sel,
                        "type": "id",
                        "tag": tag.name,
                        "text": tag.get_text(strip=True)[:50] if tag.get_text(strip=True) else ""
                    })
                    seen_selectors.add(sel)
            
            if tag.get("name"):
                sel = f"[name='{tag.get('name')}']"
                if sel not in seen_selectors:
                    selectors.append({
                        "selector": sel,
                        "type": "name",
                        "tag": tag.name,
                        "text": tag.get_text(strip=True)[:50] if tag.get_text(strip=True) else ""
                    })
                    seen_selectors.add(sel)
            
            if tag.get("class"):
                for cls in tag.get("class"):
                    sel = f".{cls}"
                    if sel not in seen_selectors:
                        selectors.append({
                            "selector": sel,
                            "type": "class",
                            "tag": tag.name,
                            "text": tag.get_text(strip=True)[:50] if tag.get_text(strip=True) else ""
                        })
                        seen_selectors.add(sel)
        
        selectors = selectors[:150]

        try:
            docs, metas = retrieve_for_query(test_case_json, top_k=2)
            aggregated = ""
            for d, m in zip(docs, metas):
                aggregated += f"### Source: {m.get('source_document','unknown')}\n{d}\n\n"
            aggregated = aggregated[:2000]
        except Exception:
            aggregated = "No additional documentation available."

        try:
            test_case = json.loads(test_case_json)
            test_steps = test_case.get("steps", [])
            test_scenario = test_case.get("scenario", "")
            test_expected = test_case.get("expected", "")
        except:
            test_steps = []
            test_scenario = ""
            test_expected = ""

        prompt = f"""You are a Selenium Python expert. Generate a complete, production-ready, runnable Python Selenium script.

TEST CASE TO AUTOMATE:
{json.dumps(test_case, indent=2)}

Test Scenario: {test_scenario}
Expected Result: {test_expected}
Test Steps: {json.dumps(test_steps, indent=2)}

CHECKOUT HTML STRUCTURE:
{raw_html[:2500]}

AVAILABLE SELECTORS FROM HTML (use these - they are extracted from the actual HTML):
{json.dumps(selectors[:100], indent=2)}

RELEVANT DOCUMENTATION:
{aggregated}

CRITICAL REQUIREMENTS:
1. Write a COMPLETE, FULLY EXECUTABLE Python Selenium script
2. Import all necessary libraries: from selenium import webdriver, from selenium.webdriver.common.by import By, from selenium.webdriver.support.ui import WebDriverWait, from selenium.webdriver.support import expected_conditions as EC, from selenium.webdriver.chrome.service import Service, etc.
3. Use Chrome WebDriver with proper setup
4. Use EXPLICIT WAITS (WebDriverWait) for ALL element interactions - never use time.sleep() for waiting
5. Use selectors from the "Available Selectors" list above - prioritize ID selectors, then name, then class
6. If a needed selector is not in the list, infer a reasonable CSS selector based on the HTML structure
7. Follow the test case steps exactly: {json.dumps(test_steps, indent=2)}
8. Include proper error handling with try-except blocks
9. Add clear comments explaining each major step
10. Include a main execution block (if __name__ == "__main__")
11. Make the script verify the expected result: {test_expected}
12. Return ONLY valid Python code - NO markdown, NO explanations, NO code fences

SCRIPT STRUCTURE:
- Imports
- WebDriver setup
- Test execution following the test case steps
- Assertions/verifications for expected results
- Error handling
- Cleanup (driver.quit())
- Main block

Generate the complete Selenium Python script now:"""

        llm_out = call_llm(prompt, max_tokens=MAX_LLM_TOKENS)
        
        if "```python" in llm_out or "```" in llm_out:
            import re
            code_match = re.search(r'```(?:python)?\s*(.*?)```', llm_out, re.DOTALL)
            if code_match:
                llm_out = code_match.group(1).strip()
        
        return {"selenium_script": llm_out}
    except Exception as e:
        return {"selenium_script": f"GEMINI ERROR: Failed to generate script: {str(e)}"}
