import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowUp,
  BookOpen,
  Bot,
  CheckSquare,
  ChevronRight,
  Clock,
  ExternalLink,
  Flame,
  Gem,
  GraduationCap,
  LayoutGrid,
  Map as MapIcon,
  Paintbrush,
  Pencil,
  Rocket,
  Star,
  Sun,
  Target,
  Trophy,
  Type,
  User,
  type LucideIcon,
} from "lucide-react";
import avatarUrl from "./assets/ava.png";
import backgroundUrl from "./assets/background.png";
import catUrl from "./assets/Cat.png";
import happyCatUrl from "./assets/Happy_Cat (1).png";
import profileCatUrl from "./assets/cat_with_procents.png";
import completedNodeUrl from "./assets/completed_node.png";
import currentNodeUrl from "./assets/current_node.png";
import lockedNodeUrl from "./assets/locked_node.png";
import trophyUrl from "./assets/trofeyy.png";
import {
  AiMasterMessage,
  askAiMaster,
  completeRoadmapItem,
  getProfileState,
  ProfileState,
  Roadmap,
  RoadmapItem,
  sendRoadmapFeedback,
  skipRoadmapItem,
  startRoadmapItem,
  unskipRoadmapItem,
  UserProfile,
} from "./api";

type NodeStatus = "completed" | "current" | "locked" | "skipped" | "goal";
type TabId = "profile" | "roadmap" | "mentor";
type LabelSide = "left" | "right" | "top";

type RoadmapNode = {
  id: string;
  title: string;
  progress: number;
  status: NodeStatus;
  description?: string;
  backendItem?: RoadmapItem;
  materials?: RoadmapMaterial[];
  rewards?: {
    coins: number;
    achievement: string;
  };
};

type RoadmapMaterial = { title: string; meta: string; icon: LucideIcon; url?: string };

type ProfileView = typeof profile;
type ProfileSkill = (typeof profileSkills)[number];

type TelegramUser = {
  id?: number;
  username?: string;
  first_name?: string;
  last_name?: string;
};

type LaidOutRoadmapNode = RoadmapNode & {
  x: number;
  y: number;
  labelSide: LabelSide;
};

const roadmapNodes: RoadmapNode[] = [
  {
    id: "start",
    title: "Старт",
    progress: 100,
    status: "completed",
    description: "Ты выбрала цель и начала персональный путь развития.",
    rewards: { coins: 5, achievement: "Первые шаги" },
  },
  {
    id: "basics",
    title: "Основы дизайна",
    progress: 100,
    status: "completed",
    description: "База визуальной коммуникации, контрастов и сеток.",
    rewards: { coins: 15, achievement: "База собрана" },
  },
  {
    id: "color",
    title: "Цвет и типографика",
    progress: 100,
    status: "completed",
    description: "Работа с палитрами, шрифтовыми парами и настроением.",
    rewards: { coins: 20, achievement: "Чувство стиля" },
  },
  {
    id: "composition",
    title: "Композиция",
    progress: 65,
    status: "current",
    description: "Научись выстраивать визуальную иерархию и создавать гармоничные макеты.",
    rewards: { coins: 25, achievement: "Достижение" },
  },
  {
    id: "ui-kit",
    title: "UI Kit",
    progress: 0,
    status: "locked",
    description: "Собери систему компонентов, которая ускоряет дизайн-процесс.",
    rewards: { coins: 20, achievement: "Системность" },
  },
  {
    id: "prototype",
    title: "Прототипирование",
    progress: 0,
    status: "locked",
    description: "Покажи логику продукта через интерактивный прототип.",
    rewards: { coins: 22, achievement: "Поток" },
  },
  {
    id: "research",
    title: "Исследование пользователей",
    progress: 0,
    status: "locked",
    description: "Научись превращать интервью и наблюдения в дизайн-решения.",
    rewards: { coins: 25, achievement: "Исследователь" },
  },
  {
    id: "portfolio",
    title: "Портфолио",
    progress: 0,
    status: "locked",
    description: "Упакуй кейсы так, чтобы работодатель быстро увидел твой уровень.",
    rewards: { coins: 30, achievement: "Кейс готов" },
  },
  {
    id: "goal",
    title: "Твоя цель",
    progress: 0,
    status: "goal",
    description: "Финальный этап: готовое портфолио и понятный план выхода на рынок.",
    rewards: { coins: 50, achievement: "Новая роль" },
  },
];

const recommendedMaterials: RoadmapMaterial[] = [
  { title: "Основы композиции", meta: "Видео • 12 мин", icon: BookOpen },
  { title: "Визуальная иерархия", meta: "Статья • 8 мин", icon: BookOpen },
  { title: "Практика: карточка товара", meta: "Практика • 20 мин", icon: LayoutGrid },
];

const profile = {
  name: "Алина",
  level: 12,
  xp: 1240,
  nextLevelXp: 2000,
  procoins: 50,
  goal: "Стать востребованным UI/UX дизайнером",
  estimatedTime: "3–6 месяцев",
  progress: 65,
};

const profileSkills = [
  { title: "Иллюстрация", progress: 80, icon: Paintbrush },
  { title: "Композиция", progress: 60, icon: LayoutGrid },
  { title: "Цвет и свет", progress: 40, icon: Sun },
  { title: "Типографика", progress: 20, icon: Type },
];

const navItems: Array<{ id: TabId; label: string; icon: typeof User }> = [
  { id: "profile", label: "Профиль", icon: User },
  { id: "roadmap", label: "Родмап", icon: MapIcon },
  { id: "mentor", label: "AI-ментор", icon: Bot },
];

const X_PATTERN = [24, 70, 38, 72, 35, 72, 38, 70, 50];

const nodeImages: Partial<Record<NodeStatus, string>> = {
  completed: completedNodeUrl,
  current: currentNodeUrl,
  locked: lockedNodeUrl,
  skipped: lockedNodeUrl,
};

function normalizeLabelSide(x: number, side: LabelSide): LabelSide {
  if (side === "left" && x < 42) {
    return "right";
  }

  if (side === "right" && x > 65) {
    return "left";
  }

  return side;
}

function layoutRoadmapNodes(nodes: RoadmapNode[]) {
  const TOP = 72;
  const GAP = 150;
  const BOTTOM = 180;

  const laidOutNodes = nodes.map<LaidOutRoadmapNode>((node, index) => {
    const x = X_PATTERN[index % X_PATTERN.length];
    const rawLabelSide: LabelSide = node.status === "goal" ? "top" : index % 2 === 0 ? "right" : "left";

    return {
      ...node,
      x,
      y: TOP + index * GAP,
      labelSide: normalizeLabelSide(x, rawLabelSide),
    };
  });

  const canvasHeight = TOP + Math.max(nodes.length - 1, 0) * GAP + BOTTOM;

  return { nodes: laidOutNodes, canvasHeight };
}

function buildSmoothPath(nodes: LaidOutRoadmapNode[]) {
  if (nodes.length === 0) {
    return "";
  }

  const [first, ...rest] = nodes;

  return rest.reduce((path, next, index) => {
    const prev = nodes[index];
    const midY = (prev.y + next.y) / 2;
    return `${path} C ${prev.x} ${midY}, ${next.x} ${midY}, ${next.x} ${next.y}`;
  }, `M ${first.x} ${first.y}`);
}

function getInitialTab(): TabId {
  const tab = new URLSearchParams(window.location.search).get("tab");
  return tab === "profile" || tab === "mentor" || tab === "roadmap" ? tab : "roadmap";
}

