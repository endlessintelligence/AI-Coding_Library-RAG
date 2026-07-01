# llm/adapter.py - ChatService → LangChain BaseChatModel 适配器（预留）

from typing import Any, Iterator, List, Optional
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from model import get_chat_service


class LangChainChatModel(BaseChatModel):
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service = get_chat_service()

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        formatted = self._format_messages(messages)
        content = self._service.chat(formatted)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs) -> Iterator[ChatGeneration]:
        formatted = self._format_messages(messages)
        for chunk in self._service.chat_stream(formatted):
            yield ChatGeneration(message=AIMessage(content=chunk))

    def _format_messages(self, messages):
        formatted = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                formatted.append({"role": "system", "content": msg.content})
            else:
                formatted.append({"role": "user", "content": msg.content})
        return formatted

    @property
    def _llm_type(self) -> str:
        return "custom-qwen-chat"
