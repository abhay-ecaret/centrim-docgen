import requests
import subprocess
import sys
import json

OLLAMA_URL = "http://localhost:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_URL}/api/generate"
OLLAMA_TAGS_URL = f"{OLLAMA_URL}/api/tags"

def check_ollama_status():
    print(f"[⚙️] Checking Ollama server status at {OLLAMA_URL}...")
    try:
        response = requests.get(OLLAMA_URL, timeout=5)
        if response.status_code == 200:
            print("[✅] Ollama server is running.")
            return True
        else:
            print(f"[❌] Ollama server responded with status code {response.status_code}.")
            return False
    except requests.exceptions.ConnectionError:
        print(f"[❌] Could not connect to Ollama server at {OLLAMA_URL}.")
        print("Please ensure Ollama is installed and running.")
        print("Download Ollama from: https://ollama.com/")
        print("After installation, Ollama usually starts automatically.")
        return False
    except requests.exceptions.Timeout:
        print(f"[❌] Connection to Ollama server timed out.")
        return False
    except Exception as e:
        print(f"[❌] An unexpected error occurred while checking Ollama status: {e}")
        return False

def get_available_ollama_models():
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [m['name'].split(':')[0] for m in data.get('models', [])]
        return sorted(list(set(models)))
    except requests.exceptions.RequestException as e:
        print(f"[❌] Error fetching Ollama models: {e}")
        return []

def pull_ollama_model(model_name):
    print(f"[⬇️] Attempting to pull model '{model_name}'. This may take some time...")
    try:
        pull_process = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=False,
            text=True,
            check=True
        )
        print(f"[✅] Model '{model_name}' pulled successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[❌] Failed to pull model '{model_name}'. Error: {e}")
        print("Please check your internet connection or try 'ollama pull' manually.")
        return False
    except FileNotFoundError:
        print("[❌] 'ollama' command not found. Make sure Ollama is installed and in your PATH.")
        return False
    except Exception as e:
        print(f"[❌] An unexpected error occurred during model pull: {e}")
        return False

def ensure_model_available(model_name):
    if not model_name:
        print("[❌] No model specified.")
        return False
    print(f"[⚙️] Checking if model '{model_name}' is available...")
    available_models = get_available_ollama_models()
    if model_name in available_models:
        print(f"[✅] Model '{model_name}' is available.")
        return True
    else:
        print(f"[⚠️] Model '{model_name}' not found locally. Attempting to pull...")
        return pull_ollama_model(model_name)

def send_to_ollama(prompt, model_name, watch_mode=False):
    status_message_prefix = " [🤖] Querying Ollama for documentation..."
    if not watch_mode:
        sys.stdout.write(status_message_prefix + ' ' * 40 + '\r')
        sys.stdout.flush()
    else:
        sys.stdout.write(status_message_prefix + '\n')
        sys.stdout.flush()
        sys.stdout.write("--- Ollama Raw Output Start ---\n")
        sys.stdout.write(f"Prompt sent:\n---\n{prompt}\n---\n")
        sys.stdout.flush()
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": True
    }
    output = ""
    try:
        response = requests.post(OLLAMA_GENERATE_URL, json=payload, stream=True, timeout=300)
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                try:
                    data = json.loads(decoded)
                    if data.get("done"):
                        break
                    response_part = data.get("response", "")
                    output += response_part
                    if watch_mode:
                        sys.stdout.write(response_part)
                        sys.stdout.flush()
                except json.JSONDecodeError:
                    sys.stdout.write(f"\n[⚠️] Could not decode JSON line: {decoded}\n")
                    sys.stdout.flush()
                    output += decoded
        if not watch_mode:
            sys.stdout.write(f"\r{status_message_prefix} [✅] Ollama response received.\n")
            sys.stdout.flush()
        else:
            sys.stdout.write("\n--- Ollama Raw Output End ---\n")
            sys.stdout.write("[✅] Ollama response received.\n")
            sys.stdout.flush()
        return output.strip()
    except requests.exceptions.ConnectionError as e:
        sys.stdout.write(f"\r{status_message_prefix} [❌] Error connecting to Ollama: {e}\n")
        sys.stdout.flush()
        return None
    except requests.exceptions.Timeout:
        sys.stdout.write(f"\r{status_message_prefix} [❌] Ollama request timed out after {300} seconds.\n")
        sys.stdout.flush()
        return None
    except requests.exceptions.RequestException as e:
        sys.stdout.write(f"\r{status_message_prefix} [❌] Ollama API Request Error: {e}\n")
        sys.stdout.flush()
        return None
    except Exception as e:
        sys.stdout.write(f"\r{status_message_prefix} [❌] An unexpected error occurred while querying Ollama: {e}\n")
        sys.stdout.flush()
        return None
