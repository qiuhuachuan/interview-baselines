"""Orchestration for the three-stage MAGI interview pipeline."""

import json
from copy import deepcopy

from agent.magi_modules.judgment_agent import JUDGMENT_AGENT_PROMPT
from agent.magi_modules.navigation_agent import NAVIGATION_AGENT_PROMPT
from agent.magi_modules.question_agent import QUESTION_AGENT_PROMPT
from llm_api import get_llm_content

INITIAL_NODE_ID = "GLOBAL.chief_complaint"
INITIAL_QUESTION_GOAL = "了解来访者当前最主要的困扰"
MAX_STATE_NODES = 300


def initial_magi_state():
    """Return a fresh, JSON-serializable MAGI interview state."""
    return {
        "current_node_id": INITIAL_NODE_ID,
        "question_goal": INITIAL_QUESTION_GOAL,
        "assistant_question": "最近最困扰你的问题是什么？",
        "nodes": {},
        "additional_flags": [],
        "risk_flags": {},
        "turn_count": 0,
    }


def run_magi_interview(history, state=None, model="deepseek-v4-flash"):
    """Run Judgment -> Navigation -> Question for one user response."""
    if not history or history[-1].get("role") != "user":
        raise ValueError("MAGI 访谈需要以来访者的回答作为最后一条消息")

    current_state = _validate_state(state)
    user_answer = history[-1]["content"]

    judgment_payload = {
        "current_node_id": current_state["current_node_id"],
        "question_goal": current_state["question_goal"],
        "assistant_question": current_state["assistant_question"],
        "user_answer": user_answer,
        "conversation_history": history,
        "current_state": current_state,
    }
    judgment = _call_json_agent(
        JUDGMENT_AGENT_PROMPT, judgment_payload, model, "Judgment Agent"
    )
    _apply_judgment(current_state, judgment)

    navigation_payload = {
        "conversation_history": history,
        "current_state": current_state,
        "current_node": current_state["current_node_id"],
        "last_user_response": user_answer,
        "last_judgment": judgment,
        "global_constraints": {
            "max_interview_turns": 40,
            "must_cover_core_modules": True,
            "allow_early_end": False,
            "safety_has_highest_priority": True,
        },
    }
    navigation = _call_json_agent(
        NAVIGATION_AGENT_PROMPT, navigation_payload, model, "Navigation Agent"
    )
    navigation = _enforce_navigation_safety(navigation, judgment)
    _apply_navigation(current_state, navigation)

    question_payload = {
        "conversation_history": history,
        "navigation_decision": navigation,
        "current_state": current_state,
        "style_constraints": {
            "language": "Chinese",
            "tone": "warm_structured",
            "max_questions_per_turn": 1,
        },
    }
    question = get_llm_content(
        [
            {"role": "system", "content": QUESTION_AGENT_PROMPT},
            {"role": "user", "content": json.dumps(question_payload, ensure_ascii=False)},
        ],
        model,
    ).strip()

    ended = bool(navigation.get("end")) or navigation.get("decision") == "END"
    ended = ended or question.lower().strip(" .。") in {"[end]", "[interview_complete]"}
    current_state["turn_count"] += 1
    current_state["assistant_question"] = "" if ended else question

    return {
        "message": "" if ended else question,
        "ended": ended,
        "state": current_state,
    }


def _call_json_agent(system_prompt, payload, model, agent_name):
    content = get_llm_content(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        model,
    )
    result = _parse_json_object(content, agent_name)
    if not isinstance(result, dict):
        raise RuntimeError(f"{agent_name} 未返回 JSON 对象")
    return result


def _parse_json_object(content, agent_name="Agent"):
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    if start < 0:
        raise RuntimeError(f"{agent_name} 未返回有效 JSON")
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{agent_name} 返回的 JSON 无法解析") from exc
    return value


def _validate_state(state):
    if state is None:
        return initial_magi_state()
    if not isinstance(state, dict):
        raise ValueError("MAGI 访谈状态格式不正确")
    clean = initial_magi_state()
    for key in ("current_node_id", "question_goal", "assistant_question"):
        value = state.get(key)
        if isinstance(value, str) and len(value) <= 2000:
            clean[key] = value
    nodes = state.get("nodes", {})
    if not isinstance(nodes, dict) or len(nodes) > MAX_STATE_NODES:
        raise ValueError("MAGI 节点状态格式不正确")
    clean["nodes"] = deepcopy(nodes)
    flags = state.get("additional_flags", [])
    clean["additional_flags"] = deepcopy(flags[-100:]) if isinstance(flags, list) else []
    risks = state.get("risk_flags", {})
    clean["risk_flags"] = deepcopy(risks) if isinstance(risks, dict) else {}
    turns = state.get("turn_count", 0)
    clean["turn_count"] = turns if isinstance(turns, int) and 0 <= turns <= 40 else 0
    return clean


def _apply_judgment(state, judgment):
    node_id = judgment.get("current_node_id") or state["current_node_id"]
    status = judgment.get("node_status", "UNCERTAIN")
    if status not in {"YES", "NO", "PARTIAL", "UNCERTAIN", "NOT_ASKED", "N/A"}:
        status = "UNCERTAIN"
    state["nodes"][node_id] = {
        "status": status,
        "evidence_brief": str(judgment.get("evidence_brief", ""))[:1000],
    }
    flags = judgment.get("additional_flags")
    if isinstance(flags, list):
        state["additional_flags"] = (state["additional_flags"] + flags)[-100:]
    risks = judgment.get("risk_flags")
    if isinstance(risks, dict):
        for key, value in risks.items():
            if value:
                state["risk_flags"][key] = True


def _apply_navigation(state, navigation):
    updates = navigation.get("state_updates")
    if isinstance(updates, list):
        for update in updates:
            if not isinstance(update, dict) or not isinstance(update.get("node_id"), str):
                continue
            state["nodes"][update["node_id"]] = {
                "status": update.get("status", "UNCERTAIN"),
                "evidence_brief": str(update.get("evidence_brief", ""))[:1000],
            }
    next_node = navigation.get("next_node_id")
    if isinstance(next_node, str) and next_node:
        state["current_node_id"] = next_node
    goal = navigation.get("question_goal")
    if isinstance(goal, str) and goal:
        state["question_goal"] = goal


def _enforce_navigation_safety(navigation, judgment):
    decisions = {
        "ASK_NODE",
        "CLARIFY",
        "SKIP_MODULE",
        "SWITCH_MODULE",
        "CRISIS_PROTOCOL",
        "END",
    }
    risk_flags = judgment.get("risk_flags", {})
    if isinstance(risk_flags, dict) and risk_flags.get("imminent_risk"):
        return {
            "agent": "navigation",
            "decision": "CRISIS_PROTOCOL",
            "next_node_id": "B.CRISIS_PROTOCOL",
            "next_module": "B",
            "question_goal": "优先保障来访者即时安全，并鼓励联系现实中的紧急支持",
            "priority": "urgent",
            "required_answer_type": "safety_check",
            "state_updates": [],
            "constraints_for_question_agent": {
                "max_questions": 1,
                "tone": "calm_direct_supportive",
                "must_avoid": ["diagnosis", "method_details"],
            },
            "end": False,
        }
    if navigation.get("decision") not in decisions:
        raise RuntimeError("Navigation Agent 返回了无效决策")
    return navigation
