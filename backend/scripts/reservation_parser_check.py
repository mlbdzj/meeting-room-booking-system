"""自然语言预约解析自检：打印几组口语描述的解析结果，便于调整规则。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.reservation import parse_reservation_text  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

SAMPLES = [
    "帮我订下周五使用开始两晚的杭州西湖智选假日会议空间高级大床房，2个人，需要安静楼层",
    "下周三使用开始，住 3 晚，上海外滩云舍会议空间江景双床房，2 位客人",
    "帮我预约明天使用开始 1 晚的成都宽窄巷子花园会议空间家庭房，4 个人",
    "9 月 24 号使用开始、26 号使用结束，三亚亚龙湾海景度假会议空间海景大床房，2 人",
    "帮我订两间杭州西湖智选假日会议空间的高级双床房，下周六使用开始三晚，一共 4 个人",
]


def main() -> None:
    with SessionLocal() as db:
        for text in SAMPLES:
            parsed = parse_reservation_text(db, text)
            print(text)
            print(
                f"  会议空间={parsed['venue_name'] or '未识别'}"
                f" | 会议室类型={parsed['meeting_room_name'] or '未识别'}"
                f" | 使用开始={parsed['start_at'] or '未识别'}"
                f" | 使用结束={parsed['end_at'] or '未识别'}"
                f" | 晚数={parsed['hours']}"
                f" | 间数={parsed['rooms']}"
                f" | 人数={parsed['attendees']}"
                f" | 特殊要求={parsed['equipment_request'] or '无'}"
            )


if __name__ == "__main__":
    main()
