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


def test_zip_size_decision_ignores_declared_file_size(monkeypatch):
    """`ZipInfo.file_size` is attacker-controlled central-directory metadata,
    not a property of the actual bytes a member decompresses to, so the size
    cap must be decided from bytes actually read, never from the declared
    value. Prove it by forging file_size to look huge on a member whose real
    content is well under the limit — plan_batch must still accept it,
    showing the decision tracks real bytes rather than trusting metadata."""
    data = _zip({"tiny.pdf": b"%PDF-1.7 body"})

    real_getinfo = zipfile.ZipFile.getinfo

    def lying_getinfo(self, name):
        info = real_getinfo(self, name)
        info.file_size = 100 * 1_048_576  # falsely claim the member is huge
        return info

    monkeypatch.setattr(zipfile.ZipFile, "getinfo", lying_getinfo)

    out = plan_batch(data, "zip", LIMITS)
    assert [(e.filename, e.data) for e in out] == [("tiny.pdf", b"%PDF-1.7 body")]


def test_corrupt_member_raises_invalid_archive_not_raw_badzipfile():
    """A structurally valid zip whose member data is corrupted (flipped byte
    breaks the CRC-32) must surface as a typed PlanError, never an unhandled
    zipfile.BadZipFile crash."""
    data = bytearray(_zip({"a.pdf": b"%PDF-1.7 " + b"y" * 100}))
    # Flip a byte inside the stored file data (after the local header + name)
    # so the CRC-32 recorded at zip-creation time no longer matches.
    marker = b"%PDF-1.7 "
    idx = data.index(marker) + len(marker)
    data[idx] ^= 0xFF

    with pytest.raises(PlanError) as exc_info:
        plan_batch(bytes(data), "zip", LIMITS)
    assert isinstance(exc_info.value, InvalidArchive)


def test_corrupt_zip_raises_invalid_archive():
    with pytest.raises(PlanError) as exc_info:
        plan_batch(b"this is not a zip", "zip", LIMITS)
    assert isinstance(exc_info.value, InvalidArchive)
    assert isinstance(exc_info.value, PlanError)
