# Autonomous QA Agent for Test Case and Script Generation

An intelligent, autonomous QA agent that constructs a "testing brain" from project documentation. The system ingests support documents (product specifications, UI/UX guidelines, mock APIs) alongside HTML structure to generate comprehensive test cases and executable Selenium scripts.

## Features

- **Phase 1: Knowledge Base Ingestion** - Upload and process documentation files
- **Phase 2: Test Case Generation** - Generate documentation-grounded test cases using RAG
- **Phase 3: Selenium Script Generation** - Convert test cases into executable Python Selenium scripts

## Requirements

- **Python Version**: 3.8 or higher
- **Backend**: FastAPI
- **Frontend**: Streamlit
- **Vector Database**: ChromaDB
- **Embeddings**: Sentence Transformers (all-MiniLM-L6-v2)
- **LLM**: Google Gemini API

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd OceanAI
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Get your Gemini API key from: https://ai.google.dev/

### 5. Project Structure

```
OceanAI/
├── backend/
│   └── main.py          # FastAPI backend server
├── frontend/
│   └── app.py           # Streamlit UI
├── testing/             # Sample documents
│   ├── checkout.html
│   ├── product_specs.md
│   ├── ui_ux_guide.txt
│   ├── api_endpoints.json
│   └── ...
├── requirements.txt
├── README.md
└── .env
```

## How to Run

### Step 1: Start the Backend Server

Open a terminal and run:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`

### Step 2: Start the Streamlit Frontend

Open another terminal and run:

```bash
cd frontend
streamlit run app.py
```

The frontend will open automatically in your browser at `http://localhost:8501`

## Usage Examples

### Phase 1: Build Knowledge Base

1. **Upload Support Documents**
   - Click on "Upload documentation files"
   - Select your files (PDF, TXT, MD, JSON, HTML)
   - Example files: `product_specs.md`, `ui_ux_guide.txt`, `api_endpoints.json`

2. **Upload checkout.html**
   - Click on "Upload checkout.html"
   - Select your HTML file

3. **Build Knowledge Base**
   - Click "Build Knowledge Base"
   - Wait for confirmation: "Knowledge Base built successfully!"

### Phase 2: Generate Test Cases

1. **Enter Your Request**
   - Example: "Generate all positive and negative test cases for the discount code feature"
   - Adjust the context chunks slider (3-8 recommended)

2. **Generate Test Cases**
   - Click "Generate Test Cases"
   - Review the generated test cases
   - Each test case includes:
     - ID
     - Title
     - Scenario
     - Steps
     - Expected Result
     - Source Document (Grounded_In)

3. **Select a Test Case**
   - Click "Select Test Case X" on any test case
   - The selected test case will be highlighted

### Phase 3: Generate Selenium Script

1. **Upload checkout.html**
   - Upload the checkout.html file again for accuracy

2. **Generate Script**
   - Click "Generate Selenium Script"
   - Wait for generation (may take 30-60 seconds)

3. **Review and Download**
   - Review the generated Python Selenium script
   - Click "Download Script" to save the file
   - The script is ready to run with: `python selenium_test.py`

## Support Documents Explanation

The system works with various document types:

### 1. **product_specs.md**
Contains feature rules and specifications:
- Discount code rules (e.g., "SAVE15 applies 15% discount")
- Shipping costs (e.g., "Express shipping costs $10")
- Feature descriptions and business rules

### 2. **ui_ux_guide.txt**
Contains UI/UX guidelines:
- Form validation rules
- Color schemes
- Button styles
- Error message formats

### 3. **api_endpoints.json**
Contains API endpoint definitions:
```json
{
  "POST /apply_coupon": {"code": "string"},
  "POST /submit_order": {"name": "string", "email": "string"}
}
```

### 4. **checkout.html**
The target web application HTML file containing:
- Add to Cart buttons
- Cart summary with quantity inputs
- Discount code input field
- User Details form (Name, Email, Address)
- Form validation
- Shipping method radio buttons
- Payment method radio buttons
- Pay Now button

## 🔧 Technical Details

### Backend Architecture

- **FastAPI**: RESTful API server
- **ChromaDB**: Vector database for document storage
- **Sentence Transformers**: Text embeddings
- **Google Gemini API**: LLM for test case and script generation

### Frontend Architecture

- **Streamlit**: Interactive web UI
- **Requests**: HTTP client for backend communication

### RAG Pipeline

1. **Document Ingestion**:
   - Parse documents (PDF, TXT, MD, JSON, HTML)
   - Chunk text into manageable pieces (350 words, 80 overlap)
   - Generate embeddings using Sentence Transformers
   - Store in ChromaDB with metadata

2. **Query Processing**:
   - Embed user query
   - Retrieve top-k relevant chunks
   - Aggregate context from multiple documents

3. **LLM Generation**:
   - Feed context + query to Gemini API
   - Generate structured test cases (JSON format)
   - Extract and validate output

### Test Case Format

```json
{
  "id": "TC001",
  "title": "Valid discount code application",
  "scenario": "User applies a valid discount code",
  "steps": [
    "Navigate to checkout",
    "Enter discount code",
    "Apply code"
  ],
  "expected": "Discount is applied successfully",
  "based_on": "product_specs.md"
}
```

### Selenium Script Features

- Uses Chrome WebDriver
- Explicit waits (WebDriverWait)
- Proper error handling
- Selectors extracted from actual HTML
- Follows test case steps exactly
- Includes assertions for expected results

## Troubleshooting

### Common Issues

1. **"GEMINI ERROR: Quota exceeded"**
   - Wait a few minutes and try again
   - Check your API quota at: https://ai.dev/usage
   - Reduce the number of context chunks

2. **"Could not parse JSON"**
   - Try simplifying your request
   - Reduce context chunks
   - Check if documents are properly uploaded

3. **Backend not responding**
   - Ensure backend is running on port 8000
   - Check for port conflicts
   - Verify all dependencies are installed

4. **Knowledge Base not building**
   - Ensure documents are uploaded
   - Check file formats are supported
   - Verify ChromaDB directory permissions

## 🎥 Demo Video (Contains)

link : https://drive.google.com/file/d/15s2kdS8Mjx1MKMHRP0fKU8NhuG1ETOr5/view?usp=sharing

1. ✅ Uploading documents + HTML
2. ✅ Building the knowledge base
3. ✅ Generating test cases
4. ✅ Selecting a test case
5. ✅ Generating Selenium scripts
6. ✅ Downloading and reviewing the script

## License

This project is created for educational/assignment purposes.

## 👤 Author

Developed by Deepesh Raj A.Y

## 🙏 Acknowledgments

- Google Gemini API
- ChromaDB
- Sentence Transformers
- FastAPI
- Streamlit

