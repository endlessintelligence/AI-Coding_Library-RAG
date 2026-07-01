# graph/agent.py - LangGraph 状态图（Master → 规则/资源/人员管理/FAQ）

from typing import TypedDict
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.master import run as master_run
from agents.rules import run as rules_run
from agents.resources import run as resources_run
from agents.personnel import run as personnel_run
from agents.faq import run as faq_run

WEEKDAY_NAMES = ["周一","周二","周三","周四","周五","周六","周日"]


class AgentState(TypedDict):
    user_question: str
    route_decision: str
    route_reason: str
    agent_output: str
    final_answer: str


def _with_time(question: str) -> str:
    now = datetime.now()
    wd = WEEKDAY_NAMES[now.weekday()]
    return f"[当前时间：{wd} {now.hour}:{now.minute:02d}] {question}"


def master_node(state: AgentState) -> dict:
    decision, reason = master_run(_with_time(state["user_question"]))
    return {"route_decision": decision, "route_reason": reason,
            "agent_output": "", "final_answer": ""}


def rules_node(state: AgentState) -> dict:
    output = rules_run(_with_time(state["user_question"]))
    return {"agent_output": output}


def resources_node(state: AgentState) -> dict:
    output = resources_run(_with_time(state["user_question"]))
    return {"agent_output": output}


def personnel_node(state: AgentState) -> dict:
    output = personnel_run(_with_time(state["user_question"]))
    return {"agent_output": output}


def faq_node(state: AgentState) -> dict:
    output = faq_run(_with_time(state["user_question"]))
    return {"agent_output": output}


def summarize_node(state: AgentState) -> dict:
    return {"final_answer": state.get("agent_output", "")}


def route_after_master(state: AgentState) -> str:
    route_map = {
        "RULES": "rules",
        "RESOURCES": "resources",
        "PERSONNEL": "personnel",
        "FAQ": "faq",
    }
    return route_map.get(state.get("route_decision", "FAQ"), "faq")


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("master", master_node)
    builder.add_node("rules", rules_node)
    builder.add_node("resources", resources_node)
    builder.add_node("personnel", personnel_node)
    builder.add_node("faq", faq_node)
    builder.add_node("summarize", summarize_node)

    builder.set_entry_point("master")
    builder.add_conditional_edges("master", route_after_master, {
        "rules": "rules", "resources": "resources",
        "personnel": "personnel", "faq": "faq",
    })
    builder.add_edge("rules", "summarize")
    builder.add_edge("resources", "summarize")
    builder.add_edge("personnel", "summarize")
    builder.add_edge("faq", "summarize")
    builder.add_edge("summarize", END)

    return builder.compile(checkpointer=MemorySaver())


_graph_instance = None


def get_graph() -> StateGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance
