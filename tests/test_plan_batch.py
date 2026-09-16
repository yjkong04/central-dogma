import io
import zipfile

import pytest

from worker.plan_batch import (
    PlanEntry, PlanLimits, plan_batch,
    BatchTooLarge, PdfTooLarge, EmptyBatch, InvalidArchive, PlanError,
)

LIMITS = PlanLimits(max_pdfs_per_zip=3, max_pdf_mb=1)


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in files.items():
            z.writestr(name, body)
    return buf.getvalue()


def test_single_pdf_is_a_batch_of_one():
    out = plan_batch(b"%PDF-1.7 body", "pdf", LIMITS)
    assert out == [PlanEntry(filename="upload.pdf", data=b"%PDF-1.7 body")]


def test_single_pdf_over_limit_raises():
    with pytest.raises(PdfTooLarge):
        plan_batch(b"x" * (1_048_576 + 1), "pdf", LIMITS)


def test_zip_returns_one_entry_per_pdf_in_order():
    data = _zip({"a.pdf": b"A", "b.pdf": b"B"})
    out = plan_batch(data, "zip", LIMITS)
    assert [(e.filename, e.data) for e in out] == [("a.pdf", b"A"), ("b.pdf", b"B")]


def test_zip_skips_non_pdf_and_directory_entries():
    data = _zip({"a.pdf": b"A", "notes.txt": b"x", "sub/": b"", "b.PDF": b"B"})
    out = plan_batch(data, "zip", LIMITS)
    assert [e.filename for e in out] == ["a.pdf", "b.PDF"]  # .PDF (any case) kept, txt/dir skipped


def test_zip_over_count_limit_raises():
    data = _zip({f"{i}.pdf": b"x" for i in range(4)})  # limit is 3
    with pytest.raises(BatchTooLarge):
        plan_batch(data, "zip", LIMITS)


def test_zip_with_oversized_pdf_raises():
    data = _zip({"big.pdf": b"x" * (1_048_576 + 1)})
    with pytest.raises(PdfTooLarge):
        plan_batch(data, "zip", LIMITS)


def test_empty_or_no_pdf_zip_raises():
    with pytest.raises(EmptyBatch):
        plan_batch(_zip({"readme.txt": b"x"}), "zip", LIMITS)
    with pytest.raises(EmptyBatch):
        plan_batch(_zip({}), "zip", LIMITS)


def test_corrupt_zip_raises_invalid_archive():
    with pytest.raises(PlanError) as exc_info:
        plan_batch(b"this is not a zip", "zip", LIMITS)
    assert isinstance(exc_info.value, InvalidArchive)
    assert isinstance(exc_info.value, PlanError)
