"""
Analytics routes — weekly statistics from real PostgreSQL data.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models.models import (
    User, Message, AnswerFeedback, PendingQuestion,
    Lesson, LessonUsage, FeedbackType, PendingQuestionStatus,
    MessageRole
)
from app.schemas.lessons import AnalyticsSummary, WeeklyStats
from app.utils.auth import get_current_active_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    bid = str(current_user.business_id)

    # 1 single round-trip for all summary metrics
    summary_sql = text("""
        SELECT
            (SELECT COUNT(*) FROM messages WHERE business_id = :bid AND role = 'assistant') AS total_ai,
            (SELECT COUNT(*) FROM messages WHERE business_id = :bid AND role = 'owner') AS total_owner,
            (SELECT COUNT(*) FROM pending_questions WHERE business_id = :bid AND status = 'resolved' AND owner_answer IS NOT NULL) AS total_owner_pq,
            (SELECT COUNT(*) FROM messages WHERE business_id = :bid AND role = 'user') AS total_q,
            (SELECT COUNT(*) FROM answer_feedback WHERE business_id = :bid AND feedback_type = 'good') AS good,
            (SELECT COUNT(*) FROM answer_feedback WHERE business_id = :bid AND feedback_type = 'bad') AS bad,
            (SELECT COUNT(*) FROM pending_questions WHERE business_id = :bid AND status = 'open') AS pending,
            (SELECT COUNT(*) FROM lessons WHERE business_id = :bid) AS lessons_created,
            (SELECT COUNT(*) FROM lesson_usage WHERE business_id = :bid) AS lessons_used
    """)
    res = await db.execute(summary_sql, {"bid": bid})
    row = res.fetchone()

    total_ai = row.total_ai or 0
    total_owner = max(row.total_owner or 0, row.total_owner_pq or 0)
    total_q = row.total_q or 0
    good = row.good or 0
    bad = row.bad or 0
    pending = row.pending or 0
    lessons_created = row.lessons_created or 0
    lessons_used = row.lessons_used or 0

    # Fast weekly trends
    weekly_trends = await _get_weekly_trends_fast(db, bid)

    return AnalyticsSummary(
        total_questions=total_q,
        total_ai_answers=total_ai,
        total_owner_answers=total_owner,
        good_answers=good,
        bad_answers=bad,
        pending_questions=pending,
        lessons_created=lessons_created,
        lessons_used=lessons_used,
        weekly_trends=weekly_trends,
    )


async def _get_weekly_trends_fast(db: AsyncSession, business_id: str) -> list:
    """Generate weekly stats for the last 8 weeks efficiently."""
    now = datetime.now(timezone.utc)
    eight_weeks_ago = (now - timedelta(weeks=8)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Pre-fetch weekly aggregates in grouped queries
    msg_sql = text("""
        SELECT 
            date_trunc('week', created_at) AS wk,
            SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS total_q,
            SUM(CASE WHEN role = 'assistant' THEN 1 ELSE 0 END) AS ai_ans,
            SUM(CASE WHEN role = 'owner' THEN 1 ELSE 0 END) AS owner_ans
        FROM messages
        WHERE business_id = :bid AND created_at >= :start
        GROUP BY 1
    """)
    fb_sql = text("""
        SELECT 
            date_trunc('week', created_at) AS wk,
            SUM(CASE WHEN feedback_type = 'good' THEN 1 ELSE 0 END) AS good,
            SUM(CASE WHEN feedback_type = 'bad' THEN 1 ELSE 0 END) AS bad
        FROM answer_feedback
        WHERE business_id = :bid AND created_at >= :start
        GROUP BY 1
    """)
    pq_sql = text("""
        SELECT 
            date_trunc('week', created_at) AS wk,
            COUNT(*) AS pend
        FROM pending_questions
        WHERE business_id = :bid AND created_at >= :start
        GROUP BY 1
    """)
    l_sql = text("""
        SELECT 
            date_trunc('week', created_at) AS wk,
            COUNT(*) AS lc
        FROM lessons
        WHERE business_id = :bid AND created_at >= :start
        GROUP BY 1
    """)
    lu_sql = text("""
        SELECT 
            date_trunc('week', created_at) AS wk,
            COUNT(*) AS lu
        FROM lesson_usage
        WHERE business_id = :bid AND created_at >= :start
        GROUP BY 1
    """)

    params = {"bid": business_id, "start": eight_weeks_ago}
    msg_rows = (await db.execute(msg_sql, params)).fetchall()
    fb_rows = (await db.execute(fb_sql, params)).fetchall()
    pq_rows = (await db.execute(pq_sql, params)).fetchall()
    l_rows = (await db.execute(l_sql, params)).fetchall()
    lu_rows = (await db.execute(lu_sql, params)).fetchall()

    def to_map(rows, *keys):
        m = {}
        for r in rows:
            if r.wk:
                k = r.wk.strftime("%Y-%m-%d")
                m[k] = {key: getattr(r, key, 0) or 0 for key in keys}
        return m

    msg_map = to_map(msg_rows, "total_q", "ai_ans", "owner_ans")
    fb_map = to_map(fb_rows, "good", "bad")
    pq_map = to_map(pq_rows, "pend")
    l_map = to_map(l_rows, "lc")
    lu_map = to_map(lu_rows, "lu")

    weeks = []
    for i in range(7, -1, -1):
        week_start = (now - timedelta(weeks=i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=now.weekday())
        k = week_start.strftime("%Y-%m-%d")

        weeks.append(WeeklyStats(
            week_start=k,
            total_questions=msg_map.get(k, {}).get("total_q", 0),
            ai_answered=msg_map.get(k, {}).get("ai_ans", 0),
            owner_answered=msg_map.get(k, {}).get("owner_ans", 0),
            good_answers=fb_map.get(k, {}).get("good", 0),
            bad_answers=fb_map.get(k, {}).get("bad", 0),
            pending=pq_map.get(k, {}).get("pend", 0),
            lessons_created=l_map.get(k, {}).get("lc", 0),
            lessons_used=lu_map.get(k, {}).get("lu", 0),
        ))

    return weeks
