# model/chat.py - LLM 调用核心（同步+流式，对接阿里云百炼 qwen-max）

import os, time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class ChatService:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("MODEL_API_KEY"),
            base_url=os.getenv("MODEL_BASE_URL"),
        )
        self.model = os.getenv("MODEL_NAME", "qwen-max")
        self.timeout = int(os.getenv("MODEL_TIMEOUT", "60"))
        self.max_retries = int(os.getenv("MODEL_MAX_RETRIES", "3"))
        self.temperature = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
        self.max_tokens = int(os.getenv("MODEL_MAX_TOKENS", "2048"))

    def chat(self, messages, temperature=None, max_tokens=None):
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature or self.temperature,
                    max_tokens=max_tokens or self.max_tokens,
                    timeout=self.timeout,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                else:
                    raise e

    def chat_stream(self, messages, temperature=None, max_tokens=None):
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
            timeout=self.timeout,
            stream=True,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content


_service_instance = None


def get_chat_service():
    global _service_instance
    if _service_instance is None:
        _service_instance = ChatService()
    return _service_instance
