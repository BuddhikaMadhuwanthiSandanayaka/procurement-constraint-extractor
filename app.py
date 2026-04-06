import streamlit as st
import PyPDF2
import docx
import re
import json
import pandas as pd
from datetime import datetime, date

# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="Procurement Constraint Intelligence",
    page_icon="📄",
    layout="wide"
)

# -----------------------------
# Custom styling
# -----------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}
[data-testid="stAppViewContainer"] {
    background: linear-gradient(to bottom, #f8fbff, #eef4f9);
}
.card {
    background: white;
    padding: 1.2rem;
    border-radius: 16px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.08);
    margin-bottom: 1rem;
}
.section-title {
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
}
.small-muted {
    color: #5f6b7a;
    font-size: 0.95rem;
}
.footer {
    text-align: center;
    color: #6b7280;
    font-size: 0.85rem;
    margin-top: 2rem;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Session state for tracker
# -----------------------------
if "tracker_data" not in st.session_state:
    st.session_state.tracker_data = []

if "current_output" not in st.session_state:
    st.session_state.current_output = None

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.header("Workflow")
    st.markdown("""
    1. Upload supplier document  
    2. Review extracted text  
    3. Extract constraints  
    4. Review structured output  
    5. Add record to MOQ tracker  
    """)
    st.info("Best results come from text-based PDF, DOCX, or TXT files.")
    st.success("New feature: Active Supplier MOQ & Deadline Tracker")

# -----------------------------
# Header section
# -----------------------------
st.image(
    "banner.png",
    use_container_width=True
)

st.title("Procurement Constraint Intelligence")
st.caption(
    "A web-based prototype for transforming supplier documents into structured procurement constraints for decision support."
)

st.markdown(
    """
    <div class="card">
        <div class="section-title">Prototype Purpose</div>
        <div class="small-muted">
            This proof of concept demonstrates supplier document ingestion, parsing, structured procurement
            constraint extraction, and cumulative supplier visibility through an MOQ and deadline tracker.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

step1, step2, step3, step4 = st.columns(4)
step1.metric("Step 1", "Upload")
step2.metric("Step 2", "Parse")
step3.metric("Step 3", "Extract")
step4.metric("Step 4", "Track")

# -----------------------------
# Helper functions
# -----------------------------
def extract_text(file):
    """Extract text from uploaded PDF, DOCX, or TXT files."""
    if file.type == "application/pdf":
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()

    elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs]).strip()

    elif file.type == "text/plain":
        return file.read().decode("utf-8").strip()

    return ""

def find_pattern(text, patterns):
    """Try multiple regex patterns and return the first match."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def parse_deadline(deadline_text):
    """Convert extracted deadline string into a Python date."""
    if not deadline_text:
        return None

    formats = [
        "%B %d, %Y",   # April 15, 2026
        "%Y-%m-%d",    # 2026-04-15
        "%b %d, %Y"    # Apr 15, 2026
    ]

    for fmt in formats:
        try:
            return datetime.strptime(deadline_text, fmt).date()
        except ValueError:
            continue
    return None

def get_deadline_status(deadline_date):
    """Label the deadline status for planning visibility."""
    if not deadline_date:
        return "No deadline"

    today = date.today()
    delta = (deadline_date - today).days

    if delta < 0:
        return "Past due"
    elif delta <= 7:
        return "Urgent"
    elif delta <= 21:
        return "Upcoming"
    else:
        return "Planned"

def extract_constraints_demo(text):
    """Rule-based procurement constraint extractor for demo purposes."""
    result = {
        "supplier_name": None,
        "product_scope": None,
        "moq": None,
        "order_multiple": None,
        "lead_time": None,
        "payment_terms": None,
        "penalties": None,
        "delivery_restrictions": None,
        "cancellation_conditions": None,
        "conditions": None,
        "order_deadline": None,
        "confidence": "Medium",
        "evidence": {}
    }

    # Supplier name
    supplier = find_pattern(text, [
        r"Supplier:\s*(.+)",
        r"Supplier Name:\s*(.+)"
    ])
    if supplier:
        result["supplier_name"] = supplier
        result["evidence"]["supplier_name"] = f"Supplier: {supplier}"

    # Product scope
    product_scope = find_pattern(text, [
        r"Product Scope:\s*(.+)",
        r"Product Category:\s*(.+)"
    ])
    if product_scope:
        result["product_scope"] = product_scope
        result["evidence"]["product_scope"] = f"Product Scope: {product_scope}"

    # MOQ
    moq = find_pattern(text, [
        r"minimum order quantity is (\d+)\s*units",
        r"MOQ is (\d+)\s*units",
        r"MOQ\s*[:\-]?\s*(\d+)\s*units"
    ])
    if moq:
        result["moq"] = int(moq)
        result["evidence"]["moq"] = f"Matched MOQ value: {moq} units"

    # Order multiple
    order_multiple = find_pattern(text, [
        r"multiples of (\d+)",
        r"order multiple is (\d+)",
        r"order multiples?\s*[:\-]?\s*(\d+)"
    ])
    if order_multiple:
        result["order_multiple"] = int(order_multiple)
        result["evidence"]["order_multiple"] = f"Matched order multiple: {order_multiple}"

    # Lead time
    lead_time = find_pattern(text, [
        r"lead time is (\d+\s*days)",
        r"standard lead time is (\d+\s*days)",
        r"lead time\s*[:\-]?\s*(\d+\s*days)"
    ])
    if lead_time:
        result["lead_time"] = lead_time
        result["evidence"]["lead_time"] = f"Matched lead time: {lead_time}"

    # Payment terms
    payment_terms = find_pattern(text, [
        r"payment terms are ([A-Za-z0-9\s]+)",
        r"payment terms\s*[:\-]?\s*([A-Za-z0-9\s]+)",
        r"terms are ([A-Za-z0-9\s]+)"
    ])
    if payment_terms:
        result["payment_terms"] = payment_terms.strip()
        result["evidence"]["payment_terms"] = f"Matched payment terms: {payment_terms}"

    # Penalties
    penalties = find_pattern(text, [
        r"below MOQ incur (.+)",
        r"penalty\s*[:\-]?\s*(.+)",
        r"surcharge\s*[:\-]?\s*(.+)"
    ])
    if penalties:
        result["penalties"] = penalties.strip()
        result["evidence"]["penalties"] = f"Matched penalties: {penalties}"

    # Delivery restrictions
    delivery = find_pattern(text, [
        r"delivery restrictions\s*[:\-]?\s*(.+)",
        r"shipping only to (.+)"
    ])
    if delivery:
        result["delivery_restrictions"] = delivery.strip()
        result["evidence"]["delivery_restrictions"] = f"Matched delivery restriction: {delivery}"
    elif re.search(r"FOB origin", text, re.IGNORECASE):
        result["delivery_restrictions"] = "FOB origin"
        result["evidence"]["delivery_restrictions"] = "Matched delivery restriction: FOB origin"

    # Cancellation conditions
    cancellation = find_pattern(text, [
        r"cancellable within (.+)",
        r"cancellation conditions?\s*[:\-]?\s*(.+)",
        r"orders cancellable within (.+)"
    ])
    if cancellation:
        result["cancellation_conditions"] = cancellation.strip()
        result["evidence"]["cancellation_conditions"] = f"Matched cancellation condition: {cancellation}"

    # Order deadline
    deadline = find_pattern(text, [
        r"Order deadline is ([A-Za-z]+ \d{1,2}, \d{4})",
        r"Orders must be placed by (\d{4}-\d{2}-\d{2})",
        r"Orders must be placed by ([A-Za-z]+ \d{1,2}, \d{4})",
        r"Deadline:\s*([A-Za-z]+ \d{1,2}, \d{4})",
        r"Deadline:\s*(\d{4}-\d{2}-\d{2})"
    ])
    if deadline:
        result["order_deadline"] = deadline
        result["evidence"]["order_deadline"] = f"Matched order deadline: {deadline}"

    # Conditions / conditional flags
    conditions = []
    if re.search(r"peak season", text, re.IGNORECASE):
        conditions.append("Peak season condition detected")
    if re.search(r"standard items", text, re.IGNORECASE):
        conditions.append("Standard item condition detected")
    if re.search(r"premium items", text, re.IGNORECASE):
        conditions.append("Premium item condition detected")

    if conditions:
        result["conditions"] = conditions
        result["evidence"]["conditions"] = "; ".join(conditions)

    # Confidence scoring
    filled_fields = sum(
        1 for k, v in result.items()
        if k not in ["confidence", "evidence"] and v not in [None, [], {}]
    )

    if filled_fields >= 7:
        result["confidence"] = "High"
    elif filled_fields >= 4:
        result["confidence"] = "Medium"
    else:
        result["confidence"] = "Low"

    return result

# -----------------------------
# Main layout
# -----------------------------
left, right = st.columns([1, 1])

with left:
    st.markdown(
        """
        <div class="card">
            <div class="section-title">Upload Document</div>
            <div class="small-muted">Supported file types: PDF, DOCX, TXT</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "txt"])

with right:
    st.markdown(
        """
        <div class="card">
            <div class="section-title">Decision-Support Goal</div>
            <div class="small-muted">
                Convert supplier policy documents into structured procurement constraints and consolidate
                active supplier MOQ and deadline visibility.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# -----------------------------
# Extraction workflow
# -----------------------------
if uploaded_file:
    st.success(f"Uploaded file: {uploaded_file.name}")
    document_text = extract_text(uploaded_file)

    if not document_text:
        st.warning("No readable text was extracted from this file.")
        st.info("Use text-based PDF, DOCX, or TXT files for the best demo results.")
    else:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("Extracted Text Preview")
            st.text_area("Document text", document_text, height=320)

        with col2:
            st.subheader("Structured Output Panel")

            if st.button("Extract Constraints"):
                output = extract_constraints_demo(document_text)
                st.session_state.current_output = output

            if st.session_state.current_output:
                output = st.session_state.current_output

                st.code(json.dumps(output, indent=2), language="json")

                m1, m2, m3, m4 = st.columns(4)
                m1.info(f"MOQ: {output.get('moq')}")
                m2.success(f"Lead Time: {output.get('lead_time')}")
                m3.warning(f"Deadline: {output.get('order_deadline')}")
                m4.error(f"Confidence: {output.get('confidence')}")

                if st.button("Add to MOQ Tracker"):
                    deadline_date = parse_deadline(output.get("order_deadline"))
                    status = get_deadline_status(deadline_date)

                    row = {
                        "Supplier": output.get("supplier_name"),
                        "Product Scope": output.get("product_scope"),
                        "MOQ": output.get("moq"),
                        "Order Multiple": output.get("order_multiple"),
                        "Lead Time": output.get("lead_time"),
                        "Order Deadline": output.get("order_deadline"),
                        "Status": status
                    }

                    st.session_state.tracker_data.append(row)
                    st.success("Record added to Active Supplier MOQ & Deadline Tracker.")

                st.info("This prototype demonstrates structured procurement constraint extraction and planner review.")

# -----------------------------
# Tracker section
# -----------------------------
st.markdown("---")
st.subheader("Active Supplier MOQ & Deadline Tracker")

if st.session_state.tracker_data:
    tracker_df = pd.DataFrame(st.session_state.tracker_data)
    st.dataframe(tracker_df, use_container_width=True)

    urgent_count = (tracker_df["Status"] == "Urgent").sum()
    upcoming_count = (tracker_df["Status"] == "Upcoming").sum()
    planned_count = (tracker_df["Status"] == "Planned").sum()

    a, b, c = st.columns(3)
    a.error(f"Urgent: {urgent_count}")
    b.warning(f"Upcoming: {upcoming_count}")
    c.success(f"Planned: {planned_count}")
else:
    st.info("No supplier records added yet. Upload a document and click 'Add to MOQ Tracker'.")

# -----------------------------
# Footer
# -----------------------------
st.markdown("---")
st.markdown('<div class="footer">Group 1 | Procurement Constraint Intelligence PoC</div>', unsafe_allow_html=True)