function getTelegramUser(): TelegramUser {
  const telegram = (
    window as Window & {
      Telegram?: {
        WebApp?: {
          initDataUnsafe?: {
            user?: TelegramUser;
          };
          ready?: () => void;
          expand?: () => void;
          close?: () => void;
          openTelegramLink?: (url: string) => void;
        };
      };
    }
  ).Telegram?.WebApp;

  telegram?.ready?.();
  telegram?.expand?.();

  return telegram?.initDataUnsafe?.user ?? {};
}

function openTelegramChat() {
  const telegram = (
    window as Window & {
      Telegram?: {
        WebApp?: {
          close?: () => void;
          openTelegramLink?: (url: string) => void;
        };
      };
    }
  ).Telegram?.WebApp;
  const botUsername = import.meta.env.VITE_BOT_USERNAME;

  if (telegram?.close) {
    telegram.close();
    return;
  }

  if (botUsername) {
    window.location.href = `https://t.me/${botUsername}`;
  }
}

function getTelegramId(user: TelegramUser) {
  const params = new URLSearchParams(window.location.search);
  const queryId = Number(params.get("telegram_id"));
  const envId = Number(import.meta.env.VITE_DEV_TELEGRAM_ID);

  if (Number.isFinite(queryId) && queryId > 0) {
    return queryId;
  }

  if (typeof user.id === "number") {
    return user.id;
  }

  if (Number.isFinite(envId) && envId > 0) {
    return envId;
  }

  return 123;
}

function formatEstimatedTime(weeks?: number | null) {
  if (!weeks) {
    return profile.estimatedTime;
  }

  if (weeks < 4) {
    return `${weeks} нед.`;
  }

  const months = Math.max(1, Math.round(weeks / 4));
  return `${months} мес.`;
}

function getLevelFromXp(xp: number) {
  return Math.max(1, Math.floor(xp / 500) + 1);
}

function getNextLevelXp(xp: number) {
  return Math.ceil((xp + 1) / 500) * 500;
}

function getProfileView(state: ProfileState | null): ProfileView {
  if (!state) {
    return profile;
  }

  const backendProfile = state.profile;
  const xp = backendProfile.global_xp ?? 0;

  return {
    name: backendProfile.first_name || backendProfile.username || profile.name,
    level: getLevelFromXp(xp),
    xp,
    nextLevelXp: getNextLevelXp(xp),
    procoins: backendProfile.procoins ?? (Math.floor(xp / 20) || profile.procoins),
    goal: backendProfile.target_role || backendProfile.goal_text || state.roadmap?.target_role || profile.goal,
    estimatedTime: formatEstimatedTime(state.roadmap?.estimated_duration_weeks),
    progress: state.progress?.completion_percent ?? profile.progress,
  };
}

function getProfileSkills(state: ProfileState | null): ProfileSkill[] {
  if (!state?.items.length) {
    return profileSkills;
  }

  const grouped = new Map<string, { total: number; completed: number }>();

  state.items.forEach((item) => {
    const current = grouped.get(item.skill_name) ?? { total: 0, completed: 0 };
    current.total += 1;
    if (item.status === "completed" || item.status === "completed_late") {
      current.completed += 1;
    }
    grouped.set(item.skill_name, current);
  });

  return Array.from(grouped.entries())
    .slice(0, 4)
    .map(([title, value], index) => ({
      title,
      progress: Math.round((value.completed / value.total) * 100),
      icon: profileSkills[index]?.icon ?? LayoutGrid,
    }));
}

function getCurrentItemId(items: RoadmapItem[], progress: ProfileState["progress"]) {
  const activeItem = items.find((item) => item.status === "in_progress");

  if (activeItem) {
    return activeItem.item_id;
  }

  if (progress?.next_item?.status === "not_started") {
    return progress.next_item.item_id;
  }

  if (progress?.current_item?.status === "not_started") {
    return progress.current_item.item_id;
  }

  return (
    items.find((item) => item.status === "not_started")?.item_id ??
    items.find((item) => item.status === "pending_check")?.item_id ??
    null
  );
}

function mapItemStatus(item: RoadmapItem, currentItemId: string | null): NodeStatus {
  if (item.status === "completed" || item.status === "completed_late" || item.status === "pending_check") {
    return "completed";
  }

  if (item.status === "skipped") {
    return "skipped";
  }

  if (item.item_id === currentItemId || item.status === "in_progress") {
    return "current";
  }

  return "locked";
}

function getItemProgress(item: RoadmapItem, status: NodeStatus) {
  if (item.status === "pending_check") {
    return 90;
  }

  if (status === "completed") {
    return 100;
  }

  return 0;
}

function getMaterialMeta(item: RoadmapItem) {
  const typeMap: Record<RoadmapItem["source_type"], string> = {
    video: "Видео",
    text: "Текст",
    practice: "Практика",
    course: "Курс",
    lecture: "Лекция",
    article: "Статья",
    collection: "Подборка",
    project: "Проект",
  };

  const duration = item.duration_minutes ? ` • ${item.duration_minutes} мин` : "";
  return `${typeMap[item.source_type] ?? "Материал"}${duration}`;
}

function getRoadmapNodes(state: ProfileState | null): RoadmapNode[] {
  if (!state?.items.length) {
    return roadmapNodes;
  }

  const currentItemId = getCurrentItemId(state.items, state.progress);
  const nodes = state.items
    .slice()
    .sort((a, b) => a.step_order - b.step_order)
    .map<RoadmapNode>((item) => {
      const status = mapItemStatus(item, currentItemId);
      return {
        id: item.item_id,
        title: item.name || item.skill_name,
        progress: getItemProgress(item, status),
        status,
        description: item.description || item.why_this_material || item.practice_task || "Материал из твоего персонального родмапа.",
        backendItem: item,
        materials: [
          {
            title: item.source_name || item.topic_name || item.name,
            meta: getMaterialMeta(item),
            icon: item.source_type === "practice" || item.source_type === "project" ? LayoutGrid : BookOpen,
            url: item.resources?.startsWith("http") ? item.resources : undefined,
          },
        ],
        rewards: {
          coins: Math.max(1, Math.round(item.xp / 4)),
          achievement: `${item.xp} XP`,
        },
      };
    });

  nodes.push({
    id: "goal",
    title: "Твоя цель",
    progress: state.progress?.completion_percent ?? 0,
    status: "goal",
    description: state.roadmap?.target_role
      ? `Финальный этап: выйти на уровень ${state.roadmap.target_role}.`
      : "Финальный этап твоего персонального маршрута.",
    rewards: { coins: 50, achievement: "Новая роль" },
  });

  return nodes;
}

function getRoadmapTitle(roadmap: Roadmap | null, profileView: ProfileView) {
  return roadmap?.target_role || roadmap?.title || profileView.goal;
}

function formatRoadmapDate(value: string | null) {
  if (!value) {
    return null;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
  }).format(new Date(value));
}

function getRoadmapItemStatusLabel(status: RoadmapItem["status"]) {
  const labels: Record<RoadmapItem["status"], string> = {
    not_started: "Не начато",
    in_progress: "В работе",
    pending_check: "На проверке",
    completed: "Завершено",
    completed_late: "Завершено позже",
    expired: "Просрочено",
    skipped: "Пропущено",
    replaced: "Заменено",
  };

  return labels[status];
}

function getDifficultyLabel(difficulty: RoadmapItem["difficulty"]) {
  if (!difficulty) {
    return null;
  }

  const labels: Record<NonNullable<RoadmapItem["difficulty"]>, string> = {
    beginner: "новичок",
    basic: "база",
    intermediate: "средний",
    advanced: "продвинутый",
  };

  return labels[difficulty];
}

