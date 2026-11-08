"""Google My Maps import files: one CSV per day in a zip. My Maps places rows by the "위치" column text.

No coordinates go into the files (Google coordinates may not be exported), so My Maps geocodes each row itself.
"""

import csv
import io
import zipfile

from dongseon.export.plan import PlanExport

HEADER = ["순서", "시각", "이름", "현지 이름", "동네", "메모", "위치"]


def day_csv(plan: PlanExport, index: int) -> str:
    """The CSV text for one day (``index`` into ``plan.days``)."""
    day = plan.days[index]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HEADER)
    for s in day.stops:
        where = s.local_name or s.label
        w.writerow(
            [
                s.seq,
                f"{s.start:%H:%M}~{s.end:%H:%M}",
                s.label,
                s.local_name or "",
                s.area or "",
                s.note or "",
                ", ".join(x for x in (where, s.area, plan.city.name_en or plan.city.name) if x),
            ]
        )
    return buf.getvalue()


def file_name(plan: PlanExport, index: int) -> str:
    """``day1_1228.csv`` style names, so the layers sort by day."""
    return f"day{index + 1}_{plan.days[index].day:%m%d}.csv"


def build_zip(plan: PlanExport) -> bytes:
    """Zip one CSV per day that has stops, plus a short how-to."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, day in enumerate(plan.days):
            if day.stops:
                z.writestr(file_name(plan, i), day_csv(plan, i))
        z.writestr(
            "README.txt",  # ASCII name: some unzip tools garble non-ASCII names
            "Google 내 지도(https://www.google.com/maps/d/)에서 새 지도를 만들고, 레이어마다 '가져오기'로 "
            "날짜별 CSV를 하나씩 올리세요.\n"
            "위치 열: '위치', 제목 열: '이름'을 고르면 내 지도가 이름으로 장소를 찾습니다. "
            "잘못 찾은 곳은 내 지도에서 직접 옮겨 주세요.\n"
            f"시각은 dongseon 일정 v{plan.version}의 추정입니다.\n",
        )
    return buf.getvalue()
