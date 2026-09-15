import json
from openai import OpenAI
from requests.exceptions import ConnectionError, Timeout, RequestException
import os

# Set OpenAI api and url
# Adapting to standard env vars if not present
api_key = os.getenv('OPENAI_API_KEY') or os.getenv('LLM_API_KEY', '')
api_base = os.getenv('OPENAI_BASE_URL') or os.getenv('LLM_BASE_URL', '')

# If not set, try to read from a local config provided by the main wrapper?
# For now, rely on Env vars being set by the runner.

os.environ['OPENAI_API_KEY'] = api_key
if api_base:
    os.environ['OPENAI_API_BASE'] = api_base
    os.environ['OPENAI_BASE_URL'] = api_base # Newer lib uses this

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def load_jsonl(file_path):
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
    return data

def save_json(data, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_completion(prompt, history, flag):
    # Mock mode for testing without keys
    if api_key == "sk-dummy" or os.getenv('CI_TEST_MODE'):
        return "10分；完全匹配", history

    # Allow overriding model via env var
    model_name = os.getenv('EVAL_MODEL_NAME', "gpt-4o-2024-08-06")
    
    client = OpenAI(api_key=api_key,
                    base_url=api_base if api_base else None)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            SYSTEM_PROMPT = """你是一个得力的助手。"""
            messages = []
            messages.append({'role': 'system', "content": SYSTEM_PROMPT})
            if history != []:
                for h in history:
                    messages.append({'role':'user',"content":h[0]})
                    messages.append({'role':'assistant',"content":h[1]})
            else:
                messages.append({'role':'user',"content":prompt})
        
            if flag == 1:
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                    temperature=0
                    )
            else:
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    max_tokens=4096,
                    temperature=0
                    )
            
            response = chat_completion.choices[0].message.content
            # Note: The original code appended to history but returned a tuple. 
            # We preserve this behavior although it side-effects the passed history list.
            history.append((prompt, response))
            return response, history
        
        except (ConnectionError, Timeout) as e:
            print(f"Network error occurred: {e}. Retrying {attempt + 1}/{max_retries}...")
            if attempt == max_retries - 1:
                # Return empty string or handle error gracefully instead of crashing everything?
                # Original raises, we'll respect that.
                raise
                
        except RequestException as e:
            print(f"An error occurred: {e}.")
            raise 
        except Exception as e:
            print(f"General Error: {e}")
            # Raising here to ensure we don't silently fail evaluations
            raise
            
    return "Unable to get a response after several attempts."