function getCompletionTypeLabel(type: RoadmapItem["completion_check_type"]) {
  const labels: Record<RoadmapItem["completion_check_type"], string> = {
    self_check: "самопроверка",
    quiz: "квиз",
    practice: "практика",
    note: "конспект",
    project: "проект",
    manual: "ручная проверка",
  };

  return labels[type];
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>(getInitialTab);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const telegramUser = useMemo(getTelegramUser, []);
  const telegramId = useMemo(() => getTelegramId(telegramUser), [telegramUser]);
  const [profileState, setProfileState] = useState<ProfileState | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [loadingState, setLoadingState] = useState(true);

  const refreshState = useCallback(async () => {
    setLoadingState(true);
    try {
      const state = await getProfileState(telegramId);
      setProfileState(state);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Не удалось загрузить данные backend");
    } finally {
      setLoadingState(false);
    }
  }, [telegramId]);

  useEffect(() => {
    void refreshState();
  }, [refreshState]);

  const profileView = useMemo(() => getProfileView(profileState), [profileState]);
  const skillsView = useMemo(() => getProfileSkills(profileState), [profileState]);
  const nodesView = useMemo(() => getRoadmapNodes(profileState), [profileState]);
  const roadmapTitle = useMemo(
    () => getRoadmapTitle(profileState?.roadmap ?? null, profileView),
    [profileState?.roadmap, profileView],
  );

  function handleTabChange(tab: TabId) {
    setActiveTab(tab);
    window.history.replaceState(null, "", `/?tab=${tab}`);
  }

  return (
    <main className="min-h-dvh overflow-x-hidden bg-[#050817] text-white">
      <motion.section
        className="relative mx-auto flex min-h-dvh w-full max-w-[430px] flex-col px-4 pb-[calc(104px+env(safe-area-inset-bottom))] pt-[calc(20px+env(safe-area-inset-top))]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.45 }}
      >
        {activeTab === "roadmap" ? (
          <RoadmapPage
            apiError={apiError}
            loading={loadingState}
            nodes={nodesView}
            profile={profileView}
            roadmapTitle={roadmapTitle}
            selectedNodeId={selectedNodeId}
            state={profileState}
            telegramId={telegramId}
            onRefresh={refreshState}
            onSelect={setSelectedNodeId}
          />
        ) : activeTab === "mentor" ? (
          <AiMasterPage
            profile={profileState?.profile ?? null}
            telegramId={telegramId}
          />
        ) : (
          <ProfileStubPage apiError={apiError} loading={loadingState} profile={profileView} skills={skillsView} />
        )}
        <BottomNav activeTab={activeTab} onChange={handleTabChange} />
      </motion.section>
    </main>
  );
}

function RoadmapPage({
  apiError,
  loading,
  nodes,
  profile,
  roadmapTitle,
  selectedNodeId,
  state,
  telegramId,
  onRefresh,
  onSelect,
}: {
  apiError: string | null;
  loading: boolean;
  nodes: RoadmapNode[];
  profile: ProfileView;
  roadmapTitle: string;
  selectedNodeId: string | null;
  state: ProfileState | null;
  telegramId: number;
  onRefresh: () => Promise<void>;
  onSelect: (id: string | null) => void;
}) {
  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );
  const completionPercent = Math.round(state?.progress?.completion_percent ?? profile.progress);
  const shouldShowFinishModal = Boolean(state?.roadmap && completionPercent >= 80);
  const [finishModalDismissed, setFinishModalDismissed] = useState(false);
  const [showNoRoadmapPrompt, setShowNoRoadmapPrompt] = useState(false);

  return (
    <section
      className="relative z-10 -mx-4 -mb-[calc(104px+env(safe-area-inset-bottom))] -mt-[calc(20px+env(safe-area-inset-top))] flex flex-1 flex-col bg-cover bg-center bg-no-repeat px-4 pb-[calc(128px+env(safe-area-inset-bottom))] pt-[calc(20px+env(safe-area-inset-top))]"
      style={{ backgroundImage: `url(${backgroundUrl})` }}
    >
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,rgba(5,8,23,.62),rgba(5,8,23,.28),rgba(5,8,23,.72)),radial-gradient(circle_at_15%_0%,rgba(139,53,255,.28),transparent_34%),radial-gradient(circle_at_100%_18%,rgba(46,232,255,.12),transparent_28%)]" />
      <div className={`relative z-10 flex flex-1 flex-col ${showNoRoadmapPrompt ? "blur-sm" : ""}`}>
        {!showNoRoadmapPrompt && (
          <>
            <Header roadmapTitle={roadmapTitle} />
            <ProgressSummary loading={loading} profile={profile} progress={state?.progress ?? null} />
            {apiError && (
              <div className="glass-card relative z-10 mb-4 rounded-3xl border-progressPink/25 p-4 text-sm text-white/72">
                Backend недоступен или профиль ещё не создан. Показываю моковые данные. Ошибка: {apiError}
              </div>
            )}
            <RoadmapMap nodes={nodes} selectedNodeId={selectedNodeId} onSelect={onSelect} />
            <RoadmapNodeSheet
              node={selectedNode}
              telegramId={telegramId}
              onClose={() => onSelect(null)}
              onRefresh={onRefresh}
            />
          </>
        )}
      </div>
      <AnimatePresence>
        {shouldShowFinishModal && !finishModalDismissed && !showNoRoadmapPrompt && (
          <RoadmapFinishModal
            completionPercent={completionPercent}
            onCreateRoadmap={openTelegramChat}
            onStay={() => {
              setFinishModalDismissed(true);
              setShowNoRoadmapPrompt(true);
            }}
          />
        )}
      </AnimatePresence>
      {showNoRoadmapPrompt && <NoRoadmapPrompt onCreateRoadmap={openTelegramChat} />}
    </section>
  );
}

function EmptyRoadmapState({ telegramId }: { telegramId: number }) {
  return (
    <div className="glass-card relative z-10 mt-6 rounded-[28px] p-6 text-center">
      <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-3xl bg-progressPurple/20 text-progressPurple">
        <Rocket size={30} />
      </div>
      <h2 className="text-2xl font-black">Трек еще не создан</h2>
      <p className="mt-3 text-[15px] leading-snug text-white/66">
        Открой Telegram-бота, нажми «Сделать трек» и ответь на вопросы. После генерации roadmap появится здесь.
      </p>
      <p className="mt-4 rounded-2xl bg-white/[0.045] px-4 py-3 text-sm font-bold text-white/58">
        Telegram ID: {telegramId}
      </p>
    </div>
  );
}

