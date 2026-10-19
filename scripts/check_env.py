"""Environment check script for Provenance.

Verifies:
1. Python version >= 3.11.
2. `ollama --version` executes successfully.
3. `gemma4:12b` is present in `ollama list`.
4. A test chat completion at http://localhost:11434/v1 returns valid JSON.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request

def check_python_version() -> bool:
    print(f"[1/4] Checking Python version...")
    version = sys.version_info
    print(f"      Found Python {version.major}.{version.minor}.{version.micro} at {sys.executable}")
    if (version.major, version.minor) < (3, 11):
        print("      FAILED: Python 3.11+ is required.")
        return False
    print("      PASSED: Python >= 3.11 verified.")
    return True

def check_ollama_version() -> bool:
    print(f"[2/4] Checking ollama version...")
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        version_str = result.stdout.strip() or result.stderr.strip()
        print(f"      Found: {version_str}")
        print("      PASSED: ollama command is accessible.")
        return True
    except FileNotFoundError:
        print("      FAILED: 'ollama' executable not found in PATH.")
        return False
    except subprocess.CalledProcessError as exc:
        print(f"      FAILED: 'ollama --version' exited with code {exc.returncode}: {exc.stderr}")
        return False

def check_ollama_model(required_model: str = "gemma4:12b") -> bool:
    print(f"[3/4] Checking if '{required_model}' is present in `ollama list`...")
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout
        print("      `ollama list` output:")
        for line in output.strip().splitlines():
            print(f"        {line}")

        if any(line.split()[0] == required_model for line in output.strip().splitlines() if line.strip() and not line.startswith("NAME")):
            print(f"      PASSED: Model '{required_model}' is installed.")
            return True

        if required_model in output:
            print(f"      PASSED: Model '{required_model}' found.")
            return True

        print(f"      FAILED: Model '{required_model}' not found in `ollama list`.")
        return False
    except Exception as exc:
        print(f"      FAILED: Error running `ollama list`: {exc}")
        return False

def check_chat_completion(
    model: str = "gemma4:12b",
    base_url: str = "http://localhost:11434/v1/chat/completions",
) -> bool:
    print(f"[4/4] Testing OpenAI-compatible chat completion at {base_url}...")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Return a JSON object with keys 'status' ('ok') and 'service' ('provenance-verifier'). Do not include explanation outside JSON.",
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.status
            body_bytes = resp.read()
            body_text = body_bytes.decode("utf-8")

        if status_code != 200:
            print(f"      FAILED: HTTP {status_code} received from Ollama.")
            return False

        parsed_api_response = json.loads(body_text)
        content = parsed_api_response["choices"][0]["message"]["content"]
        print(f"      Raw assistant content:\n        {content.strip()}")

        model_json = json.loads(content)
        print(f"      Parsed JSON from model: {model_json}")
        if model_json.get("status") == "ok":
            print("      PASSED: Ollama OpenAI-compatible endpoint returned valid JSON with expected content.")
            return True

        print("      PASSED: Ollama returned valid JSON (structure differs slightly but valid).")
        return True
    except urllib.error.URLError as exc:
        print(f"      FAILED: Could not connect to Ollama at {base_url}: {exc}")
        return False
    except json.JSONDecodeError as exc:
        print(f"      FAILED: Response content is not valid JSON: {exc}")
        return False
    except Exception as exc:
        print(f"      FAILED: Unexpected error: {exc}")
        return False

def main() -> int:
    print("=" * 60)
    print("Provenance Environment & LLM Verification")
    print("=" * 60)

    checks = [
        check_python_version(),
        check_ollama_version(),
        check_ollama_model("gemma4:12b"),
        check_chat_completion("gemma4:12b"),
    ]

    print("=" * 60)
    if all(checks):
        print("ALL CHECKS PASSED: Environment is ready for Provenance.")
        print("=" * 60)
        return 0
    else:
        print("CHECKS FAILED: Please fix the errors above before proceeding.")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
