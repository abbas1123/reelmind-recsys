import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router";
import { useProfile } from "../state/profile";

const THEME_KEY = "reelmind.theme";

function initialTheme(): "dark" | "light" {
  try {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

const NAV = [
  { to: "/home", label: "Programme", needsProfile: true },
  { to: "/discover", label: "Discover", needsProfile: false },
  { to: "/me", label: "My list", needsProfile: true },
  { to: "/models", label: "Evaluation", needsProfile: false },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { profile, profileId } = useProfile();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#12100d" : "#f3eee4");
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-40 border-b border-rule bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-[1320px] items-center gap-6 px-5 sm:px-8">
          <NavLink to={profileId ? "/home" : "/"} className="flex items-baseline gap-2" aria-label="ReelMind home">
            <span className="font-display text-[26px] italic leading-none tracking-[-0.02em]">ReelMind</span>
            <span className="hidden font-mono text-[9px] tracking-[0.2em] text-paper-3 sm:inline">LOCAL&nbsp;CINEMATHEQUE</span>
          </NavLink>

          <nav aria-label="Main" className="scroll-row flex min-w-0 items-center gap-5 overflow-x-auto">
            {NAV.filter((n) => !n.needsProfile || profileId).map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `relative whitespace-nowrap py-4 text-[13px] transition-colors ${
                    isActive
                      ? "text-paper after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-amber"
                      : "text-paper-3 hover:text-paper"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-4">
            <button
              type="button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="kicker hidden hover:text-paper sm:block"
              aria-label={theme === "dark" ? "Switch to paper (light) theme" : "Switch to ink (dark) theme"}
            >
              {theme === "dark" ? "Paper" : "Ink"}
            </button>
            <button
              type="button"
              onClick={() => navigate("/")}
              className="group flex items-center gap-2 border-l border-rule pl-4 text-left"
              aria-label="Switch profile"
            >
              <span className="kicker hidden md:inline">Viewing as</span>
              <span className="max-w-40 truncate text-[13px] text-paper group-hover:text-amber" data-testid="current-profile">
                {profile?.display_name ?? "Choose profile"}
              </span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1320px] flex-1 px-5 py-10 sm:px-8">{children}</main>

      <footer className="border-t border-rule">
        <div className="mx-auto grid max-w-[1320px] gap-4 px-5 py-8 text-[12px] text-paper-3 sm:grid-cols-3 sm:px-8">
          <p>
            <span className="font-display text-base italic text-paper-2">ReelMind</span> — recommendations computed entirely on
            this machine.
          </p>
          <p>Data: MovieLens 1M (GroupLens, 2000–2003) and community tags from MovieLens 32M.</p>
          <p className="sm:text-right">Covers are typeset from metadata; the dataset contains no artwork.</p>
        </div>
      </footer>
    </div>
  );
}