function ProfileStubPage({
  apiError,
  loading,
  profile,
  skills,
}: {
  apiError: string | null;
  loading: boolean;
  profile: ProfileView;
  skills: ProfileSkill[];
}) {
  return (
    <section className="profile-page relative z-10 flex flex-col gap-5 pb-5">
      {apiError && (
        <div className="glass-card rounded-3xl border-progressPink/25 p-4 text-sm text-white/72">
          Backend недоступен или профиль ещё не создан. Показываю моковый профиль. Ошибка: {apiError}
        </div>
      )}
      <motion.header
        className="grid grid-cols-[142px_1fr] items-center gap-5 pt-3 min-[410px]:grid-cols-[154px_1fr]"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.38 }}
      >
        <div className="relative">
          <div className="profile-avatar h-[142px] w-[142px] overflow-hidden rounded-full min-[410px]:h-[154px] min-[410px]:w-[154px]">
            <img className="h-full w-full object-cover" src={avatarUrl} alt={profile.name} draggable={false} />
          </div>
          <button
            className="absolute bottom-1 right-0 grid h-12 w-12 place-items-center rounded-full bg-[#181568] text-white shadow-neonPurple"
            type="button"
            aria-label="Редактировать профиль"
          >
            <Pencil size={20} />
          </button>
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="truncate text-[34px] font-black leading-none">{profile.name}</h1>
            <span className="rounded-full border border-progressPink/35 bg-progressPink/18 px-3 py-1.5 text-sm font-black text-progressPink">
              Lv.{profile.level}
            </span>
          </div>
          {loading && <p className="mt-3 text-sm text-white/52">Синхронизация с backend...</p>}

          <div className="mt-7 flex items-center gap-3 text-lg">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-[#ff7eb4] text-[#16051d]">
              <Star size={15} fill="currentColor" />
            </span>
            <span>
              <b>{profile.xp}</b> <span className="text-white/58">/ {profile.nextLevelXp} XP</span>
            </span>
          </div>
          <span className="mt-4 block h-2.5 overflow-hidden rounded-full bg-white/9">
            <motion.i
              className="block h-full rounded-full bg-gradient-to-r from-progressPink to-progressPurple shadow-neonPink"
              initial={{ width: 0 }}
              animate={{ width: `${Math.round((profile.xp / profile.nextLevelXp) * 100)}%` }}
              transition={{ duration: 0.9, ease: "easeOut" }}
            />
          </span>

          <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-progressPink/30 bg-white/[0.045] px-4 py-2 text-progressPink shadow-neonPink">
            <Gem size={18} />
            <b>{profile.procoins}</b>
            <span className="text-sm text-white/68">прокоинов</span>
          </div>
        </div>

        <motion.img
          className="pointer-events-none col-span-2 mx-auto -mt-8 w-[250px] max-w-[76%] object-contain drop-shadow-[0_0_32px_rgba(139,53,255,.62)]"
          src={profileCatUrl}
          alt=""
          draggable={false}
          initial={{ opacity: 0, y: 14, scale: 0.96 }}
          animate={{ opacity: 1, y: [0, -8, 0], scale: 1 }}
          transition={{
            opacity: { delay: 0.12, duration: 0.35 },
            scale: { delay: 0.12, duration: 0.35 },
            y: { duration: 2.8, repeat: Infinity, ease: "easeInOut" },
          }}
        />
      </motion.header>

      <motion.div
        className="glass-card rounded-[28px] p-5 min-[410px]:p-6"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08, duration: 0.34 }}
      >
        <h2 className="mb-5 text-2xl font-black">Мои навыки</h2>
        <div className="grid gap-4">
          {skills.map((skill) => {
            const Icon = skill.icon;
            return (
              <div className="grid grid-cols-[54px_1fr_44px] items-center gap-4" key={skill.title}>
                <span className="grid h-[54px] w-[54px] place-items-center rounded-2xl bg-progressPurple/18 text-white shadow-neonPurple">
                  <Icon size={26} />
                </span>
                <div className="min-w-0">
                  <p className="mb-2 truncate text-lg">{skill.title}</p>
                  <span className="block h-2.5 overflow-hidden rounded-full bg-white/8">
                    <motion.i
                      className="block h-full rounded-full bg-gradient-to-r from-progressPink to-[#aa157e]"
                      initial={{ width: 0 }}
                      whileInView={{ width: `${skill.progress}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.7, ease: "easeOut" }}
                    />
                  </span>
                </div>
                <b className="text-right text-lg">{skill.progress}%</b>
              </div>
            );
          })}
        </div>
      </motion.div>

      <motion.div
        className="glass-card grid grid-cols-[70px_1fr] items-center gap-4 rounded-[28px] p-5"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.14, duration: 0.34 }}
      >
        <span className="grid h-[70px] w-[70px] place-items-center rounded-full bg-progressPurple/20 text-progressPink shadow-neonPurple">
          <Target size={38} />
        </span>
        <div>
          <h2 className="text-2xl font-black">Твоя цель</h2>
          <p className="mt-2 text-lg leading-tight text-white/68">{profile.goal}</p>
          <p className="mt-3 text-base text-white/68">
            Осталось <span className="text-progressPink">{profile.estimatedTime}</span>
          </p>
        </div>
      </motion.div>

      <motion.div
        className="glass-card rounded-[28px] p-5"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.34 }}
      >
        <h2 className="mb-5 text-2xl font-black">Что дальше?</h2>
        <div className="grid gap-4">
          <ProfileAction icon={GraduationCap} text="Изучай новые навыки" />
          <ProfileAction icon={CheckSquare} text="Практикуйся каждый день" />
          <ProfileAction icon={Rocket} text="Достигай цели" />
        </div>
      </motion.div>
    </section>
  );
}

function RoadmapFinishModal({
  completionPercent,
  onCreateRoadmap,
  onStay,
}: {
  completionPercent: number;
  onCreateRoadmap: () => void;
  onStay: () => void;
}) {
  return (
    <motion.div
      className="fixed inset-0 z-[90] grid place-items-center bg-[#050817]/72 px-5 backdrop-blur-md"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.section
        className="w-full max-w-[390px] overflow-hidden rounded-[32px] border border-progressPurple/36 bg-[#0b0a24]/96 p-5 text-center text-white shadow-[0_0_70px_rgba(139,53,255,.36)]"
        initial={{ opacity: 0, y: 28, scale: 0.94 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 18, scale: 0.96 }}
        transition={{ type: "spring", stiffness: 280, damping: 24 }}
      >
        <div className="relative mx-auto mb-2 grid h-[168px] place-items-center">
          <div className="absolute inset-x-8 top-8 h-28 rounded-full bg-progressPink/22 blur-3xl" />
          <img
            className="relative z-10 h-[154px] object-contain drop-shadow-[0_0_34px_rgba(255,43,191,.46)]"
            src={happyCatUrl}
            alt=""
            draggable={false}
          />
        </div>
        <p className="text-sm font-black uppercase tracking-normal text-progressPink">Маршрут почти пройден</p>
        <h2 className="mt-2 text-[30px] font-black leading-tight">Ты молодец</h2>
        <p className="mx-auto mt-3 max-w-[300px] text-[16px] leading-snug text-white/66">
          Уже закрыто {completionPercent}% пути. Можно создать новый roadmap и выбрать следующую цель.
        </p>

        <div className="mt-6 rounded-[24px] border border-white/10 bg-white/[0.045] p-4 text-left">
          <p className="text-[17px] font-black">Что дальше?</p>
          <div className="mt-4 grid gap-3">
            <button
              className="h-14 rounded-2xl bg-gradient-to-r from-progressPink to-progressPurple text-[16px] font-black text-white shadow-neonPink"
              type="button"
              onClick={onCreateRoadmap}
            >
              Создать новый roadmap
            </button>
            <button
              className="h-12 rounded-2xl border border-white/12 bg-white/[0.035] text-[15px] font-bold text-white/72"
              type="button"
              onClick={onStay}
            >
              Остаться
            </button>
          </div>
        </div>
      </motion.section>
    </motion.div>
  );
}

function NoRoadmapPrompt({ onCreateRoadmap }: { onCreateRoadmap: () => void }) {
  return (
    <div className="absolute inset-0 z-[60] grid place-items-center px-6 text-center">
      <motion.button
        className="glass-card max-w-[360px] rounded-[30px] border-progressPurple/34 p-6 text-white shadow-neonPurple"
        type="button"
        onClick={onCreateRoadmap}
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <img className="mx-auto mb-3 h-[118px] object-contain" src={happyCatUrl} alt="" draggable={false} />
        <h2 className="text-[26px] font-black leading-tight">Пока нет roadmap</h2>
        <p className="mt-3 text-[16px] leading-snug text-white/66">Давай создадим новый маршрут в Telegram-чате.</p>
        <span className="mt-5 inline-flex h-12 items-center rounded-2xl bg-gradient-to-r from-progressPink to-progressPurple px-5 text-[15px] font-black text-white">
          Создать roadmap
        </span>
      </motion.button>
    </div>
  );
}

function ProfileAction({ icon: Icon, text }: { icon: typeof GraduationCap; text: string }) {
  return (
    <div className="grid grid-cols-[52px_1fr] items-center gap-4">
      <span className="grid h-[52px] w-[52px] place-items-center rounded-2xl bg-progressPurple/18 text-progressPurple shadow-neonPurple">
        <Icon size={26} />
      </span>
      <p className="text-lg text-white/82">{text}</p>
    </div>
  );
}

function AiMasterPage({
  profile,
  telegramId,
}: {
  profile: UserProfile | null;
  telegramId: number;
}) {
  const [message, setMessage] = useState("");
  const [chatMessages, setChatMessages] = useState<AiMasterMessage[]>([]);
  const [isSending, setIsSending] = useState(false);

  function extractAiAnswer(response: Awaited<ReturnType<typeof askAiMaster>>) {
    if (typeof response.answer === "string") {
      return response.answer;
    }

    if (typeof response.reply === "string") {
      return response.reply;
    }

    if (typeof response.message === "string") {
      return response.message;
    }

    if (typeof response.llm_output === "string") {
      return response.llm_output;
    }

    if (response.llm_output && typeof response.llm_output === "object") {
      return response.llm_output.answer || response.llm_output.reply || response.llm_output.message;
    }

    return "Я получил ответ, но не смог распознать формат сообщения.";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage || isSending) {
      return;
    }

    setIsSending(true);
    try {
      const nextMessages: AiMasterMessage[] = [...chatMessages, { role: "user", content: trimmedMessage }];
      setChatMessages(nextMessages);
      setMessage("");

      const result = await askAiMaster({
        telegram_id: telegramId,
        question: trimmedMessage,
        dialog_history: chatMessages,
      });
      setChatMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: extractAiAnswer(result) || "Я получил ответ, но не смог распознать формат сообщения.",
        },
      ]);
    } catch (error) {
      setChatMessages((messages) => [
        ...messages,
        {
          role: "assistant",
          content: error instanceof Error ? error.message : "Не удалось связаться с AI-мастером.",
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <motion.section
      className="ai-master-page relative z-10 -mx-4 -mb-[calc(104px+env(safe-area-inset-bottom))] -mt-[calc(20px+env(safe-area-inset-top))] flex min-h-dvh flex-col overflow-hidden px-5 pb-[calc(104px+env(safe-area-inset-bottom))] pt-[calc(28px+env(safe-area-inset-top))]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.45 }}
    >
      <div className="ai-orb ai-orb-top" />
      <div className="ai-orb ai-orb-left" />
      <div className="ai-orb ai-orb-bottom" />
      <div className="ai-orb ai-orb-blue" />
      <div className="ai-star ai-star-one" />
      <div className="ai-star ai-star-two" />
      <div className="ai-star ai-star-three" />
      <div className="ai-wave" />

      <header className="relative z-10">
        <h1 className="text-[34px] font-black leading-none tracking-normal min-[410px]:text-[38px]">
          <span className="bg-gradient-to-b from-progressPurple to-progressPink bg-clip-text text-transparent">
            AI
          </span>{" "}
          мастер
        </h1>
      </header>

      <div className="relative z-10 mt-5 flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-1 pb-5 pt-2">
          {chatMessages.length === 0 && (
            <motion.div
              className="flex flex-1 flex-col items-center justify-center text-center"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12, duration: 0.45 }}
            >
              <h2 className="text-[34px] font-black leading-none">Чем помочь?</h2>
              <p className="mt-4 max-w-[280px] text-[17px] leading-snug text-white/62">
                Спроси про текущий шаг, тему, практику или развитие навыка.
              </p>
            </motion.div>
          )}

          {chatMessages.map((chatMessage, index) => (
            <motion.div
              className={`max-w-[88%] rounded-[22px] px-4 py-3 text-[15px] leading-snug ${
                chatMessage.role === "user"
                  ? "ml-auto bg-progressPurple text-white shadow-neonPurple"
                  : "mr-auto border border-white/10 bg-white/[0.07] text-white/78 backdrop-blur-xl"
              }`}
              key={`${chatMessage.role}-${index}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {chatMessage.content}
            </motion.div>
          ))}
          {isSending && (
            <div className="mr-auto rounded-[22px] border border-white/10 bg-white/[0.07] px-4 py-3 text-[15px] text-white/58">
              Думаю...
            </div>
          )}
        </div>

        <motion.form
          className="ai-input shrink-0 grid w-full grid-cols-[1fr_56px] items-center gap-3 rounded-full p-2 pl-6"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.24, duration: 0.45 }}
          onSubmit={handleSubmit}
        >
          <input
            className="min-w-0 border-0 bg-transparent text-[18px] text-white outline-none placeholder:text-[#8b58cb]/85"
            placeholder="Сообщение"
            aria-label="Вопрос AI мастеру"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
          <button
            className="grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-progressPurple via-[#8b5cff] to-progressCyan text-white shadow-[0_0_28px_rgba(46,232,255,.4)] disabled:opacity-50"
            type="submit"
            aria-label="Отправить"
            disabled={isSending}
          >
            <ArrowUp size={28} strokeWidth={2.4} />
          </button>
        </motion.form>
      </div>
    </motion.section>
  );
}

