from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.vectorstores import VectorStoreRetriever

from agents.base_agent import BaseAgent
from config import Settings


def _format_docs(docs: list) -> str:
    return "\n\n---\n\n".join(d.page_content for d in docs)


class RAGAgent(BaseAgent):
    """Base class for agents that retrieve context before generating.

    Subclasses call _build_rag_str_chain() or _build_rag_json_chain()
    in their __init__ to get a chain that automatically retrieves and
    injects relevant context into the prompt.
    """

    def __init__(
        self,
        llm: BaseChatModel,
        settings: Settings,
        retriever: VectorStoreRetriever,
    ) -> None:
        super().__init__(llm, settings)
        self._retriever = retriever

    def _build_rag_str_chain(self, system_template: str):
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template + "\n\nRelevant retrieved context:\n{context}"),
            ("human", "{question}"),
        ])
        chain = (
            {"context": self._retriever | _format_docs, "question": RunnablePassthrough()}
            | prompt
            | self._llm
            | StrOutputParser()
        )
        return chain.with_retry(stop_after_attempt=self._settings.agent_max_retries)

    def _build_rag_json_chain(self, system_template: str):
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template + "\n\nRelevant retrieved context:\n{context}"),
            ("human", "{question}"),
        ])
        chain = (
            {"context": self._retriever | _format_docs, "question": RunnablePassthrough()}
            | prompt
            | self._llm
            | JsonOutputParser()
        )
        return chain.with_retry(stop_after_attempt=self._settings.agent_max_retries)
