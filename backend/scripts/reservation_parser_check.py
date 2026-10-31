"""自然语言会议室预约解析自检。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.reservation import parse_reservation_text  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

SAMPLES = [
    "帮我订下周五上午10点到12点的杭州西湖商务中心西湖 A 会议室，10人，需要视频会议",
    "明天下午2点到4点，杭州西湖商务中心西湖 B 会议室，2个人",
    "下周三上午9点半到11点半订两间上海外滩云舍会议空间外滩1号，12人",
    "9 月 24 号下午3点到5点，深圳湾创新中心南山 A 会议室，18人",
    "预约成都宽窄巷子共享会议室宽巷子1号，下周六下午1点到3点，8人",
]


def main() -> None:
    with SessionLocal() as db:
        for text in SAMPLES:
            parsed = parse_reservation_text(db, text)
            print(text)
            print(
                f"  空间={parsed['venue_name'] or '未识别'}"
                f" | 会议室={parsed['meeting_room_name'] or '未识别'}"
                f" | 开始={parsed['start_at'] or '未识别'}"
                f" | 结束={parsed['end_at'] or '未识别'}"
                f" | 时长={parsed['hours']}"
                f" | 间数={parsed['rooms']}"
                f" | 人数={parsed['attendees']}"
                f" | 设备需求={parsed['equipment_request'] or '无'}"
            )


if __name__ == "__main__":
    main()
