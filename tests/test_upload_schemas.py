from api.schemas import UploadRequest, UploadResponse, PresignedPost, BatchStatusResponse, PaperState


def test_upload_request_defaults_to_zip():
    assert UploadRequest(filename="p.pdf").kind == "zip"


def test_upload_request_rejects_bad_kind():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        UploadRequest(filename="p", kind="tar")


def test_batch_status_shape():
    r = BatchStatusResponse(batch_id="b1", state="pending", total=2, done=1, failed=0,
                            papers=[PaperState(paper_id="A", filename="a.pdf", state="done")])
    assert r.papers[0].error is None
    assert UploadResponse(batch_id="b1",
                          upload=PresignedPost(url="https://s3", fields={"key": "uploads/b1.zip"})).upload.fields["key"] == "uploads/b1.zip"