function Header({ roadmapTitle }: { roadmapTitle: string }) {
  return (
    <header className="relative z-10 mb-4 flex min-w-0 flex-col gap-4 overflow-hidden">
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2.5">
          <h1 className="min-w-0 whitespace-nowrap text-[32px] font-black leading-none tracking-normal text-white drop-shadow-[0_0_18px_rgba(255,255,255,.18)] min-[410px]:text-[36px]">
            Мой родмап
          </h1>
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-progressPurple/45 bg-progressPurple/22 text-progressPurple shadow-neonPurple">
            <Star size={18} fill="currentColor" />
          </span>
        </div>
        <p className="mt-3 text-[18px] leading-none text-white/66 min-[410px]:text-[20px]">
          Твой путь к цели
        </p>
      </div>

      <button
        className="flex h-12 w-fit max-w-[240px] items-center rounded-full border border-progressPurple/45 bg-[#120d34]/72 px-4 text-[13px] font-black text-progressPink shadow-neonPurple backdrop-blur-xl"
        type="button"
      >
        <span className="flex min-w-0 items-center gap-2 overflow-hidden">
          <Target className="shrink-0" size={19} />
          <span className="min-w-0 truncate whitespace-nowrap">Цель: {roadmapTitle}</span>
          <ChevronRight className="shrink-0" size={19} />
        </span>
      </button>
    </header>
  );
}

