"""A print-friendly HTML page of a plan (one section per day)."""

from html import escape

from dongseon.export.plan import PlanExport, day_route_urls, directions_url

WEEKDAYS = "월화수목금토일"

_STYLE = """
body{font-family:-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;margin:24px;color:#111;font-size:13px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 6px;border-bottom:2px solid #0f766e;padding-bottom:4px}
p.meta{color:#555;margin:0 0 12px}table{width:100%;border-collapse:collapse}
td,th{border-bottom:1px solid #ddd;padding:6px 4px;text-align:left;vertical-align:top}
th{font-size:11px;color:#555}td.t{white-space:nowrap;font-variant-numeric:tabular-nums;width:88px}
td.l{white-space:nowrap}.local{color:#555}.warn{color:#92400e}.links a{margin-right:8px}a{color:#0f766e}
section{break-inside:avoid-page}@media print{body{margin:0}a{color:#111;text-decoration:none}.noprint{display:none}}
"""


def build_print_html(plan: PlanExport) -> str:
    """Render the plan as a standalone HTML page (no scripts, no map, no Google content)."""
    t = plan.trip
    out = [
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{escape(t.title)} 일정 v{plan.version}</title><style>{_STYLE}</style></head><body>",
        f"<h1>{escape(t.title)}</h1>",
        f"<p class='meta'>{t.start_date:%Y-%m-%d} ~ {t.end_date:%Y-%m-%d} · 일정 v{plan.version} · "
        "시각은 모두 추정입니다. 실제 이동과 영업시간은 Google 지도에서 확인하세요.</p>",
        "<p class='noprint'><button onclick='window.print()'>인쇄</button></p>",
    ]
    for n, day in enumerate(plan.days, start=1):
        out.append("<section>")
        out.append(
            f"<h2>{n}일차 · {day.day.month}/{day.day.day} ({WEEKDAYS[day.day.weekday()]})"
            + (f" <small>· {escape(day.depot)}에서 출발</small>" if day.depot else "")
            + "</h2>"
        )
        if not day.stops:
            out.append("<p>일정 없음</p></section>")
            continue
        out.append("<table><tr><th>시각</th><th>장소</th><th>메모</th><th>길찾기</th></tr>")
        for s in day.stops:
            name = escape(s.label)
            if s.local_name:
                name += f" <span class='local'>{escape(s.local_name)}</span>"
            if s.area:
                name += f" <span class='local'>· {escape(s.area)}</span>"
            memo = escape(s.note or "")
            if s.warnings:
                memo += "".join(f"<div class='warn'>⚠️ {escape(w)}</div>" for w in s.warnings)
            link = escape(directions_url(s.label, s.google_place_id))
            out.append(
                f"<tr><td class='t'>{s.start:%H:%M}~{s.end:%H:%M}</td><td>{name}</td><td>{memo}</td>"
                f"<td class='l'><a href='{link}'>Google 지도</a></td></tr>"
            )
        out.append("</table>")
        routes = day_route_urls(day.stops)
        out.append(
            "<p class='links'>이날 경로: "
            + "".join(f"<a href='{escape(u)}'>경로 {i}</a>" for i, u in enumerate(routes, start=1))
            + "</p></section>"
        )
    out.append("</body></html>")
    return "".join(out)
