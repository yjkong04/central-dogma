"""Regenerate the committed PDF fixtures. Run once; commit the output.

    python tests/fixtures/pdf/make_fixtures.py
"""
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).parent


def born_digital() -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)
    pdf.cell(0, 10, "Introduction", ln=True)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, "This is a born-digital test paper with a real text layer. "
                         "It exists so the renderer and native-text path can be tested "
                         "without OCR. Central Dogma ingests arbitrary PDFs.")
    pdf.output(str(OUT / "born_digital.pdf"))


if __name__ == "__main__":
    born_digital()
    print("wrote born_digital.pdf")
