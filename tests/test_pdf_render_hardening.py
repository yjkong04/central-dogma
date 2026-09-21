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


class _FakeDocBadIndex(_FakeDoc):
    """Like _FakeDoc, but __getitem__ itself raises for a chosen page index.

    Models a corrupt/unreadable page-directory entry in an untrusted PDF,
    which pypdfium2 can surface as an exception straight out of doc[i].
    """

    def __init__(self, n: int, bad_index: int) -> None:
        super().__init__(n)
        self._bad_index = bad_index

    def __getitem__(self, i: int) -> _FakePage:
        if i == self._bad_index:
            raise RuntimeError("corrupt page directory entry")
        return super().__getitem__(i)


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


def test_bad_page_index_access_is_skipped_not_fatal(monkeypatch, tmp_path, caplog):
    # doc[i] itself raises for page index 1 (corrupt page-directory entry),
    # not _rasterize_page or _native_text. render_pdf must still skip just
    # that page and keep rendering the rest, not abort the whole PDF.
    pdf_path = _write_fake_pdf(tmp_path)
    fake_doc = _FakeDocBadIndex(3, bad_index=1)
    monkeypatch.setattr(render.pdfium, "PdfDocument", lambda path: fake_doc)
    monkeypatch.setattr(render, "_native_text", lambda page, scale, i: [])
    monkeypatch.setattr(render, "_rasterize_page", lambda page, index, dpi: object())

    with caplog.at_level(logging.WARNING):
        pages = render.render_pdf(pdf_path)

    assert [pg.index for pg in pages] == [0, 2]
    assert fake_doc.closed
    assert any("corrupt page directory entry" in rec.message for rec in caplog.records)


def test_native_text_failure_keeps_page_with_empty_text(monkeypatch, tmp_path, caplog):
    # Rasterize succeeds; _native_text raises something other than pdfium.PdfiumError
    # (e.g. an unexpected bug). The page must still be kept, image intact, with
    # native_text degraded to [] rather than the whole page being dropped.
    pdf_path = _write_fake_pdf(tmp_path)
    fake_doc = _FakeDoc(1)
    monkeypatch.setattr(render.pdfium, "PdfDocument", lambda path: fake_doc)

    sentinel_image = object()
    monkeypatch.setattr(render, "_rasterize_page", lambda page, index, dpi: sentinel_image)

    def fake_native_text(page, scale, i):
        raise AttributeError("unexpected bug, not a missing-text-layer case")

    monkeypatch.setattr(render, "_native_text", fake_native_text)

    with caplog.at_level(logging.WARNING):
        pages = render.render_pdf(pdf_path)

    assert len(pages) == 1
    assert pages[0].index == 0
    assert pages[0].image is sentinel_image
    assert pages[0].native_text == []
    assert any("native text extraction failed" in rec.message for rec in caplog.records)


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
