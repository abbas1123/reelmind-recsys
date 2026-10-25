import { Button, Input, Label, TextField } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../api/client";
import type { User } from "../api/types";
import { ErrorAlert, Notice } from "../components/Feedback";
import { useProfile } from "../state/profile";

const fieldInput = "h-11 rounded-none border-0 border-b border-rule-strong bg-transparent px-0 text-[15px] shadow-none focus:border-amber";

export default function ProfilesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { select, profileId } = useProfile();
  const [name, setName] = useState("");
  const [mlId, setMlId] = useState("1");
  // Always refetch on open: profiles and their counts change on other pages without touching this cache.
  const users = useQuery({ queryKey: ["users"], queryFn: api.users, staleTime: 0 });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });

  const enter = (u: User) => {
    select(u.id);
    qc.setQueryData(["user", u.id], u);
    navigate(u.onboarding_done ? "/home" : "/onboarding");
  };
  const create = useMutation({ mutationFn: () => api.createUser(name.trim()), onSuccess: enter });
  const fromMl = useMutation({ mutationFn: () => api.movielensProfile(Number(mlId)), onSuccess: enter });
  const mlValid = /^\d+$/.test(mlId) && Number(mlId) >= 1 && Number(mlId) <= 6040;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-14">
      <section className="grid gap-8 pt-6 md:grid-cols-[1.4fr_1fr] md:items-end">
        <div>
          <p className="kicker">Tonight · {new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}</p>
          <h1 className="mt-4 font-display text-[56px] leading-[0.92] tracking-[-0.02em] sm:text-[80px]">
            Who&rsquo;s watching<span className="text-amber">?</span>
          </h1>
        </div>
        <p className="max-w-sm text-[15px] leading-relaxed text-paper-2">
          Every recommendation here is computed on this machine from 1,000,209 real MovieLens ratings — no cloud, no
          paid APIs. Pick a profile, start a new one, or borrow the history of a real MovieLens viewer.
        </p>
      </section>

      {health.data?.status === "degraded" && (
        <Notice title="Models not loaded" tone="signal">
          {health.data.detail}
        </Notice>
      )}
      {users.error && <ErrorAlert error={users.error} onRetry={() => users.refetch()} />}

      {users.data && users.data.length > 0 && (
        <section aria-label="Existing profiles">
          <p className="kicker mb-3">Profiles on this machine</p>
          <ul className="border-t border-rule">
            {users.data.map((u, i) => (
              <li key={u.id}>
                <button
                  onClick={() => enter(u)}
                  data-testid="profile-tile"
                  className="group grid w-full grid-cols-[2.5rem_1fr_auto] items-baseline gap-4 border-b border-rule py-4 text-left outline-none focus-visible:bg-ink-raised"
                >
                  <span className="font-mono text-[11px] text-paper-3">{String(i + 1).padStart(2, "0")}</span>
                  <span className="truncate font-display text-[30px] leading-none transition-colors group-hover:text-amber">
                    {u.display_name}
                    {u.id === profileId && <span className="ml-3 align-middle font-mono text-[10px] tracking-[0.18em] text-amber">CURRENT</span>}
                  </span>
                  <span className="font-mono text-[11px] text-paper-3 tabular">
                    {u.ml_user_id ? `MovieLens #${u.ml_user_id}` : `${u.n_ratings} rated · ${u.n_favorites} saved`}
                    <span className="ml-3 inline-block transition-transform group-hover:translate-x-1">→</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="grid gap-12 border-t border-rule pt-8 md:grid-cols-2 md:gap-16">
        <form
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <div>
            <p className="kicker">A — New profile</p>
            <h2 className="mt-2 font-display text-[30px] leading-tight">Start from nothing</h2>
            <p className="mt-2 text-sm leading-relaxed text-paper-2">
              Choose a few genres, rate what you know, and watch the system move from popularity to collaborative filtering.
            </p>
          </div>
          <TextField value={name} onChange={setName} aria-label="Profile name" className="flex flex-col gap-1">
            <Label className="kicker">Name</Label>
            <Input placeholder="e.g. Aysel" data-testid="new-profile-name" maxLength={80} className={fieldInput} />
          </TextField>
          <div>
            <Button type="submit" variant="primary" isDisabled={!name.trim() || create.isPending} data-testid="create-profile">
              Create profile
            </Button>
          </div>
          {create.error && <p className="text-sm text-signal">{(create.error as Error).message}</p>}
        </form>

        <form
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (mlValid) fromMl.mutate();
          }}
        >
          <div>
            <p className="kicker">B — Borrow a history</p>
            <h2 className="mt-2 font-display text-[30px] leading-tight">Watch as a MovieLens viewer</h2>
            <p className="mt-2 text-sm leading-relaxed text-paper-2">
              Load one of 6,040 real rating histories (ids 1–6040) to see what the trained models do for an established user.
            </p>
          </div>
          <TextField value={mlId} onChange={setMlId} aria-label="MovieLens user id" className="flex flex-col gap-1">
            <Label className="kicker">MovieLens user id</Label>
            <Input inputMode="numeric" data-testid="ml-user-id" className={`${fieldInput} font-mono`} />
          </TextField>
          <div>
            <Button type="submit" variant="outline" isDisabled={!mlValid || fromMl.isPending} data-testid="open-ml-user">
              Open history
            </Button>
          </div>
          {fromMl.error && <p className="text-sm text-signal">{(fromMl.error as Error).message}</p>}
        </form>
      </section>
    </div>
  );
}
