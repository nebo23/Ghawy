"""Baseline snapshot of the whole schema — the root of the history.

Revision ID: ghawy_baseline
Revises: (nothing — this is the root)
Create Date: 2026-09-03

Everything before this revision was written against a database that
``Base.metadata.create_all()`` had already built, so the history could only ever
be replayed on a database that already had the tables. This revision creates
them, so ``alembic upgrade head`` works on an empty database for the first time.

The snapshot is a *frozen* copy of the schema as production has it (verified by
diffing ``pg_dump --schema-only`` of production against this migration's
output). It is not regenerated from the models — later schema changes go in
later revisions, exactly as they should.

On a database that already has tables but was never stamped, this revision does
nothing at all and, crucially, does not write the marker, so the historical
revisions below it still run and bring that database up to date.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import MARKER_TABLE, table_exists


# revision identifiers, used by Alembic.
revision: str = 'ghawy_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if table_exists("users"):
        # Pre-existing database. It has the schema already and the revisions
        # after this one are the ones that know how to bring it forward.
        return
    op.create_table('birthday_gift_claims',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('decided_by', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_birthday_gift_claims_id'), 'birthday_gift_claims', ['id'], unique=False)
    op.create_index(op.f('ix_birthday_gift_claims_user_id'), 'birthday_gift_claims', ['user_id'], unique=False)
    op.create_table('categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('emoji', sa.String(), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_categories_id'), 'categories', ['id'], unique=False)
    op.create_table('coupons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('display_code', sa.String(length=64), nullable=True),
    sa.Column('discount_percent', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('max_redemptions', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_coupons_code'), 'coupons', ['code'], unique=True)
    op.create_index(op.f('ix_coupons_id'), 'coupons', ['id'], unique=False)
    op.create_table('courses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('thumbnail_url', sa.String(), nullable=True),
    sa.Column('pdf_url', sa.String(), nullable=True),
    sa.Column('certificate_url', sa.String(), nullable=True),
    sa.Column('total_lessons', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('course_time', sa.String(), nullable=True),
    sa.Column('is_published', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_courses_id'), 'courses', ['id'], unique=False)
    op.create_index(op.f('ix_courses_sort_order'), 'courses', ['sort_order'], unique=False)
    op.create_table('email_campaign_sends',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_campaign_sends_campaign_id'), 'email_campaign_sends', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_email_campaign_sends_email'), 'email_campaign_sends', ['email'], unique=False)
    op.create_index(op.f('ix_email_campaign_sends_id'), 'email_campaign_sends', ['id'], unique=False)
    op.create_table('guests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('company', sa.String(), nullable=True),
    sa.Column('bio', sa.Text(), nullable=True),
    sa.Column('avatar_url', sa.String(), nullable=True),
    sa.Column('avatar_initials', sa.String(length=5), nullable=True),
    sa.Column('avatar_color', sa.String(length=20), nullable=True),
    sa.Column('category', sa.String(), nullable=True),
    sa.Column('is_featured', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('sessions_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('attendees_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('rating', sa.Numeric(precision=3, scale=1), server_default=sa.text('0.0'), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_guests_id'), 'guests', ['id'], unique=False)
    op.create_table('legacy_emails',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_legacy_emails_email'), 'legacy_emails', ['email'], unique=True)
    op.create_index(op.f('ix_legacy_emails_id'), 'legacy_emails', ['id'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(), nullable=False),
    sa.Column('first_name', sa.String(), nullable=True),
    sa.Column('last_name', sa.String(), nullable=True),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('country', sa.String(), nullable=True),
    sa.Column('governorate', sa.String(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('is_verified', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('verification_code', sa.String(length=6), nullable=True),
    sa.Column('verification_expiry', sa.DateTime(), nullable=True),
    sa.Column('password_reset_code', sa.String(length=6), nullable=True),
    sa.Column('password_reset_expiry', sa.DateTime(), nullable=True),
    sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('is_owner', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('staff_permissions', sa.Text(), nullable=True),
    sa.Column('team_role', sa.String(length=40), nullable=True),
    sa.Column('avatar_url', sa.String(), nullable=True),
    sa.Column('bio', sa.Text(), nullable=True),
    sa.Column('level', sa.Integer(), server_default=sa.text('1'), nullable=True),
    sa.Column('xp', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('streak_days', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('badge', sa.String(), nullable=True),
    sa.Column('birth_date', sa.Date(), nullable=True),
    sa.Column('social_media_url', sa.String(), nullable=True),
    sa.Column('show_social_media', sa.Boolean(), server_default=sa.text('true'), nullable=True),
    sa.Column('onboarding_completed', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('selected_avatar', sa.String(), nullable=True),
    sa.Column('last_seen', sa.DateTime(), nullable=True),
    sa.Column('token_version', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('is_legacy_redeemed', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('legacy_promo_round', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('subscription_source', sa.String(length=64), nullable=True),
    sa.Column('custom_title', sa.String(length=120), nullable=True),
    sa.Column('winback_email_sent_at', sa.DateTime(), nullable=True),
    sa.Column('first_lesson_email_sent_at', sa.DateTime(), nullable=True),
    sa.Column('expiry5_email_sent_for', sa.DateTime(), nullable=True),
    sa.Column('birthday_email_sent_year', sa.Integer(), nullable=True),
    sa.Column('birthday_gift_year', sa.Integer(), nullable=True),
    sa.Column('inactive6_email_sent_at', sa.DateTime(), nullable=True),
    sa.Column('end_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('phone')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_table('admin_member_notes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('member_id', sa.Integer(), nullable=False),
    sa.Column('note', sa.Text(), server_default=sa.text("''"), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['member_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_member_notes_member_id'), 'admin_member_notes', ['member_id'], unique=True)
    op.create_table('ai_update_posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_type', sa.Enum('TEXT', 'VIDEO', 'PHOTO', 'POLL', name='aiupdateposttype'), nullable=False),
    sa.Column('category', sa.String(length=30), nullable=True),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('image_url', sa.String(), nullable=True),
    sa.Column('video_url', sa.String(), nullable=True),
    sa.Column('media', sa.JSON(), nullable=True),
    sa.Column('is_pinned', sa.Boolean(), nullable=True),
    sa.Column('like_count', sa.Integer(), nullable=True),
    sa.Column('comment_count', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_update_posts_id'), 'ai_update_posts', ['id'], unique=False)
    op.create_table('ai_update_reads',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('last_read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_ai_update_reads_id'), 'ai_update_reads', ['id'], unique=False)
    op.create_table('certificates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('course_id', sa.Integer(), nullable=True),
    sa.Column('certificate_id', sa.String(), nullable=True),
    sa.Column('issued_at', sa.DateTime(), nullable=True),
    sa.Column('completion_email_sent_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('certificate_id'),
    sa.UniqueConstraint('user_id', 'course_id')
    )
    op.create_table('channels',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('channel_type', sa.Enum('GROUP', 'DM', 'ANNOUNCEMENT', name='channeltype'), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_channels_id'), 'channels', ['id'], unique=False)
    op.create_table('course_reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('course_id', 'user_id')
    )
    op.create_index(op.f('ix_course_reviews_id'), 'course_reviews', ['id'], unique=False)
    op.create_table('daily_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('team_role', sa.Enum('COMMUNITY_MANAGER', 'TECHNICAL_ENGINEER', 'CUSTOMER_SUCCESS', name='teamrole'), nullable=False),
    sa.Column('what_went_well', sa.Text(), nullable=False),
    sa.Column('what_can_improve', sa.Text(), nullable=False),
    sa.Column('ai_updates_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('messages_replied_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('hours_worked', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('productivity', sa.Integer(), nullable=True),
    sa.Column('community_posts_count', sa.Integer(), nullable=True),
    sa.Column('members_welcomed_count', sa.Integer(), nullable=True),
    sa.Column('wins_encouraged_count', sa.Integer(), nullable=True),
    sa.Column('avg_reply_speed', sa.String(), nullable=True),
    sa.Column('platform_engagement', sa.String(), nullable=True),
    sa.Column('projects_reviewed_count', sa.Integer(), nullable=True),
    sa.Column('projects_accepted_count', sa.Integer(), nullable=True),
    sa.Column('projects_rejected_count', sa.Integer(), nullable=True),
    sa.Column('workflows_resolved_count', sa.Integer(), nullable=True),
    sa.Column('avg_resolution_time', sa.String(), nullable=True),
    sa.Column('report_date', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_daily_reports_id'), 'daily_reports', ['id'], unique=False)
    op.create_index(op.f('ix_daily_reports_report_date'), 'daily_reports', ['report_date'], unique=False)
    op.create_index(op.f('ix_daily_reports_user_id'), 'daily_reports', ['user_id'], unique=False)
    op.create_table('feedbacks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.Enum('COMMUNITY_MANAGER', 'TECHNICAL_ENGINEER', 'CUSTOMER_SUCCESS', name='teamrole'), nullable=False),
    sa.Column('person_name', sa.String(), nullable=False),
    sa.Column('person_email', sa.String(), nullable=True),
    sa.Column('person_user_id', sa.Integer(), nullable=True),
    sa.Column('image_url', sa.String(), nullable=True),
    sa.Column('feedback_text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feedbacks_id'), 'feedbacks', ['id'], unique=False)
    op.create_index(op.f('ix_feedbacks_user_id'), 'feedbacks', ['user_id'], unique=False)
    op.create_table('guest_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('guest_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('session_date', sa.DateTime(), nullable=False),
    sa.Column('platform', sa.String(), nullable=True),
    sa.Column('session_url', sa.String(), nullable=True),
    sa.Column('status', sa.String(), server_default=sa.text("'upcoming'"), nullable=True),
    sa.Column('attendees_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('rating', sa.Numeric(precision=3, scale=1), server_default=sa.text('0.0'), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['guest_id'], ['guests.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_guest_sessions_id'), 'guest_sessions', ['id'], unique=False)
    op.create_table('lessons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('video_url', sa.String(), nullable=True),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('section_title', sa.String(), nullable=True),
    sa.Column('section_order', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('order', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('duration_minutes', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('bunny_video_url', sa.String(), nullable=True),
    sa.Column('vdo_video_id', sa.String(), nullable=True),
    sa.Column('video_status', sa.String(), server_default=sa.text("'pending'"), nullable=True),
    sa.Column('is_free_preview', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('is_project', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('pdf_url', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lessons_id'), 'lessons', ['id'], unique=False)
    op.create_table('live_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('thumbnail_url', sa.String(), nullable=True),
    sa.Column('instructor_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('LIVE', 'UPCOMING', 'ENDED', 'CANCELLED', name='livesessionstatus'), nullable=True),
    sa.Column('difficulty', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='livesessiondifficulty'), nullable=True),
    sa.Column('start_time', sa.DateTime(), nullable=True),
    sa.Column('end_time', sa.DateTime(), nullable=True),
    sa.Column('stream_url', sa.String(), nullable=True),
    sa.Column('recording_url', sa.String(), nullable=True),
    sa.Column('max_attendees', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('current_viewers', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('is_recording_available', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('tags', sa.String(), nullable=True),
    sa.Column('youtube_url', sa.String(), nullable=True),
    sa.Column('zoom_url', sa.String(), nullable=True),
    sa.Column('is_published', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['instructor_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_live_sessions_id'), 'live_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_live_sessions_slug'), 'live_sessions', ['slug'], unique=True)
    op.create_table('manual_payment_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('receipt_url', sa.String(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('expected_amount', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('coupon_code', sa.String(length=64), nullable=True),
    sa.Column('plan', sa.String(), nullable=True),
    sa.Column('method', sa.String(length=20), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('invite_token', sa.String(), nullable=True),
    sa.Column('invite_sent_at', sa.DateTime(), nullable=True),
    sa.Column('invite_expires_at', sa.DateTime(), nullable=True),
    sa.Column('reviewed_by', sa.Integer(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('rejection_reason', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('invite_token')
    )
    op.create_index(op.f('ix_manual_payment_requests_id'), 'manual_payment_requests', ['id'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('link', sa.String(), nullable=True),
    sa.Column('is_read', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)
    op.create_table('payments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('method', sa.Enum('KASHIER', 'MANUAL', name='paymentmethod'), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'CONFIRMED', 'REJECTED', 'REFUNDED', name='paymentstatus'), nullable=True),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(), nullable=True),
    sa.Column('provider_order_id', sa.String(), nullable=True),
    sa.Column('plan_key', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
    op.create_index(op.f('ix_payments_provider_order_id'), 'payments', ['provider_order_id'], unique=False)
    op.create_table('phone_otps',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('phone', sa.String(), nullable=False),
    sa.Column('code', sa.String(length=6), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('is_used', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('post_channel_reads',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('channel', sa.String(), nullable=False),
    sa.Column('last_read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'channel')
    )
    op.create_index(op.f('ix_post_channel_reads_id'), 'post_channel_reads', ['id'], unique=False)
    op.create_table('posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('category_slug', sa.String(), nullable=True),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('tag', sa.String(), nullable=True),
    sa.Column('tag_color', sa.String(), nullable=True),
    sa.Column('tags', sa.String(), nullable=True),
    sa.Column('image_url', sa.String(), nullable=True),
    sa.Column('like_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('comment_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('is_pinned', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_posts_category_slug'), 'posts', ['category_slug'], unique=False)
    op.create_index(op.f('ix_posts_id'), 'posts', ['id'], unique=False)
    op.create_table('project_submissions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('file_name', sa.String(), nullable=False),
    sa.Column('file_url', sa.String(), nullable=False),
    sa.Column('json_payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('admin_notes', sa.Text(), nullable=True),
    sa.Column('reviewed_by', sa.Integer(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_submissions_course_id'), 'project_submissions', ['course_id'], unique=False)
    op.create_index(op.f('ix_project_submissions_id'), 'project_submissions', ['id'], unique=False)
    op.create_index(op.f('ix_project_submissions_user_id'), 'project_submissions', ['user_id'], unique=False)
    op.create_table('suggested_guests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_suggested_guests_id'), 'suggested_guests', ['id'], unique=False)
    op.create_table('user_course_progress',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('completed_lessons', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('percent', sa.Numeric(precision=5, scale=2), server_default=sa.text('0.0'), nullable=True),
    sa.Column('last_accessed', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_course_progress_id'), 'user_course_progress', ['id'], unique=False)
    op.create_table('ai_update_comments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['ai_update_comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['post_id'], ['ai_update_posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_update_comments_id'), 'ai_update_comments', ['id'], unique=False)
    op.create_table('ai_update_polls',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('question', sa.String(), nullable=False),
    sa.Column('total_votes', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['post_id'], ['ai_update_posts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id')
    )
    op.create_index(op.f('ix_ai_update_polls_id'), 'ai_update_polls', ['id'], unique=False)
    op.create_table('ai_update_reactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('emoji', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['post_id'], ['ai_update_posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'user_id')
    )
    op.create_index(op.f('ix_ai_update_reactions_id'), 'ai_update_reactions', ['id'], unique=False)
    op.create_table('chat_members',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('channel_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.Enum('ADMIN', 'MEMBER', name='memberrole'), nullable=True),
    sa.Column('joined_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('last_read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_members_id'), 'chat_members', ['id'], unique=False)
    op.create_table('comments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comments_id'), 'comments', ['id'], unique=False)
    op.create_table('coupon_redemptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('coupon_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('payment_id', sa.Integer(), nullable=True),
    sa.Column('manual_request_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('slot_no', sa.Integer(), nullable=True),
    sa.Column('original_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('final_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=8), server_default=sa.text("'EGP'"), nullable=False),
    sa.Column('plan_key', sa.String(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(), nullable=True),
    sa.Column('released_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['coupon_id'], ['coupons.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['manual_request_id'], ['manual_payment_requests.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('coupon_id', 'slot_no', name='uq_coupon_redemption_slot')
    )
    op.create_index(op.f('ix_coupon_redemptions_coupon_id'), 'coupon_redemptions', ['coupon_id'], unique=False)
    op.create_index(op.f('ix_coupon_redemptions_id'), 'coupon_redemptions', ['id'], unique=False)
    op.create_index(op.f('ix_coupon_redemptions_status'), 'coupon_redemptions', ['status'], unique=False)
    op.create_index(op.f('ix_coupon_redemptions_user_id'), 'coupon_redemptions', ['user_id'], unique=False)
    op.create_index('uq_coupon_redemption_live', 'coupon_redemptions', ['coupon_id', 'user_id'], unique=True, postgresql_where=sa.text("status IN ('pending', 'active')"))
    op.create_table('exams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('pass_percent', sa.Integer(), server_default=sa.text('70'), nullable=True),
    sa.Column('questions', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    sa.Column('is_published', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('after_lesson_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['after_lesson_id'], ['lessons.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exams_after_lesson_id'), 'exams', ['after_lesson_id'], unique=False)
    op.create_index(op.f('ix_exams_course_id'), 'exams', ['course_id'], unique=False)
    op.create_index(op.f('ix_exams_id'), 'exams', ['id'], unique=False)
    op.create_table('lesson_playback_grants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('lesson_id', sa.Integer(), nullable=False),
    sa.Column('first_played_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('last_played_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'lesson_id', name='uq_playback_grant_user_lesson')
    )
    op.create_index(op.f('ix_lesson_playback_grants_lesson_id'), 'lesson_playback_grants', ['lesson_id'], unique=False)
    op.create_index(op.f('ix_lesson_playback_grants_user_id'), 'lesson_playback_grants', ['user_id'], unique=False)
    op.create_table('live_attendees',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('registered_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['live_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_id', 'user_id')
    )
    op.create_index(op.f('ix_live_attendees_id'), 'live_attendees', ['id'], unique=False)
    op.create_table('messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('channel_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('message_type', sa.Enum('TEXT', 'IMAGE', 'FILE', 'VOICE', 'LINK', name='messagetype'), nullable=True),
    sa.Column('file_url', sa.String(), nullable=True),
    sa.Column('file_name', sa.String(), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('reply_to_id', sa.Integer(), nullable=True),
    sa.Column('read_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('edited_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reply_to_id'], ['messages.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_id'), 'messages', ['id'], unique=False)
    op.create_table('post_likes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'user_id')
    )
    op.create_index(op.f('ix_post_likes_id'), 'post_likes', ['id'], unique=False)
    op.create_table('post_reactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('emoji', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', 'user_id')
    )
    op.create_index(op.f('ix_post_reactions_id'), 'post_reactions', ['id'], unique=False)
    op.create_table('session_bookings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('reminder_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['live_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_bookings_id'), 'session_bookings', ['id'], unique=False)
    op.create_table('session_projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('rating', sa.Numeric(precision=3, scale=1), server_default=sa.text('0.0'), nullable=True),
    sa.Column('creator_name', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['live_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_projects_id'), 'session_projects', ['id'], unique=False)
    op.create_table('session_reminders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('reminder_sent', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('reminder_time', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['live_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_reminders_id'), 'session_reminders', ['id'], unique=False)
    op.create_table('user_progress',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('lesson_id', sa.Integer(), nullable=True),
    sa.Column('course_id', sa.Integer(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'lesson_id')
    )
    op.create_table('ai_update_poll_options',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('poll_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(), nullable=False),
    sa.Column('image_url', sa.String(), nullable=True),
    sa.Column('votes_count', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['poll_id'], ['ai_update_polls.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_update_poll_options_id'), 'ai_update_poll_options', ['id'], unique=False)
    op.create_table('chat_message_reactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('emoji', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('message_id', 'user_id', name='uq_chat_message_reaction_user')
    )
    op.create_index(op.f('ix_chat_message_reactions_id'), 'chat_message_reactions', ['id'], unique=False)
    op.create_index(op.f('ix_chat_message_reactions_message_id'), 'chat_message_reactions', ['message_id'], unique=False)
    op.create_index(op.f('ix_chat_message_reactions_user_id'), 'chat_message_reactions', ['user_id'], unique=False)
    op.create_table('comment_reactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('comment_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('emoji', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('comment_id', 'user_id')
    )
    op.create_index(op.f('ix_comment_reactions_id'), 'comment_reactions', ['id'], unique=False)
    op.create_table('exam_attempts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('exam_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('score', sa.Integer(), nullable=False),
    sa.Column('correct_count', sa.Integer(), nullable=False),
    sa.Column('total_questions', sa.Integer(), nullable=False),
    sa.Column('passed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('answers', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exam_attempts_exam_id'), 'exam_attempts', ['exam_id'], unique=False)
    op.create_index(op.f('ix_exam_attempts_id'), 'exam_attempts', ['id'], unique=False)
    op.create_index(op.f('ix_exam_attempts_user_id'), 'exam_attempts', ['user_id'], unique=False)
    op.create_table('message_reads',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('read_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_message_reads_id'), 'message_reads', ['id'], unique=False)
    op.create_table('ai_update_poll_votes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('poll_id', sa.Integer(), nullable=False),
    sa.Column('option_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['option_id'], ['ai_update_poll_options.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['poll_id'], ['ai_update_polls.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('poll_id', 'user_id')
    )
    op.create_index(op.f('ix_ai_update_poll_votes_id'), 'ai_update_poll_votes', ['id'], unique=False)

    # Records that this database's schema came from the snapshot above, which is
    # how the revisions below know their change is already present.
    op.create_table(
        MARKER_TABLE,
        sa.Column("revision", sa.String(length=64), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.execute(sa.text("INSERT INTO %s (revision) VALUES ('ghawy_baseline')" % MARKER_TABLE))


def downgrade() -> None:
    op.drop_table(MARKER_TABLE)
    op.drop_index(op.f('ix_ai_update_poll_votes_id'), table_name='ai_update_poll_votes')
    op.drop_table('ai_update_poll_votes')
    op.drop_index(op.f('ix_message_reads_id'), table_name='message_reads')
    op.drop_table('message_reads')
    op.drop_index(op.f('ix_exam_attempts_user_id'), table_name='exam_attempts')
    op.drop_index(op.f('ix_exam_attempts_id'), table_name='exam_attempts')
    op.drop_index(op.f('ix_exam_attempts_exam_id'), table_name='exam_attempts')
    op.drop_table('exam_attempts')
    op.drop_index(op.f('ix_comment_reactions_id'), table_name='comment_reactions')
    op.drop_table('comment_reactions')
    op.drop_index(op.f('ix_chat_message_reactions_user_id'), table_name='chat_message_reactions')
    op.drop_index(op.f('ix_chat_message_reactions_message_id'), table_name='chat_message_reactions')
    op.drop_index(op.f('ix_chat_message_reactions_id'), table_name='chat_message_reactions')
    op.drop_table('chat_message_reactions')
    op.drop_index(op.f('ix_ai_update_poll_options_id'), table_name='ai_update_poll_options')
    op.drop_table('ai_update_poll_options')
    op.drop_table('user_progress')
    op.drop_index(op.f('ix_session_reminders_id'), table_name='session_reminders')
    op.drop_table('session_reminders')
    op.drop_index(op.f('ix_session_projects_id'), table_name='session_projects')
    op.drop_table('session_projects')
    op.drop_index(op.f('ix_session_bookings_id'), table_name='session_bookings')
    op.drop_table('session_bookings')
    op.drop_index(op.f('ix_post_reactions_id'), table_name='post_reactions')
    op.drop_table('post_reactions')
    op.drop_index(op.f('ix_post_likes_id'), table_name='post_likes')
    op.drop_table('post_likes')
    op.drop_index(op.f('ix_messages_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_live_attendees_id'), table_name='live_attendees')
    op.drop_table('live_attendees')
    op.drop_index(op.f('ix_lesson_playback_grants_user_id'), table_name='lesson_playback_grants')
    op.drop_index(op.f('ix_lesson_playback_grants_lesson_id'), table_name='lesson_playback_grants')
    op.drop_table('lesson_playback_grants')
    op.drop_index(op.f('ix_exams_id'), table_name='exams')
    op.drop_index(op.f('ix_exams_course_id'), table_name='exams')
    op.drop_index(op.f('ix_exams_after_lesson_id'), table_name='exams')
    op.drop_table('exams')
    op.drop_index('uq_coupon_redemption_live', table_name='coupon_redemptions', postgresql_where=sa.text("status IN ('pending', 'active')"))
    op.drop_index(op.f('ix_coupon_redemptions_user_id'), table_name='coupon_redemptions')
    op.drop_index(op.f('ix_coupon_redemptions_status'), table_name='coupon_redemptions')
    op.drop_index(op.f('ix_coupon_redemptions_id'), table_name='coupon_redemptions')
    op.drop_index(op.f('ix_coupon_redemptions_coupon_id'), table_name='coupon_redemptions')
    op.drop_table('coupon_redemptions')
    op.drop_index(op.f('ix_comments_id'), table_name='comments')
    op.drop_table('comments')
    op.drop_index(op.f('ix_chat_members_id'), table_name='chat_members')
    op.drop_table('chat_members')
    op.drop_index(op.f('ix_ai_update_reactions_id'), table_name='ai_update_reactions')
    op.drop_table('ai_update_reactions')
    op.drop_index(op.f('ix_ai_update_polls_id'), table_name='ai_update_polls')
    op.drop_table('ai_update_polls')
    op.drop_index(op.f('ix_ai_update_comments_id'), table_name='ai_update_comments')
    op.drop_table('ai_update_comments')
    op.drop_index(op.f('ix_user_course_progress_id'), table_name='user_course_progress')
    op.drop_table('user_course_progress')
    op.drop_index(op.f('ix_suggested_guests_id'), table_name='suggested_guests')
    op.drop_table('suggested_guests')
    op.drop_index(op.f('ix_project_submissions_user_id'), table_name='project_submissions')
    op.drop_index(op.f('ix_project_submissions_id'), table_name='project_submissions')
    op.drop_index(op.f('ix_project_submissions_course_id'), table_name='project_submissions')
    op.drop_table('project_submissions')
    op.drop_index(op.f('ix_posts_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_category_slug'), table_name='posts')
    op.drop_table('posts')
    op.drop_index(op.f('ix_post_channel_reads_id'), table_name='post_channel_reads')
    op.drop_table('post_channel_reads')
    op.drop_table('phone_otps')
    op.drop_index(op.f('ix_payments_provider_order_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_id'), table_name='payments')
    op.drop_table('payments')
    op.drop_index(op.f('ix_notifications_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_manual_payment_requests_id'), table_name='manual_payment_requests')
    op.drop_table('manual_payment_requests')
    op.drop_index(op.f('ix_live_sessions_slug'), table_name='live_sessions')
    op.drop_index(op.f('ix_live_sessions_id'), table_name='live_sessions')
    op.drop_table('live_sessions')
    op.drop_index(op.f('ix_lessons_id'), table_name='lessons')
    op.drop_table('lessons')
    op.drop_index(op.f('ix_guest_sessions_id'), table_name='guest_sessions')
    op.drop_table('guest_sessions')
    op.drop_index(op.f('ix_feedbacks_user_id'), table_name='feedbacks')
    op.drop_index(op.f('ix_feedbacks_id'), table_name='feedbacks')
    op.drop_table('feedbacks')
    op.drop_index(op.f('ix_daily_reports_user_id'), table_name='daily_reports')
    op.drop_index(op.f('ix_daily_reports_report_date'), table_name='daily_reports')
    op.drop_index(op.f('ix_daily_reports_id'), table_name='daily_reports')
    op.drop_table('daily_reports')
    op.drop_index(op.f('ix_course_reviews_id'), table_name='course_reviews')
    op.drop_table('course_reviews')
    op.drop_index(op.f('ix_channels_id'), table_name='channels')
    op.drop_table('channels')
    op.drop_table('certificates')
    op.drop_index(op.f('ix_ai_update_reads_id'), table_name='ai_update_reads')
    op.drop_table('ai_update_reads')
    op.drop_index(op.f('ix_ai_update_posts_id'), table_name='ai_update_posts')
    op.drop_table('ai_update_posts')
    op.drop_index(op.f('ix_admin_member_notes_member_id'), table_name='admin_member_notes')
    op.drop_table('admin_member_notes')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_legacy_emails_id'), table_name='legacy_emails')
    op.drop_index(op.f('ix_legacy_emails_email'), table_name='legacy_emails')
    op.drop_table('legacy_emails')
    op.drop_index(op.f('ix_guests_id'), table_name='guests')
    op.drop_table('guests')
    op.drop_index(op.f('ix_email_campaign_sends_id'), table_name='email_campaign_sends')
    op.drop_index(op.f('ix_email_campaign_sends_email'), table_name='email_campaign_sends')
    op.drop_index(op.f('ix_email_campaign_sends_campaign_id'), table_name='email_campaign_sends')
    op.drop_table('email_campaign_sends')
    op.drop_index(op.f('ix_courses_sort_order'), table_name='courses')
    op.drop_index(op.f('ix_courses_id'), table_name='courses')
    op.drop_table('courses')
    op.drop_index(op.f('ix_coupons_id'), table_name='coupons')
    op.drop_index(op.f('ix_coupons_code'), table_name='coupons')
    op.drop_table('coupons')
    op.drop_index(op.f('ix_categories_id'), table_name='categories')
    op.drop_table('categories')
    op.drop_index(op.f('ix_birthday_gift_claims_user_id'), table_name='birthday_gift_claims')
    op.drop_index(op.f('ix_birthday_gift_claims_id'), table_name='birthday_gift_claims')
    op.drop_table('birthday_gift_claims')
    # ### end Alembic commands ###
