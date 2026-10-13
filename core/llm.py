import json
import time
import os
import hashlib
from typing import List, Union
from pydantic import BaseModel
from core.schemas import Action, ToolCall, AskUser, FinalAnswer
from dotenv import load_dotenv

load_dotenv()

class GeminiProviderClient:
    def __init__(self, api_key: str = None, model: str = "gemini-flash-latest"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                pass

    def _call_api(self, messages, tools):
        if not self.client:
            return "{}"
        
        prompt_lines = [
            "You are an AI Business Intelligence agent in an iterative loop.",
            "You must respond with ONLY a single valid JSON object representing your next action.",
            'Choose ONE format:',
            '1. Tool Call: {"name": "<tool_name>", "args": {<tool_args>}, "thought": "<reasoning>"}',
            '2. Ask User: {"question": "<clarification_question>"}',
            '3. Final Answer: {"payload": {<final_answer_fields>}}',
            f"Available tools: {json.dumps(tools)}",
            "Conversation & Context history:"
        ]
        for m in messages:
            prompt_lines.append(f"{m.get('role', 'user').upper()}: {m.get('content', '')}")
            
        full_prompt = "\n".join(prompt_lines)
        
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config={"response_mime_type": "application/json"}
            )
            return resp.text.strip()
        except Exception as e:
            return json.dumps({"error": str(e)})

class LLMClient:
    def __init__(self, mode="live", cache_dir="data/llm_cache", provider_client=None, api_key=None, model="gemini-flash-latest"):
        self.mode = mode
        self.cache_dir = cache_dir
        if provider_client is not None:
            self.provider_client = provider_client
        elif api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            self.provider_client = GeminiProviderClient(api_key=api_key, model=model)
        else:
            self.provider_client = None
        os.makedirs(self.cache_dir, exist_ok=True)
        self.calls = 0

    def next_action(self, messages: list, tools: list) -> Action:
        prompt_hash = self._hash_prompt(messages, tools)
        cache_path = os.path.join(self.cache_dir, f"{prompt_hash}.json")
        
        if self.mode == "replay" and os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                return self._parse_json(f.read())
                
        if self.mode == "mock" and self.provider_client:
            return self.provider_client.next_action(messages, tools)

        # Backoff logic
        retries = 3
        for attempt in range(retries):
            try:
                raw_output = self._call_api(messages, tools)
                try:
                    action = self._parse_json(raw_output)
                except Exception:
                    # Repair attempt
                    messages.append({"role": "user", "content": "REPAIR: Invalid JSON."})
                    raw_output = self._call_api(messages, tools)
                    action = self._parse_json(raw_output)
                
                if self.mode == "record":
                    with open(cache_path, "w") as f:
                        f.write(raw_output)
                return action
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)

    def _call_api(self, messages, tools):
        if self.provider_client:
            return self.provider_client._call_api(messages, tools)
        return "{}"

    def _hash_prompt(self, messages, tools):
        data = json.dumps({"messages": messages, "tools": tools}, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    def _parse_json(self, text):
        data = json.loads(text)
        if isinstance(data, dict) and "error" in data and not ("summary" in data and "findings" in data):
            raise RuntimeError(f"LLM API Error: {data['error']}")
        if "name" in data and "args" in data:
            return ToolCall(**data)
        if "question" in data:
            return AskUser(**data)
        if "payload" in data:
            return FinalAnswer(**data)
        return FinalAnswer(payload=data)

class MockLLM(LLMClient):
    def __init__(self, script: List[Action]):
        super().__init__(mode="mock")
        self.provider_client = None
        self.script = script
        self.idx = 0

    def next_action(self, messages: list, tools: list) -> Action:
        if self.idx < len(self.script):
            action = self.script[self.idx]
            self.idx += 1
            return action
        return FinalAnswer(payload={"msg": "end of script"})

    def _call_api(self, messages, tools) -> str:
        action = self.next_action(messages, tools)
        if isinstance(action, BaseModel):
            return action.model_dump_json()
        elif isinstance(action, dict):
            return json.dumps(action)
        return json.dumps(getattr(action, "__dict__", {}))
