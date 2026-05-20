CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS user_profile (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    telegram_id BIGINT NOT NULL UNIQUE,
    username TEXT,
    first_name TEXT,
    last_name TEXT,

    goal_text TEXT,
    direction TEXT,
    specific_track TEXT,
    target_role TEXT,
    goal_reason TEXT,

    current_level TEXT CHECK (
        current_level IN ('beginner', 'basic', 'professional')
    ),

    time_per_week_label TEXT,
    time_per_week_value INT CHECK (
        time_per_week_value IS NULL OR time_per_week_value >= 0
    ),

    preferred_formats TEXT[] DEFAULT '{}'::TEXT[],
    wishes TEXT,
    preference_json JSONB NOT NULL DEFAULT '{
        "collected": false,
        "hard_rules": [],
        "soft_rules": [],
        "blocked_authors": [],
        "blocked_channels": [],
        "blocked_sources": [],
        "preferred_sources": [],
        "format_weights": {
            "video": 1.0,
            "article": 1.0,
            "practice": 1.0
        },
        "max_video_minutes": null,
        "explanation_style": [],
        "pace_preference": "normal"
    }'::JSONB,
    notification_settings_json JSONB NOT NULL DEFAULT '{
        "push_enabled": true,
        "motivation_style": "duolingo_aggressive",
        "quiet_hours": {
            "enabled": true,
            "start": "22:00",
            "end": "09:00"
        },
        "max_pushes_per_day": 3,
        "deadline_pushes": true,
        "streak_pushes": true,
        "xp_pushes": true,
        "allow_roast": true
    }'::JSONB,

    global_xp INT NOT NULL DEFAULT 0 CHECK (global_xp >= 0),
    streak_days INT NOT NULL DEFAULT 0 CHECK (streak_days >= 0),
    streak_multiplier NUMERIC(4, 2) NOT NULL DEFAULT 1.0,
    last_activity DATE,

    dialog_state TEXT NOT NULL DEFAULT 'start',
    profile_json JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_profile_telegram_id ON user_profile (telegram_id);
CREATE INDEX IF NOT EXISTS idx_user_profile_dialog_state ON user_profile (dialog_state);
CREATE INDEX IF NOT EXISTS idx_user_profile_target_role ON user_profile (target_role);
CREATE INDEX IF NOT EXISTS idx_user_profile_preference_json ON user_profile USING GIN (preference_json);
CREATE INDEX IF NOT EXISTS idx_user_profile_notification_settings ON user_profile USING GIN (notification_settings_json);

CREATE TABLE IF NOT EXISTS roadmap (
    roadmap_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES user_profile(user_id) ON DELETE CASCADE,

    title TEXT NOT NULL,
    direction TEXT,
    target_role TEXT,
    level TEXT,

    estimated_duration_weeks INT CHECK (
        estimated_duration_weeks IS NULL OR estimated_duration_weeks > 0
    ),
    hours_per_week_label TEXT,
    route_logic TEXT,

    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('draft', 'active', 'paused', 'completed', 'replaced', 'archived')
    ),

    version INT NOT NULL DEFAULT 1,
    roadmap_json JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_roadmap_profile_status ON roadmap (profile_id, status);
