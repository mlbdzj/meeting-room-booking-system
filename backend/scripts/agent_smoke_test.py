r"""智能助手冒烟测试：直接用真实数据库与大模型（如已配置）跑几条典型问题。

用法：
    cd backend
    .\.venv\Scripts\python.exe scripts\agent_smoke_test.py   # 使用 .env / 环境变量中的配置
    $env:AGENT_PROVIDER='local'                              # 强制使用本地知识库引擎
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.agent.engine import answer_question  # noqa: E402
from app.agent.llm import resolve_provider  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import ChatMessage, User  # noqa: E402

QUESTIONS = [
    "有哪些会议空间可以预约？",
    "杭州西湖商务中心下周五上午还有会议室吗？",
    "我的预约现在是什么状态？",
    "会议空间的开放时间和计费规则是什么？",
    "帮我订下周五上午10点到12点的杭州西湖商务中心西湖 A 会议室，10人",
]


def main() -> None:
    provider = resolve_provider()
    print(f"当前模式：{'大模型 ' + provider['model'] if provider else '本地知识库引擎'}\n")

    with SessionLocal() as db:
        for username in ("student", "admin"):
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                print(f"未找到用户 {username}，跳过")
                continue
            print(f"===== 以「{user.name}（{user.role}）」提问 =====")
            history: list[ChatMessage] = []
            for question in QUESTIONS:
                result = answer_question(db, user, question, history)
                print(f"[{question}]  来源={result['source']}  工具={result.get('tools', [])}")
                print(result["content"])
                if result.get("action"):
                    print(f"  ↳ 预约草稿：[{result['action']['status']}] {result['action']['summary']}")
                print("-" * 60)
                history.append(ChatMessage(session_id=0, role="user", content=question))
                history.append(ChatMessage(session_id=0, role="assistant", content=result["content"]))
            print()


if __name__ == "__main__":
    main()
