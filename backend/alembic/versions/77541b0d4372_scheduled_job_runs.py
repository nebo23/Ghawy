"""scheduler: one row per job run

Revision ID: 77541b0d4372
Revises: c4d7a2e918b6
Create Date: 2026-09-08

Seven daily jobs send mail — renewal reminders, the 5-day expiry warning,
birthdays, the 6-day nudge — and until now none of them left any trace that a
person could go back and read. The job bodies log at INFO while production
runs the root logger at WARNING (main.py), and the container's own log holds
about seventeen hours before rotation eats it, so "did the birthday emails go
out on Tuesday?" had no answer anywhere. Asked over the last month, the only
evidence available was the per-user guard columns, which cannot separate "the
job did not run" from "nobody qualified".

One row per firing: which job, when it started, when it finished, how many it
touched, and the error if it raised. A NULL `finished_at` is itself the useful
value — it means the process died mid-run.

Deliberately small. This is the shape of question a person actually asks, not
a metrics system.
"""
from alembic import op
import sqlalchemy as sa


revision = '77541b0d4372'
down_revision = 'c4d7a2e918b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scheduled_job_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(length=100), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('touched', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_scheduled_job_runs_id'), 'scheduled_job_runs', ['id'])
    op.create_index(op.f('ix_scheduled_job_runs_job_id'), 'scheduled_job_runs', ['job_id'])
    # "did <job> run today?" is the only query this table exists to answer.
    op.create_index('ix_scheduled_job_runs_job_started',
                    'scheduled_job_runs', ['job_id', 'started_at'])


def downgrade():
    op.drop_index('ix_scheduled_job_runs_job_started', table_name='scheduled_job_runs')
    op.drop_index(op.f('ix_scheduled_job_runs_job_id'), table_name='scheduled_job_runs')
    op.drop_index(op.f('ix_scheduled_job_runs_id'), table_name='scheduled_job_runs')
    op.drop_table('scheduled_job_runs')