CREATE INDEX IF NOT EXISTS idx_roadmap_profile_updated ON roadmap (profile_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_roadmap_target_role ON roadmap (target_role);

CREATE TABLE IF NOT EXISTS roadmap_item (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    roadmap_id UUID NOT NULL REFERENCES roadmap(roadmap_id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES user_profile(user_id) ON DELETE CASCADE,

    step_order INT NOT NULL,
    skill_name TEXT NOT NULL,
    topic_name TEXT,

    name TEXT NOT NULL,
    description TEXT,
    resources TEXT,

    source_type TEXT NOT NULL CHECK (
        source_type IN ('video', 'text', 'practice', 'course', 'lecture', 'article', 'collection', 'project')
    ),
    source_name TEXT,

    is_free BOOLEAN NOT NULL DEFAULT true,
    language TEXT NOT NULL DEFAULT 'ru',
    difficulty TEXT CHECK (
        difficulty IN ('beginner', 'basic', 'intermediate', 'advanced')
    ),

    duration_minutes INT CHECK (
        duration_minutes IS NULL OR duration_minutes >= 0
    ),
    estimated_hours NUMERIC(5, 2) CHECK (
        estimated_hours IS NULL OR estimated_hours >= 0
    ),

    why_this_material TEXT,
    skill_result TEXT,
    career_value TEXT,
    practice_task TEXT,
    self_check_questions JSONB DEFAULT '[]'::JSONB,
    completion_check_type TEXT NOT NULL DEFAULT 'self_check' CHECK (
        completion_check_type IN ('self_check', 'quiz', 'practice', 'note', 'project', 'manual')
    ),
    completion_check_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    min_seconds_before_complete INT NOT NULL DEFAULT 0 CHECK (min_seconds_before_complete >= 0),

    issued_at TIMESTAMPTZ DEFAULT now(),
    recommended_deadline_at TIMESTAMPTZ,
    deadline_at TIMESTAMPTZ,

    xp INT NOT NULL DEFAULT 0 CHECK (xp >= 0),
    pending_xp INT NOT NULL DEFAULT 0 CHECK (pending_xp >= 0),
    verified_xp INT NOT NULL DEFAULT 0 CHECK (verified_xp >= 0),
    xp_policy_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    fraud_score NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (fraud_score >= 0),
    streak_multiplier NUMERIC(4, 2) NOT NULL DEFAULT 1.0 CHECK (streak_multiplier >= 0),

    status TEXT NOT NULL DEFAULT 'not_started' CHECK (
        status IN ('not_started', 'in_progress', 'pending_check', 'completed', 'completed_late', 'expired', 'skipped', 'replaced')
    ),

    user_note TEXT,
    completed_at TIMESTAMPTZ,
    item_json JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (roadmap_id, step_order)
);

CREATE INDEX IF NOT EXISTS idx_roadmap_item_roadmap_order ON roadmap_item (roadmap_id, step_order);
CREATE INDEX IF NOT EXISTS idx_roadmap_item_roadmap_status_order ON roadmap_item (roadmap_id, status, step_order);
CREATE INDEX IF NOT EXISTS idx_roadmap_item_profile_status ON roadmap_item (profile_id, status);
CREATE INDEX IF NOT EXISTS idx_roadmap_item_profile_roadmap_order ON roadmap_item (profile_id, roadmap_id, step_order);
CREATE INDEX IF NOT EXISTS idx_roadmap_item_deadline ON roadmap_item (deadline_at);

CREATE TABLE IF NOT EXISTS roadmap_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES user_profile(user_id) ON DELETE CASCADE,
    roadmap_id UUID NOT NULL REFERENCES roadmap(roadmap_id) ON DELETE CASCADE,
    item_id UUID REFERENCES roadmap_item(item_id) ON DELETE SET NULL,

    feedback_type TEXT NOT NULL CHECK (
        feedback_type IN ('useful', 'not_suitable', 'too_hard', 'too_easy', 'already_completed', 'change_request')
    ),
    feedback_text TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_roadmap_feedback_profile ON roadmap_feedback (profile_id);
CREATE INDEX IF NOT EXISTS idx_roadmap_feedback_roadmap_created ON roadmap_feedback (roadmap_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_roadmap_feedback_item ON roadmap_feedback (item_id);
CREATE INDEX IF NOT EXISTS idx_roadmap_feedback_type ON roadmap_feedback (feedback_type);

CREATE TABLE IF NOT EXISTS llm_run (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID REFERENCES user_profile(user_id) ON DELETE SET NULL,
    roadmap_id UUID REFERENCES roadmap(roadmap_id) ON DELETE SET NULL,

    prompt_name TEXT NOT NULL CHECK (
        prompt_name IN ('profile_analysis', 'roadmap_generation', 'roadmap_correction')
    ),

    input_json JSONB NOT NULL,
    output_json JSONB,

    status TEXT NOT NULL DEFAULT 'success' CHECK (
        status IN ('success', 'failed')
    ),
    error_text TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_run_profile ON llm_run (profile_id);
CREATE INDEX IF NOT EXISTS idx_llm_run_created ON llm_run (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_run_prompt_name ON llm_run (prompt_name);

CREATE TABLE IF NOT EXISTS top_users (
    top_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES user_profile(user_id) ON DELETE CASCADE,

    period_type TEXT NOT NULL CHECK (
        period_type IN ('all_time', 'monthly', 'weekly')
    ),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    rank_place INT NOT NULL,
    xp_value INT NOT NULL DEFAULT 0,

    streak_days INT NOT NULL DEFAULT 0,
    completed_items INT NOT NULL DEFAULT 0,
    completed_roadmaps INT NOT NULL DEFAULT 0,

    username_snapshot TEXT,
    display_name_snapshot TEXT,

    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (period_type, period_start, period_end, profile_id),
    UNIQUE (period_type, period_start, period_end, rank_place)
);

CREATE INDEX IF NOT EXISTS idx_top_users_period_rank ON top_users (period_type, period_start, period_end, rank_place);
CREATE INDEX IF NOT EXISTS idx_top_users_profile ON top_users (profile_id);
CREATE INDEX IF NOT EXISTS idx_top_users_xp ON top_users (period_type, xp_value DESC);

CREATE TABLE IF NOT EXISTS motivation_push (
    push_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES user_profile(user_id) ON DELETE CASCADE,
    roadmap_id UUID REFERENCES roadmap(roadmap_id) ON DELETE CASCADE,
    item_id UUID REFERENCES roadmap_item(item_id) ON DELETE SET NULL,

    push_type TEXT NOT NULL CHECK (
        push_type IN ('deadline_warning', 'deadline_expired', 'streak_risk', 'xp_opportunity', 'return_to_route', 'test_required')
    ),
    tone TEXT NOT NULL DEFAULT 'duolingo_aggressive' CHECK (
        tone IN ('soft', 'neutral', 'duolingo_aggressive')
    ),

    message_text TEXT NOT NULL,
    button_text TEXT,
    button_payload JSONB NOT NULL DEFAULT '{}'::JSONB,

    scheduled_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'planned' CHECK (
        status IN ('planned', 'sent', 'cancelled', 'failed', 'skipped_by_quiet_hours', 'rate_limited')
    ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_motivation_push_schedule ON motivation_push (status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_motivation_push_profile ON motivation_push (profile_id);
CREATE INDEX IF NOT EXISTS idx_motivation_push_roadmap_schedule ON motivation_push (roadmap_id, status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_motivation_push_item ON motivation_push (item_id);
