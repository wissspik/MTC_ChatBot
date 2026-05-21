export type ApiResponse<T> = {
  ok: boolean;
  data: T;
};

export type UserProfile = {
  user_id: string;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  goal_text: string | null;
  direction: string | null;
  specific_track: string | null;
  target_role: string | null;
  goal_reason: string | null;
  current_level: "beginner" | "basic" | "professional" | null;
  time_per_week_label: string | null;
  time_per_week_value: number | null;
  preferred_formats: string[];
  wishes: string | null;
  preference_json: Record<string, unknown>;
  notification_settings_json: Record<string, unknown>;
  global_xp: number;
  procoins?: number;
  achievements_json?: Record<string, unknown>;
  streak_days: number;
  streak_multiplier: number;
  last_activity: string | null;
  dialog_state: "start" | "collecting_profile" | "ready_for_roadmap_generation" | "roadmap_ready";
  profile_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Roadmap = {
  roadmap_id: string;
  profile_id: string;
  title: string;
  direction: string | null;
  target_role: string | null;
  level: string | null;
  estimated_duration_weeks: number | null;
  hours_per_week_label: string | null;
  route_logic: string | null;
  status: "draft" | "active" | "paused" | "completed" | "replaced" | "archived";
  version: number;
  roadmap_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type RoadmapItem = {
  item_id: string;
  roadmap_id: string;
  profile_id: string;
  step_order: number;
  skill_name: string;
  topic_name: string | null;
  name: string;
  description: string | null;
  resources: string | null;
  source_type: "video" | "text" | "practice" | "course" | "lecture" | "article" | "collection" | "project";
  source_name: string | null;
  is_free: boolean;
  language: string;
  difficulty: "beginner" | "basic" | "intermediate" | "advanced" | null;
  duration_minutes: number | null;
  estimated_hours: number | null;
  why_this_material: string | null;
  skill_result: string | null;
  career_value: string | null;
  practice_task: string | null;
  self_check_questions: unknown[];
  completion_check_type: "self_check" | "quiz" | "practice" | "note" | "project" | "manual";
  completion_check_json: Record<string, unknown>;
  min_seconds_before_complete: number;
  issued_at: string | null;
  recommended_deadline_at: string | null;
  deadline_at: string | null;
  xp: number;
  pending_xp: number;
  verified_xp: number;
  xp_policy_json: Record<string, unknown>;
  fraud_score: number;
  streak_multiplier: number;
  status:
    | "not_started"
    | "in_progress"
    | "pending_check"
    | "completed"
    | "completed_late"
    | "expired"
    | "skipped"
    | "replaced";
  user_note: string | null;
  completed_at: string | null;
  item_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Progress = {
  total_items: number;
  completed_items: number;
  in_progress_items: number;
  skipped_items: number;
  not_started_items: number;
  total_xp: number;
  earned_xp: number;
  completion_percent: number;
  current_item: RoadmapItem | null;
  next_item: RoadmapItem | null;
};

export type ProfileState = {
  profile: UserProfile;
  roadmap: Roadmap | null;
  items: RoadmapItem[];
  progress: Progress | null;
};

export type AnalyzeProfileResponse = {
  classifier_output: Record<string, unknown>;
  llm_output: {
    Need_question?: boolean;
    Next_question?: {
      Text?: string;
      Buttons?: string[];
      Allow_multiple?: boolean;
    };
    Understood_request?: string;
    Ready_for_roadmap_generation?: boolean;
  } | null;
  fallback_output?: AnalyzeProfileResponse["llm_output"];
  llm_status?: string;
  user_profile: UserProfile;
};

export type AiMasterMessage = {
  role: "user" | "assistant";
  content: string;
};

export type AiMasterResponse = {
  answer?: string;
  message?: string;
  reply?: string;
  llm_output?: string | { answer?: string; message?: string; reply?: string };
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = errorBody?.detail;
    const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `API request failed: ${response.status}`;
    throw new Error(message);
  }

  const payload = (await response.json()) as ApiResponse<T>;
  return payload.data;
}

export function getProfileState(telegramId: number) {
  return apiRequest<ProfileState>(`/api/profile/${telegramId}/state`);
}

export function analyzeProfile(body: {
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  user_message: string;
  dialog_history: unknown[];
}) {
  return apiRequest<AnalyzeProfileResponse>("/api/profile/analyze", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function askAiMaster(body: {
  telegram_id: number;
  question: string;
  dialog_history: AiMasterMessage[];
}) {
  return apiRequest<AiMasterResponse>("/api/ai-master", {
    method: "POST",
    body: JSON.stringify({
      ...body,
      current_datetime: new Date().toISOString(),
    }),
  });
}

export function generateRoadmap(telegramId: number) {
  return apiRequest<{
    generation_status: "ok" | "llm_failed_template_fallback";
    user_profile: UserProfile;
    created: {
      roadmap: Roadmap;
      items: RoadmapItem[];
      pushes: unknown[];
    };
  }>("/api/roadmap/generate", {
    method: "POST",
    body: JSON.stringify({
      telegram_id: telegramId,
      dialog_history: [],
      current_datetime: new Date().toISOString(),
    }),
  });
}

export function switchRoadmap(telegramId: number, roadmapId: string) {
  return apiRequest<{
    profile: UserProfile;
    current_roadmap: Roadmap;
    roadmap: Roadmap;
    items: RoadmapItem[];
    roadmap_items: RoadmapItem[];
    progress: Progress;
    roadmaps: Roadmap[];
  }>(`/api/profile/${telegramId}/roadmap/switch`, {
    method: "POST",
    body: JSON.stringify({ roadmap_id: roadmapId }),
  });
}

export function startRoadmapItem(telegramId: number, itemId: string) {
  return apiRequest<{ roadmap_item: RoadmapItem }>(`/api/roadmap/item/${itemId}/start`, {
    method: "POST",
    body: JSON.stringify({ telegram_id: telegramId }),
  });
}

export function skipRoadmapItem(
  telegramId: number,
  itemId: string,
  reason: "not_suitable" | "too_hard" | "too_easy" | "already_completed" | "change_request",
  feedbackText: string | null,
) {
  return apiRequest<{ roadmap_item: RoadmapItem; roadmap_feedback: unknown }>(`/api/roadmap/item/${itemId}/skip`, {
    method: "POST",
    body: JSON.stringify({
      telegram_id: telegramId,
      reason,
      feedback_text: feedbackText,
      current_datetime: new Date().toISOString(),
    }),
  });
}

export function unskipRoadmapItem(telegramId: number, itemId: string) {
  return apiRequest<{ roadmap_item: RoadmapItem }>(`/api/roadmap/item/${itemId}/unskip`, {
    method: "POST",
    body: JSON.stringify({
      telegram_id: telegramId,
      current_datetime: new Date().toISOString(),
    }),
  });
}

export function completeRoadmapItem(
  telegramId: number,
  itemId: string,
  minSeconds: number,
  completion?: {
    answers?: Array<{ question: string; answer: string }>;
    note_text?: string | null;
    practice_result?: string | null;
  },
) {
  return apiRequest<{
    completed_item: RoadmapItem;
    user_profile: UserProfile;
    xp_earned: {
      pending_xp: number;
      status: "completed" | "pending_check";
      global_xp: number;
    };
  }>("/api/roadmap/item/complete", {
    method: "POST",
    body: JSON.stringify({
      telegram_id: telegramId,
      item_id: itemId,
      spent_seconds: Math.max(minSeconds, 60),
      answers: completion?.answers ?? [],
      note_text: completion?.note_text ?? null,
      practice_result: completion?.practice_result ?? null,
      current_datetime: new Date().toISOString(),
    }),
  });
}

export function sendRoadmapFeedback(body: {
  telegram_id: number;
  roadmap_id: string;
  item_ids: string[];
  feedback_type: "useful" | "not_suitable" | "too_hard" | "too_easy" | "already_completed" | "change_request";
  feedback_text: string | null;
}) {
  return apiRequest<{
    saved_feedback: unknown;
    llm_output: unknown | null;
    updated_roadmap: Roadmap | null;
    changed_items: RoadmapItem[];
    pushes: unknown[];
    correction_status?: "llm_failed";
    correction_error?: string;
  }>("/api/roadmap/feedback", {
    method: "POST",
    body: JSON.stringify({
      ...body,
      max_items_to_change: 1,
      dialog_history: [],
      current_datetime: new Date().toISOString(),
    }),
  });
}
