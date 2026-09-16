"""Pure unzip/validate for an uploaded object → a list of PDF entries.

No AWS, no I/O beyond the in-memory bytes handed in. The dispatcher builds
PlanLimits from config and fans each returned entry onto SQS.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass


@dataclass
class PlanEntry:
    filename: str
    data: bytes


@dataclass
class PlanLimits:
    max_pdfs_per_zip: int
    max_pdf_mb: int


class PlanError(Exception):
    pass


class BatchTooLarge(PlanError):
    pass


class PdfTooLarge(PlanError):
    pass


class EmptyBatch(PlanError):
    pass


class InvalidArchive(PlanError):
    pass


def _check_size(name: str, data: bytes, max_pdf_mb: int) -> None:
    if len(data) > max_pdf_mb * 1_048_576:
        raise PdfTooLarge(f"{name} exceeds {max_pdf_mb} MB")


def plan_batch(data: bytes, kind: str, limits: PlanLimits) -> list[PlanEntry]:
    if kind == "pdf":
        _check_size("upload.pdf", data, limits.max_pdf_mb)
        return [PlanEntry(filename="upload.pdf", data=data)]

    # kind == "zip"
    entries: list[PlanEntry] = []
    try:
        zf_ctx = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise InvalidArchive("not a readable zip archive")
    with zf_ctx as zf:
        pdf_names = [
            n for n in zf.namelist()
            if not n.endswith("/") and n.lower().endswith(".pdf")
        ]
        if len(pdf_names) > limits.max_pdfs_per_zip:
            raise BatchTooLarge(
                f"{len(pdf_names)} PDFs exceeds max {limits.max_pdfs_per_zip}"
            )
        for name in pdf_names:
            if zf.getinfo(name).file_size > limits.max_pdf_mb * 1_048_576:
                raise PdfTooLarge(f"{name} exceeds {limits.max_pdf_mb} MB")
            body = zf.read(name)
            _check_size(name, body, limits.max_pdf_mb)
            entries.append(PlanEntry(filename=name, data=body))
    if not entries:
        raise EmptyBatch("no PDF found in archive")
    return entries
