# Execution record: convert/ document-conversion tools

Date: 2026-06-25
Branch: convert-tools → merged to master
Spec: ../specs/2026-06-25-convert-document-conversion-tools-design.md
Plan: ../plans/2026-06-25-convert-document-tools.md

Built via subagent-driven development: a foundation agent, four parallel
script agents, a wiring agent, one whole-branch review, and a fix pass.

## What shipped

`convert/` — four one-shot, offline, no-model conversion scripts plus a shared
`common.py` (CLI runner + IO helpers + markitdown wrapper), wired into the TUI:

- `pdf_to_md.py`  — pymupdf4llm
- `pdf_to_txt.py` — PyMuPDF `get_text`
- `docx_to_md.py` — markitdown
- `pptx_to_md.py` — markitdown

Born-digital only; scanned PDFs remain `transcribe`'s job. 78 tests pass, no
model/network in the suite.

## Commit trail (off master @ becbda0)

- `6752a9d` docs: design spec
- `c0d0f9f` docs: implementation plan
- `d23d610` foundation — common helpers, cli, deps, fixtures
- `2f412a1` four conversion scripts
- `d4e6cec` TUI wiring + CLAUDE.md
- `a2c6f3f` review fixes (cli failure-path test; lowercase TUI format input; doc fix)
- `e8639e0` swap markitdown → mammoth + python-pptx  *(later reverted)*
- `c608252` revert the swap — restore markitdown

## Key decisions

1. **Scope:** born-digital only — no OCR/model. Keeps `convert` cheap and
   deterministic; scanned input is `transcribe`'s job.
2. **Tooling:** hybrid best-of-breed — pymupdf4llm (pdf→md), PyMuPDF (pdf→txt),
   markitdown (docx/pptx→md).
3. **Structure:** one thin pure function per format (`name(in_path) -> str`),
   sharing `convert/common.py`'s `cli()`; each script independently runnable.
4. **onnxruntime / markitdown saga:** the final review flagged that markitdown
   pulls `magika → onnxruntime` (a local ML stack), in tension with the project's
   "no model, lean" ethos. We swapped to mammoth + python-pptx (e8639e0) — but
   then found `pymupdf4llm` *also* pulls onnxruntime (via `pymupdf-layout`), so
   the swap couldn't remove onnxruntime anyway. Decision: **accept onnxruntime**
   (offline; powers genuine PDF layout detection) and **keep markitdown** (richer
   pptx extraction: tables, speaker notes). The swap was reverted (c608252).

## Review

opus whole-branch review: APPROVE-WITH-NITS, no Critical/blocking defects.
Important findings addressed: added the `cli` conversion-failure test (spec-
required path); surfaced the onnxruntime footprint for a human decision.
