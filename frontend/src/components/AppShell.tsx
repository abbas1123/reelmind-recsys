import { useQuery } from "@tanstack/react-query";
import { BarChart3, Compass, Heart, Home, Search, type LucideIcon } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { api } from "../api/client";
import { genreColor } from "../lib/genre";
import { useProfile } from "../state/profile";

const NAV: { to: string; label: string; icon: LucideIcon; needsProfile: boolean }[] = [
  { to: "/home", label: "Home", icon: Home, needsProfile: true },
  { to: "/discover", label: "Discover", icon: Compass, needsProfile: false },
  { to: "/me", label: "My list", icon: Heart, needsProfile: true },
  { to: "/models", label: "Insights", icon: BarChart3, needsProfile: false },
];

export function initials(name: string) {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function avatarGradient(id: number) {
  const hues = [350, 20, 200, 265, 160, 300, 40];
  const h = hues[id % hues.length];
  return `linear-gradient(135deg, hsl(${h} 85% 58%), hsl(${(h + 40) % 360} 80% 45%))`;
}

function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <img src="/favicon.svg" alt="" className="size-8" />
      <span className="text-lg font-extrabold tracking-tight">ReelMind</span>
    </span>
  );
}

function ProfileButton() {
  const { profile } = useProfile();
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => navigate("/")}
      className="flex items-center gap-2.5 rounded-full p-1 pr-3 text-left outline-none ring-1 ring-line transition hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-brand"
    >
      <span className="sr-only">Switch profile, </span>
      <span
        className="grid size-8 place-items-center rounded-full text-xs font-bold text-white"
        style={{ background: profile ? avatarGradient(profile.id) : "var(--surface-3)" }}
        aria-hidden
      >
        {profile ? initials(profile.display_name) : "?"}
      </span>
      <span className="max-w-36 truncate text-sm font-semibold" data-testid="current-profile">
        {profile?.display_name ?? "Choose profile"}
      </span>
    </button>
  );
}

function TopSearch() {
  const navigate = useNavigate();
  const location = useLocation();
  const [q, setQ] = useState("");
  useEffect(() => setQ(""), [location.pathname]);
  if (location.pathname === "/discover") return <div className="flex-1" />;
  return (
    <form
      role="search"
      className="relative hidden max-w-md flex-1 md:block"
      onSubmit={(e) => {
        e.preventDefault();
        navigate(q.trim() ? `/discover?q=${encodeURIComponent(q.trim())}` : "/discover");
      }}
    >
      <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-text-3" aria-hidden />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search films, moods, themes…"
        aria-label="Quick search"
        className="h-11 w-full rounded-full bg-surface-2 pl-11 pr-4 text-sm text-text outline-none ring-1 ring-line placeholder:text-text-3 focus:ring-2 focus:ring-brand"
      />
    </form>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { profile, profileId } = useProfile();
  const genres = profile?.preferred_genres ?? [];
  // Poll until the models are up (e.g. the page was opened while the backend was still starting).
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: (q) => (q.state.data?.status === "ok" ? false : 5000),
  });
  const nav = NAV.filter((n) => !n.needsProfile || profileId);

  return (
    <div className="min-h-dvh bg-bg">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[248px] flex-col gap-6 border-r border-line bg-bg-elev px-4 py-6 lg:flex">
        <NavLink to={profileId ? "/home" : "/"} className="px-2" aria-label="ReelMind home">
          <Logo />
        </NavLink>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${
                  isActive ? "bg-white/10 text-text" : "text-text-3 hover:bg-white/5 hover:text-text"
                }`
              }
            >
              <Icon className="size-5" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>

        {genres.length > 0 && (
          <div className="flex min-h-0 flex-col gap-2">
            <p className="px-3 text-xs font-semibold uppercase tracking-wider text-text-3">Your genres</p>
            <ul className="flex flex-col gap-0.5 overflow-y-auto">
              {genres.map((g) => (
                <li key={g}>
                  <NavLink
                    to={`/discover?genre=${encodeURIComponent(g)}`}
                    className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-text-2 transition hover:bg-white/5 hover:text-text"
                  >
                    <span className="size-6 rounded-md" style={{ background: genreColor(g) }} aria-hidden />
                    {g}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-auto rounded-2xl bg-surface-1 p-4 ring-1 ring-line">
          <p className="flex items-center gap-2 text-xs font-semibold text-text-2">
            <span
              className={`size-2 rounded-full ${!health.data ? "bg-surface-3" : health.data.status === "ok" ? "bg-[#3ddc97]" : "bg-[#f7c548]"}`}
              aria-hidden
            />
            {!health.data ? (health.isError ? "Backend not reachable" : "Checking models…") : health.data.status === "ok" ? "Models loaded · on-device" : "Models not loaded"}
          </p>
          <p className="mt-1.5 text-xs leading-relaxed text-text-3">
            Every recommendation is computed on this machine from MovieLens 1M. No cloud, no paid APIs.
          </p>
        </div>
      </aside>

      <div className="lg:pl-[248px]">
        <header className="sticky top-0 z-30 border-b border-line/0 bg-bg/80 backdrop-blur-xl">
          <div className="flex h-16 items-center gap-4 px-4 sm:px-6 lg:px-10">
            <NavLink to={profileId ? "/home" : "/"} className="lg:hidden" aria-label="ReelMind home">
              <Logo />
            </NavLink>
            <TopSearch />
            <div className="ml-auto">
              <ProfileButton />
            </div>
          </div>
        </header>
        <main className="px-4 pb-28 pt-4 sm:px-6 lg:px-10 lg:pb-16">{children}</main>
        <footer className="hidden px-10 pb-10 text-xs text-text-3 lg:block">
          Data: MovieLens 1M (GroupLens, 2000–2003) and community tags from MovieLens 32M. Posters from Wikipedia, cached
          locally for educational use; films without one get generated artwork.
        </footer>
      </div>

      <nav
        aria-label="Mobile"
        className="fixed inset-x-0 bottom-0 z-40 grid border-t border-line bg-bg/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
        style={{ gridTemplateColumns: `repeat(${nav.length}, minmax(0, 1fr))` }}
      >
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `flex flex-col items-center gap-1 py-2.5 text-[11px] font-semibold ${isActive ? "text-text" : "text-text-3"}`}
          >
            <Icon className="size-5" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
