"""Scheduler for personalized reports — runs hourly to check users needing reports."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def schedule_personalized_reports(scheduler, app):
    """Register a cron job to check and generate personalized reports."""

    def _run():
        try:
            with app.app_context():
                from app.models.user import User
                from app.models.user_profile import UserProfile
                from analysis.personalized.generator import generate_personal_report

                now_hhmm = datetime.now(tz=ZoneInfo('Asia/Shanghai')).strftime('%H:%M')
                profiles = UserProfile.query.join(User).filter(
                    User.tier.in_(['v2', 'v3', 'v4', 'v5']),
                    User.enabled == True,
                    UserProfile.report_time == now_hhmm,
                ).all()

                if not profiles:
                    return

                logger.info(f"Generating personalized reports for {len(profiles)} users at {now_hhmm}")

                for profile in profiles:
                    try:
                        result = generate_personal_report(profile.user_id, app)
                        if result:
                            # Try sending email notification
                            _try_send_email(profile.user_id, result, app)
                    except Exception as e:
                        logger.error(f"Failed to generate report for user {profile.user_id}: {e}")
        except Exception as e:
            logger.error(f"Personalized report scheduler error: {e}")

    scheduler.add_job(_run, 'cron', minute=0, id='personalized_reports', replace_existing=True)
    logger.info("Personalized report scheduler registered (hourly at :00)")
    return scheduler


def _try_send_email(user_id, report_result, app):
    """Try to send email notification for a generated personal report."""
    try:
        from app.models.user import User
        from app.models.subscription import Subscription

        user = User.query.get(user_id)
        if not user or not user.email:
            return

        # Check if user has email subscription
        subs = Subscription.query.filter_by(user_id=user_id, enabled=True).all()
        if not subs:
            return

        from app.services.email_sender import send_daily_report
        base_url = app.config.get('SERVER_URL', 'http://localhost:18923')
        h5_url = f"{base_url}/r/{report_result['report_id']}"
        if report_result.get('access_token'):
            h5_url += f"?token={report_result['access_token']}"

        today = datetime.now().strftime('%Y-%m-%d')
        for sub in subs:
            if sub.email:
                send_daily_report(
                    to=sub.email,
                    display_name=user.display_name or user.email,
                    report_date=today,
                    highlights=report_result.get('highlights', []),
                    h5_url=h5_url,
                )
    except Exception as e:
        logger.warning(f"Email notification failed for user {user_id}: {e}")
