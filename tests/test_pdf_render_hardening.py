import logging

import pytest

import ingest.pdf.render as render


class _FakePage:
    def __init__(self, index: int) -> None:
        self.index = index


class _FakeDoc:
    """Stand-in for pypdfium2.PdfDocument: len/getitem/close only."""

    def __init__(self, n: int) -> None:
        self._n = n
        self.closed = False

    def __len__(self) -> int:
        return self._n

    def __getitem__(self, i: int) -> _FakePage:
        return _FakePage(i)

    def close(self) -> None:
        self.closed = True


def _write_fake_pdf(tmp_path):
    p = tmp_path / "fake.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return p


def test_one_bad_page_is_skipped_not_fatal(monkeypatch, tmp_path):
    pdf_path = _write_fake_pdf(tmp_path)
    fake_doc = _FakeDoc(3)
    monkeypatch.setattr(render.pdfium, "PdfDocument", lambda path: fake_doc)
    monkeypatch.setattr(render, "_native_text", lambda page, scale, i: [])

    def fake_rasterize(page, index, dpi):
        if index == 1:
            raise RuntimeError("corrupt page")
        return object()  # stand-in for a PIL.Image

    monkeypatch.setattr(render, "_rasterize_page", fake_rasterize)

    pages = render.render_pdf(pdf_path)

    assert [pg.index for pg in pages] == [0, 2]
    assert fake_doc.closed


def test_bad_page_is_logged_not_raised(monkeypatch, tmp_path, caplog):
    pdf_path = _write_fake_pdf(tmp_path)
    fake_doc = _FakeDoc(2)
    monkeypatch.setattr(render.pdfium, "PdfDocument", lambda path: fake_doc)
    monkeypatch.setattr(render, "_native_text", lambda page, scale, i: [])

    def fake_rasterize(page, index, dpi):
        raise RuntimeError("boom")

    monkeypatch.setattr(render, "_rasterize_page", fake_rasterize)

    with caplog.at_level(logging.WARNING):
        pages = render.render_pdf(pdf_path)

    assert pages == []
    assert any("boom" in rec.message for rec in caplog.records)


def test_max_render_px_constant_is_positive():
    assert render.MAX_RENDER_PX > 0


def test_guard_render_size_raises_when_oversized():
    with pytest.raises(render.RenderTooLarge):
        render._guard_render_size(width_px=render.MAX_RENDER_PX + 1, height_px=1)


def test_guard_render_size_allows_within_bound():
    render._guard_render_size(width_px=100, height_px=100)  # should not raise


def test_render_too_large_is_a_pdf_ingest_error():
    from ingest.pdf.types import PdfIngestError

    assert issubclass(render.RenderTooLarge, PdfIngestError)
