# ai-generated: 90% - Claude wrote the script from HANDOUT.md, Stretch 1 (the pinned versions); I ran it with my own API key
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openai==3.19.2",
#   "opentelemetry-sdk==1.45.0",
#   "opentelemetry-instrumentation-genai-openai==1.2b0",
#   "opentelemetry-exporter-otlp-json-file==0.66b0",
# ]
# ///
"""Lab 3, Stretch 1 (M-28): one instrumented LLM call, its spans written as OTLP JSON to genai/spans.json.

Run from the repository root:
    $env:GEMINI_API_KEY = "<key from aistudio.google.com/apikey>"     # PowerShell; never commit the key
    uv run genai/run.py

Any OpenAI-compatible endpoint works: set GENAI_BASE_URL and GENAI_MODEL (for Ollama:
http://localhost:11434/v1 and qwen3:1.7b, with GEMINI_API_KEY set to any non-empty string).
"""

from __future__ import annotations

import os
from pathlib import Path

from opentelemetry import trace
from opentelemetry.exporter.otlp.json.file.trace_exporter import FileSpanExporter
from opentelemetry.instrumentation.genai.openai import OpenAIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

OUT = Path(__file__).resolve().parent / "spans.json"
BASE_URL = os.environ.get("GENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
MODEL = os.environ.get("GENAI_MODEL", "gemini-2.5-flash")


def main() -> None:
    OUT.unlink(missing_ok=True)  # the exporter appends; start from an empty file
    provider = TracerProvider(resource=Resource.create({"service.name": "svcdesk-genai-probe"}))
    provider.add_span_processor(SimpleSpanProcessor(FileSpanExporter(OUT)))
    trace.set_tracer_provider(provider)
    OpenAIInstrumentor().instrument(tracer_provider=provider)

    from openai import OpenAI  # imported after instrument(), so the client is patched

    client = OpenAI(base_url=BASE_URL, api_key=os.environ["GEMINI_API_KEY"])
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "In one sentence: what is an error budget in SRE?"}],
        max_tokens=200,
        temperature=0.2,
    )
    print(response.choices[0].message.content)
    provider.shutdown()  # flush the span to the file
    print(f"spans written to {OUT}")


if __name__ == "__main__":
    main()