function ProgressSummary({
  loading,
  profile,
  progress,
}: {
  loading: boolean;
  profile: ProfileView;
  progress: ProfileState["progress"];
}) {
  const percent = Math.round(progress?.completion_percent ?? profile.progress);
  const completedItems = progress?.completed_items ?? 14;
  const totalItems = progress?.total_items ?? 22;

  return (
    <section className="glass-card relative z-10 mb-4 flex min-w-0 flex-col gap-5 overflow-hidden rounded-[30px] border-progressPurple/30 bg-[#1b1450]/72 px-5 py-5 shadow-neonPurple min-[410px]:px-6">
      <div className="min-w-0">
        <p className="text-[16px] leading-none text-white/70 min-[410px]:text-[17px]">Общий прогресс</p>
        <strong className="mt-3 block text-[42px] font-black leading-none min-[410px]:text-[46px]">{percent}%</strong>
        <span className="mt-3 block h-2 min-w-0 overflow-hidden rounded-full bg-white/10">
          <motion.i
            className="block h-full rounded-full bg-gradient-to-r from-progressPink to-progressPurple shadow-neonPink"
            initial={{ width: 0 }}
            animate={{ width: `${percent}%` }}
            transition={{ duration: 1, ease: "easeOut" }}
          />
        </span>
        <p className="mt-3 text-[16px] leading-tight text-white/64 min-[410px]:text-[17px]">
          {completedItems} из {totalItems} навыков освоено
        </p>
      </div>

      <div className="flex min-w-0 items-center gap-3 rounded-[22px] border border-white/10 bg-white/[0.035] px-4 py-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-progressPink/16 text-progressPink">
          <Flame size={25} fill="currentColor" />
        </span>
        <div className="min-w-0">
          <div className="text-[34px] font-black leading-none">{loading ? "..." : profile.level}</div>
          <div className="mt-1 text-sm font-bold leading-none text-white/62">уровень</div>
        </div>
      </div>

      <div className="flex h-16 min-w-0 items-center rounded-[22px] border border-progressPurple/45 bg-[#180f46]/72 px-5 text-white shadow-neonPurple">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-progressPurple/55 bg-progressPurple/20 text-progressPurple shadow-neonPurple">
            <Star size={20} fill="currentColor" />
          </span>
          <span className="min-w-0 truncate whitespace-nowrap text-[17px] font-black leading-none">
            {profile.xp} / {profile.nextLevelXp} XP
          </span>
        </div>
      </div>
    </section>
  );
}

function RoadmapMap({
  nodes: roadmapNodesView,
  selectedNodeId,
  onSelect,
}: {
  nodes: RoadmapNode[];
  selectedNodeId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const { nodes, canvasHeight } = useMemo(() => layoutRoadmapNodes(roadmapNodesView), [roadmapNodesView]);
  const path = useMemo(() => buildSmoothPath(nodes), [nodes]);

  return (
    <section className="roadmap-stage relative z-10 mb-4 overflow-hidden rounded-[32px] bg-transparent">
      <div
        className="relative"
        style={{ height: canvasHeight }}
        role="presentation"
        onClick={() => onSelect(null)}
      >


        <svg
          className="pointer-events-none absolute inset-0 z-[1] h-full w-full"
          viewBox={`0 0 100 ${canvasHeight}`}
          preserveAspectRatio="none"
        >
          <motion.path
            d={path}
            fill="none"
            stroke="rgba(190, 120, 255, 0.16)"
            strokeLinecap="round"
            strokeWidth="14"
            pathLength={1}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.5, ease: "easeInOut" }}
          />
          <motion.path
            d={path}
            fill="none"
            stroke="rgba(220, 150, 255, 0.55)"
            strokeLinecap="round"
            strokeWidth="6"
            pathLength={1}
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 1.5, ease: "easeInOut" }}
          />
        </svg>

        {nodes.map((node, index) => (
          <RoadmapNodeMarker
            key={node.id}
            node={node}
            index={index}
            selected={selectedNodeId === node.id}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  );
}

function RoadmapNodeMarker({
  node,
  index,
  selected,
  onSelect,
}: {
  node: LaidOutRoadmapNode;
  index: number;
  selected: boolean;
  onSelect: (id: string | null) => void;
}) {
  const labelClass =
    node.status === "completed"
      ? "text-[#63ff64]"
      : node.status === "current"
        ? "text-[#f275ff]"
        : node.status === "skipped"
          ? "text-[#ffd36c]"
          : node.status === "goal"
            ? "text-[#ffd36c]"
            : "text-white/60";
  const nodeSize =
    node.status === "current"
      ? "h-[110px] w-[110px]"
      : node.status === "completed"
        ? "h-[84px] w-[84px]"
        : node.status === "goal"
          ? "h-[104px] w-[104px]"
          : "h-[80px] w-[80px]";
  const labelPositionClass =
    node.labelSide === "right"
      ? "left-[calc(100%+8px)] top-1/2 -translate-y-1/2"
      : node.labelSide === "left"
        ? "right-[calc(100%+8px)] top-1/2 -translate-y-1/2"
        : "bottom-[calc(100%+10px)] left-1/2 -translate-x-1/2";

  return (
    <motion.button
      className={`roadmap-node-button roadmap-node-${node.status} group absolute z-20 grid -translate-x-1/2 -translate-y-1/2 place-items-center border-0 bg-transparent p-0 text-center outline-none`}
      style={{ left: `${node.x}%`, top: `${node.y}px` }}
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onSelect(node.id);
      }}
      initial={{ opacity: 0, scale: 0.72, y: 12 }}
      animate={{ opacity: 1, scale: selected ? 1.08 : 1, y: 0 }}
      transition={{ delay: 0.08 * index, type: "spring", stiffness: 260, damping: 19 }}
      whileHover={{ y: -6, scale: selected ? 1.14 : 1.08 }}
      whileTap={{ scale: 0.95 }}
    >
      <motion.span
        className={`node-aura relative block ${node.status === "current" ? "current-glow" : ""} ${
          node.status === "completed" ? "completed-glow" : ""
        } ${node.status === "goal" ? "goal-node" : ""} ${selected ? "selected-ring" : ""}`}
        animate={node.status === "current" ? { filter: ["brightness(1)", "brightness(1.22)", "brightness(1)"] } : {}}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      >
        <span className="node-pulse node-pulse-one" />
        <span className="node-pulse node-pulse-two" />
        {(node.status === "current" || node.status === "completed" || node.status === "goal") && (
          <>
            <span className="node-spark node-spark-one" />
            <span className="node-spark node-spark-two" />
          </>
        )}
        {node.status === "goal" ? (
          <span className="goal-platform relative grid h-[104px] w-[104px] place-items-center">
            <img
              className="absolute left-1/2 top-1/2 h-[104px] w-[104px] -translate-x-[56%] -translate-y-[54%] object-contain"
              src={trophyUrl}
              alt=""
              draggable={false}
            />
          </span>
        ) : node.status === "current" ? (
          <motion.img
            className={`${nodeSize} object-contain`}
            src={catUrl}
            alt=""
            draggable={false}
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
          />
        ) : (
          <img
            className={`${nodeSize} object-contain`}
            src={nodeImages[node.status]}
            alt=""
            draggable={false}
          />
        )}
      </motion.span>

      <span
        className={`node-label pointer-events-none absolute w-max max-w-[178px] rounded-2xl px-3 py-2 text-left ${labelPositionClass}`}
      >
        <b className="block text-[13px] font-black leading-tight text-white">{node.title}</b>
        <strong className={`mt-1 block text-[18px] leading-none ${labelClass}`}>{node.progress}%</strong>
      </span>
    </motion.button>
  );
}

function InfoBlock({ title, text }: { title: string; text: string }) {
  return (
    <div className="mt-4 rounded-[22px] border border-white/10 bg-white/[0.035] p-4">
      <p className="mb-2 text-[13px] font-bold uppercase tracking-normal text-white/42">{title}</p>
      <p className="text-[15px] leading-snug text-white/72">{text}</p>
    </div>
  );
}

