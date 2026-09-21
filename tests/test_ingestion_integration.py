"""End-to-end: presigned upload -> dispatcher -> worker -> Aurora -> /ask.

Slow-marked and env-gated (needs a deployed stack + AWS-reachable Function URL);
skipped in default CI. Run manually once a stack is deployed:

    CENTRALDOGMA_E2E=1 CENTRALDOGMA_E2E_API_URL=https://<function-url> \
        rtk proxy .venv/bin/python -m pytest tests/test_ingestion_integration.py -m slow
"""

import os
import time

import pytest

pytestmark = pytest.mark.slow

E2E = os.environ.get("CENTRALDOGMA_E2E") == "1"
API_BASE_URL = os.environ.get("CENTRALDOGMA_E2E_API_URL")


@pytest.fixture
def api_base_url():
    return API_BASE_URL


@pytest.fixture
def sample_pdf_bytes():
    from fpdf import FPDF, XPos, YPos

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)
    pdf.cell(0, 10, "Introduction", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(40)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, "This is a tiny one-page test paper used to exercise the "
                         "end-to-end async ingestion pipeline against a deployed stack.")
    return bytes(pdf.output())


@pytest.mark.skipif(not E2E or not API_BASE_URL,
                    reason="requires a deployed stack (set CENTRALDOGMA_E2E=1 and "
                           "CENTRALDOGMA_E2E_API_URL)")
def test_upload_pdf_becomes_answerable(api_base_url, sample_pdf_bytes):
    import requests  # dev-only; import inside the test so CI collection stays clean

    # 1. POST /uploads (single PDF) -> presigned POST
    r = requests.post(f"{api_base_url}/uploads", json={"filename": "sample.pdf", "kind": "pdf"})
    r.raise_for_status()
    up = r.json()
    batch_id = up["batch_id"]

    # 2. Upload the bytes to the presigned POST
    post = up["upload"]
    files = {"file": ("sample.pdf", sample_pdf_bytes)}
    ur = requests.post(post["url"], data=post["fields"], files=files)
    assert ur.status_code in (200, 204)

    # 3. Poll /batches/{id} until done (bounded)
    deadline = time.time() + 600
    state = None
    while time.time() < deadline:
        b = requests.get(f"{api_base_url}/batches/{batch_id}").json()
        state, done, failed = b["state"], b["done"], b["failed"]
        if done + failed >= b["total"] and b["total"] > 0:
            break
        time.sleep(10)
    assert done >= 1 and failed == 0, f"batch did not complete: {state}"

    # 4. /ask returns a grounded answer citing the uploaded paper
    a = requests.post(f"{api_base_url}/ask", json={"question": "What does this paper study?"}).json()
    assert a["answer"] and a.get("citations")
