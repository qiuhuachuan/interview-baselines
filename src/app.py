"""Minimal HTTP server for the mental-health interview chat UI."""

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agent.dsm_interviewer import DSM_INTERVIEWER_SYSTEM_PROMPT
from agent.termination_intent_judge import (
    build_termination_judge_prompt,
    is_termination_intent,
)
from llm_api import get_llm_content

STATIC_DIR = Path(__file__).parent / "static"
MODEL = os.environ.get("LLM_MODEL", "deepseek-v4-flash")
MAX_MESSAGES = 40
MAX_MESSAGE_LENGTH = 4000


class InterviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 200_000:
                raise ValueError("请求大小不正确")
            payload = json.loads(self.rfile.read(length))
            history = self._validate_messages(payload.get("messages"))
            response = get_llm_content(
                [
                    {"role": "system", "content": DSM_INTERVIEWER_SYSTEM_PROMPT},
                    *history,
                ],
                MODEL,
            )
            judgement = get_llm_content(
                [{"role": "user", "content": build_termination_judge_prompt(response)}],
                MODEL,
            )
            ended = (
                is_termination_intent(judgement)
                or "[interview_complete]" in response.lower()
            )
            clean_response = response.replace("[INTERVIEW_COMPLETE]", "").strip()
            self._json_response(200, {"message": clean_response, "ended": ended})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json_response(400, {"error": str(exc)})
        except Exception as exc:
            print(f"LLM request failed: {exc}")
            self._json_response(502, {"error": "暂时无法连接访谈服务，请稍后再试。"})

    @staticmethod
    def _validate_messages(messages):
        if not isinstance(messages, list) or not messages:
            raise ValueError("对话内容不能为空")
        if len(messages) > MAX_MESSAGES:
            messages = messages[-MAX_MESSAGES:]
        clean = []
        for item in messages:
            if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
                raise ValueError("对话格式不正确")
            content = item.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("消息内容不能为空")
            if len(content) > MAX_MESSAGE_LENGTH:
                raise ValueError("单条消息不能超过 4000 字")
            clean.append({"role": item["role"], "content": content.strip()})
        if clean[-1]["role"] != "user":
            raise ValueError("最后一条消息必须来自来访者")
        return clean

    def _json_response(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def run():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), InterviewHandler)
    print(f"心理健康访谈系统已启动：http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