function RoadmapNodeSheet({
  node,
  telegramId,
  onClose,
  onRefresh,
}: {
  node: RoadmapNode | null;
  telegramId: number;
  onClose: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [completionText, setCompletionText] = useState("");
  const backendItem = node?.backendItem ?? null;
  const requiresCompletionText =
    backendItem?.completion_check_json?.required === true ||
    backendItem?.completion_check_type === "practice" ||
    backendItem?.completion_check_type === "note" ||
    backendItem?.completion_check_type === "project";
  const isFutureLocked = node?.status === "locked";
  const isSkipped = backendItem?.status === "skipped";
  const canStart = Boolean(backendItem && node?.status === "current" && backendItem.status === "not_started");
  const canComplete = Boolean(backendItem && backendItem.status === "in_progress");
  const canSkip = Boolean(
    backendItem &&
      node?.status === "current" &&
      (backendItem.status === "not_started" || backendItem.status === "in_progress"),
  );
  const canSendFeedback = Boolean(
    backendItem &&
      !isFutureLocked &&
      (backendItem.status === "in_progress" ||
        backendItem.status === "pending_check" ||
        backendItem.status === "completed" ||
        backendItem.status === "completed_late" ||
        backendItem.status === "skipped"),
  );
  const canRestoreSkipped = Boolean(backendItem && backendItem.status === "skipped");
  const completeDisabled = isUpdating || (requiresCompletionText && !completionText.trim());
  const materials = node?.materials?.length ? node.materials : recommendedMaterials;
  const deadline = formatRoadmapDate(backendItem?.deadline_at ?? null);
  const recommendedDeadline = formatRoadmapDate(backendItem?.recommended_deadline_at ?? null);
  const difficulty = getDifficultyLabel(backendItem?.difficulty ?? null);

  useEffect(() => {
    setCompletionText("");
    setActionError(null);
  }, [node?.id]);

  async function handlePrimaryAction() {
    if (!backendItem || isUpdating || (!canStart && !canComplete) || (canComplete && completeDisabled)) {
      return;
    }

    setIsUpdating(true);
    setActionError(null);
    try {
      if (backendItem.status === "not_started") {
        await startRoadmapItem(telegramId, backendItem.item_id);
      } else {
        await completeRoadmapItem(telegramId, backendItem.item_id, backendItem.min_seconds_before_complete, {
          answers: completionText.trim()
            ? [
                {
                  question: backendItem.practice_task || "Что получилось?",
                  answer: completionText.trim(),
                },
              ]
            : [],
          note_text: completionText.trim() || null,
          practice_result: completionText.trim() || null,
        });
      }
      await onRefresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось обновить шаг");
    } finally {
      setIsUpdating(false);
    }
  }

  async function handleSkip() {
    if (!backendItem || !canSkip || isUpdating) {
      return;
    }

    setIsUpdating(true);
    setActionError(null);
    try {
      await skipRoadmapItem(telegramId, backendItem.item_id, "not_suitable", "Пользователь пропустил шаг из виджета");
      await onRefresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось пропустить шаг");
    } finally {
      setIsUpdating(false);
    }
  }

  async function handleRestoreSkipped() {
    if (!backendItem || !canRestoreSkipped || isUpdating) {
      return;
    }

    setIsUpdating(true);
    setActionError(null);
    try {
      await unskipRoadmapItem(telegramId, backendItem.item_id);
      await onRefresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось отправить запрос на возврат шага");
    } finally {
      setIsUpdating(false);
    }
  }

  async function handleFeedback(
    feedbackType: "not_suitable" | "too_hard" | "too_easy" | "already_completed" | "change_request",
    feedbackText: string,
  ) {
    if (!backendItem || !canSendFeedback || isUpdating) {
      return;
    }

    setIsUpdating(true);
    setActionError(null);
    try {
      await sendRoadmapFeedback({
        telegram_id: telegramId,
        roadmap_id: backendItem.roadmap_id,
        item_ids: [backendItem.item_id],
        feedback_type: feedbackType,
        feedback_text: feedbackText,
      });
      await onRefresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось отправить фидбэк");
    } finally {
      setIsUpdating(false);
    }
  }

  return (
    <AnimatePresence>
      {node && (
        <>
          <motion.button
            className="fixed inset-0 z-[70] cursor-default border-0 bg-black/28 p-0"
            type="button"
            aria-label="Закрыть информацию о навыке"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.aside
            className="node-sheet fixed bottom-0 left-1/2 z-[80] flex w-[min(100%,430px)] flex-col rounded-t-[30px] px-5 pt-3 text-white"
            initial={{ opacity: 0, x: "-50%", y: 120, scale: 0.98 }}
            animate={{ opacity: 1, x: "-50%", y: 0, scale: 1 }}
            exit={{ opacity: 0, x: "-50%", y: 120, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 310, damping: 28 }}
            role="dialog"
            aria-label={`Информация: ${node.title}`}
            onClick={(event) => event.stopPropagation()}
          >
            <span className="mx-auto mb-4 block h-1.5 w-16 shrink-0 rounded-full bg-white/24" />

            <div className="node-sheet-scroll min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-contain pb-[calc(96px+env(safe-area-inset-bottom))]">
              <div className="grid grid-cols-[72px_1fr] gap-4">
                <span className="node-sheet-icon grid h-[72px] w-[72px] place-items-center rounded-3xl text-progressPurple">
                  {node.status === "goal" ? <Trophy size={34} /> : <LayoutGrid size={34} />}
                </span>

                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-[25px] font-black leading-tight">{node.title}</h2>
                    <span className="rounded-full border border-progressPurple/35 bg-progressPurple/14 px-3 py-1 text-[15px] font-black text-progressPurple">
                      {node.progress}%
                    </span>
                  </div>
                  <p className="mt-2 text-[15px] leading-snug text-white/62">{node.description}</p>
                </div>
              </div>

              {backendItem && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="rounded-full bg-white/[0.06] px-3 py-1.5 text-[13px] font-bold text-white/66">
                    {getRoadmapItemStatusLabel(backendItem.status)}
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.06] px-3 py-1.5 text-[13px] font-bold text-white/66">
                    <Clock size={14} />
                    {backendItem.duration_minutes ?? Math.round((backendItem.estimated_hours ?? 1) * 60)} мин
                  </span>
                  {difficulty && (
                    <span className="rounded-full bg-white/[0.06] px-3 py-1.5 text-[13px] font-bold text-white/66">
                      {difficulty}
                    </span>
                  )}
                  <span className="rounded-full bg-progressPurple/14 px-3 py-1.5 text-[13px] font-bold text-progressPurple">
                    {backendItem.xp} XP
                  </span>
                </div>
              )}

              {backendItem?.why_this_material && (
                <InfoBlock title="Зачем это" text={backendItem.why_this_material} />
              )}

              {(backendItem?.skill_result || backendItem?.career_value) && (
                <div className="mt-4 grid gap-3">
                  {backendItem.skill_result && <InfoBlock title="Результат навыка" text={backendItem.skill_result} />}
                  {backendItem.career_value && <InfoBlock title="Польза для карьеры" text={backendItem.career_value} />}
                </div>
              )}

              {backendItem?.practice_task && <InfoBlock title="Практика" text={backendItem.practice_task} />}

              {backendItem?.self_check_questions.length ? (
                <div className="mt-4 rounded-[22px] border border-white/10 bg-white/[0.035] p-4">
                  <p className="mb-3 text-[15px] font-black text-white">Самопроверка</p>
                  <div className="grid gap-2">
                    {backendItem.self_check_questions.map((question, index) => (
                      <p className="text-[14px] leading-snug text-white/66" key={`${question}-${index}`}>
                        {index + 1}. {String(question)}
                      </p>
                    ))}
                  </div>
                </div>
              ) : null}

              {backendItem && (
                <div className="mt-4 rounded-[22px] border border-white/10 bg-white/[0.035] p-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-[12px] font-bold uppercase tracking-normal text-white/42">Проверка</p>
                      <p className="mt-1 text-[15px] font-black text-white">
                        {getCompletionTypeLabel(backendItem.completion_check_type)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[12px] font-bold uppercase tracking-normal text-white/42">Дедлайн</p>
                      <p className="mt-1 text-[15px] font-black text-white">{deadline || recommendedDeadline || "без даты"}</p>
                    </div>
                    <div>
                      <p className="text-[12px] font-bold uppercase tracking-normal text-white/42">Pending XP</p>
                      <p className="mt-1 text-[15px] font-black text-white">{backendItem.pending_xp}</p>
                    </div>
                    <div>
                      <p className="text-[12px] font-bold uppercase tracking-normal text-white/42">Verified XP</p>
                      <p className="mt-1 text-[15px] font-black text-white">{backendItem.verified_xp}</p>
                    </div>
                  </div>
                </div>
              )}

              {backendItem?.status === "in_progress" && (
                <label className="mt-4 block">
                  <span className="mb-2 block text-[15px] font-bold text-white/62">
                    {requiresCompletionText ? "Ответ для сдачи" : "Заметка к шагу"}
                  </span>
                  <textarea
                    className="min-h-[112px] w-full resize-none rounded-[22px] border border-white/12 bg-white/[0.045] p-4 text-[15px] leading-snug text-white outline-none placeholder:text-white/34"
                    placeholder="Опиши, что сделал и какой результат получил"
                    value={completionText}
                    onChange={(event) => setCompletionText(event.target.value)}
                  />
                </label>
              )}

              {isFutureLocked && (
                <InfoBlock title="Пока недоступно" text="Этот шаг откроется после прохождения предыдущих этапов." />
              )}

              {isSkipped && (
                <InfoBlock
                  title="Шаг пропущен"
                  text="Материал не удалён: его можно открыть, изучить как справку или отправить запрос, чтобы вернуть шаг в маршрут."
                />
              )}

              {backendItem?.status === "pending_check" && (
                <InfoBlock
                  title="Ответ на проверке"
                  text="Ты уже отправил результат. Когда проверка завершится, прогресс и XP обновятся автоматически."
                />
              )}

              {(backendItem?.status === "completed" || backendItem?.status === "completed_late") && (
                <InfoBlock title="Шаг завершён" text="Этот материал уже засчитан. Можно вернуться к нему как к справке." />
              )}

              {(canStart || canComplete) && (
                <div className="mt-4 grid gap-3">
                  <button
                    className="h-14 rounded-2xl bg-gradient-to-r from-progressPink to-progressPurple text-[17px] font-black text-white shadow-neonPink disabled:opacity-45"
                    type="button"
                    disabled={canComplete ? completeDisabled : isUpdating}
                    onClick={handlePrimaryAction}
                  >
                    {isUpdating ? "Сохраняю..." : canStart ? "Начать" : "Сдать результат"}
                  </button>
                  {canSkip && (
                    <button
                      className="h-12 rounded-2xl border border-white/12 bg-white/[0.035] text-[15px] font-bold text-white/70 disabled:opacity-45"
                      type="button"
                      disabled={isUpdating}
                      onClick={handleSkip}
                    >
                      Пропустить шаг
                    </button>
                  )}
                </div>
              )}
              {canRestoreSkipped && (
                <div className="mt-4 grid gap-3">
                  <button
                    className="h-14 rounded-2xl bg-gradient-to-r from-progressPink to-progressPurple text-[17px] font-black text-white shadow-neonPink disabled:opacity-45"
                    type="button"
                    disabled={isUpdating}
                    onClick={handleRestoreSkipped}
                  >
                    {isUpdating ? "Отправляю..." : "Вернуть в маршрут"}
                  </button>
                </div>
              )}
              {actionError && <p className="mt-3 text-sm text-progressPink">{actionError}</p>}

              {canSendFeedback && (
                <div className="mt-5">
                  <p className="mb-3 text-[15px] font-bold text-white/62">Фидбэк по шагу</p>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      className="rounded-2xl border border-white/12 bg-white/[0.035] px-3 py-3 text-left text-[14px] font-bold text-white/72 disabled:opacity-45"
                      type="button"
                      disabled={isUpdating}
                      onClick={() => handleFeedback("too_hard", "Этот шаг слишком сложный")}
                    >
                      Слишком сложно
                    </button>
                    <button
                      className="rounded-2xl border border-white/12 bg-white/[0.035] px-3 py-3 text-left text-[14px] font-bold text-white/72 disabled:opacity-45"
                      type="button"
                      disabled={isUpdating}
                      onClick={() => handleFeedback("too_easy", "Этот шаг слишком простой")}
                    >
                      Слишком просто
                    </button>
                    <button
                      className="rounded-2xl border border-white/12 bg-white/[0.035] px-3 py-3 text-left text-[14px] font-bold text-white/72 disabled:opacity-45"
                      type="button"
                      disabled={isUpdating}
                      onClick={() => handleFeedback("not_suitable", "Материал мне не подходит")}
                    >
                      Не подходит
                    </button>
                    <button
                      className="rounded-2xl border border-white/12 bg-white/[0.035] px-3 py-3 text-left text-[14px] font-bold text-white/72 disabled:opacity-45"
                      type="button"
                      disabled={isUpdating}
                      onClick={() => handleFeedback("already_completed", "Я уже знаю эту тему")}
                    >
                      Уже знаю
                    </button>
                  </div>
                </div>
              )}

              {!backendItem && (
                <div className="mt-5">
                <p className="mb-3 text-[15px] font-bold text-white/62">Награда</p>
                <div className="flex flex-wrap gap-3">
                  <span className="inline-flex items-center gap-2 rounded-full bg-progressPurple/16 px-4 py-2 text-[15px] font-bold text-[#c46dff]">
                    <Gem size={17} fill="currentColor" />
                    {node.backendItem ? `${node.backendItem.xp} XP` : `Прокоины ${node.rewards?.coins ?? 0}`}
                  </span>
                  <span className="inline-flex items-center gap-2 rounded-full bg-progressCyan/12 px-4 py-2 text-[15px] font-bold text-progressCyan">
                    <Trophy size={17} />
                    {node.rewards?.achievement ?? "Достижение"}
                  </span>
                </div>
              </div>
              )}

              <div className="mt-5 border-t border-white/10 pt-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h3 className="text-[18px] font-black">Рекомендуемые материалы</h3>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {materials.slice(0, 3).map((material) => {
                    const Icon = material.icon;
                    const materialContent = (
                      <>
                        <span className="mb-3 grid h-10 w-10 place-items-center rounded-xl bg-progressCyan/18 text-progressCyan">
                          <Icon size={22} />
                        </span>
                        <span className="flex items-start justify-between gap-2">
                          <b className="line-clamp-2 block text-[14px] leading-tight text-white">{material.title}</b>
                          {material.url && <ExternalLink className="shrink-0 text-progressCyan" size={16} />}
                        </span>
                        <span className="mt-2 block text-[13px] leading-tight text-white/48">
                          {material.url ? "Открыть ссылку" : material.meta}
                        </span>
                      </>
                    );

                    return material.url ? (
                      <a
                        className="node-material block min-h-[108px] rounded-[20px] p-3 text-left"
                        href={material.url}
                        key={material.title}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {materialContent}
                      </a>
                    ) : (
                      <div className="node-material min-h-[108px] rounded-[20px] p-3 text-left" key={material.title}>
                        {materialContent}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function BottomNav({ activeTab, onChange }: { activeTab: TabId; onChange: (tab: TabId) => void }) {
  return (
    <nav className="glass-card fixed bottom-[calc(12px+env(safe-area-inset-bottom))] left-1/2 z-50 grid min-h-[86px] w-[min(calc(100%_-_24px),406px)] -translate-x-1/2 grid-cols-3 rounded-[30px] p-2">
      {navItems.map((item) => {
        const Icon = item.icon;
        const active = item.id === activeTab;

        return (
          <button
            className={`relative grid place-items-center gap-1 rounded-3xl border-0 bg-transparent ${
              active ? "text-progressPink" : "text-white/60"
            }`}
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
          >
            {active && (
              <span className="absolute -top-2 h-1 w-16 rounded-full bg-progressPink shadow-[0_0_24px_rgba(255,43,191,.9)]" />
            )}
            <Icon size={28} />
            <span className="text-sm">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
