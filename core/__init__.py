"""Shared internals for the FileHandlingTools apps.

Houses the things both tools (translate, transcribe) depend on: the model mapper
(`modelmap` + `models.json`), the Ollama chat client (`ollama`), small helpers
(`pages`), and the bundled font under `assets/`.
"""
