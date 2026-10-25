import { Button, Input, Label, TextField } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, UserPlus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../api/client";
import type { User } from "../api/types";
import { avatarGradient, initials } from "../components/AppShell";
import { ErrorAlert, Notice } from "../components/Feedback";
import { useProfile } from "../state/profile";

const field = "h-12 rounded-full bg-surface-2 px-5 text-[15px] ring-1 ring-line focus:ring-2 focus:ring-brand";

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
    <div className="mx-auto flex max-w-5xl flex-col items-center gap-12 py-6 sm:py-10">
      <div className="text-center">
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-6xl">Who&rsquo;s watching?</h1>
        <p className="mx-auto mt-4 max-w-xl text-base text-text-2">
          Recommendations computed on this machine from <span className="font-semibold text-text">1,000,209</span> real
          MovieLens ratings. Pick a profile, start fresh, or borrow a real viewer&rsquo;s history.
        </p>
      </div>

      {health.data?.status === "degraded" && <Notice title="Models are not loaded">{health.data.detail}</Notice>}
      {users.error && <ErrorAlert error={users.error} onRetry={() => users.refetch()} />}

      {users.data && users.data.length > 0 && (
        <section aria-label="Existing profiles" className="flex flex-wrap justify-center gap-6 sm:gap-8">
          {users.data.map((u) => (
            <button
              key={u.id}
              onClick={() => enter(u)}
              data-testid="profile-tile"
              className="group flex w-28 flex-col items-center gap-3 outline-none sm:w-36"
            >
              <span
                className={`grid aspect-square w-full place-items-center rounded-3xl text-3xl font-extrabold text-white shadow-xl shadow-black/40 ring-offset-4 ring-offset-bg transition duration-300 group-hover:scale-105 group-hover:ring-4 group-hover:ring-white group-focus-visible:ring-4 group-focus-visible:ring-brand sm:text-4xl ${
                  u.id === profileId ? "ring-2 ring-white/70" : ""
                }`}
                style={{ background: avatarGradient(u.id) }}
                aria-hidden
              >
                {initials(u.display_name)}
              </span>
              <span className="w-full truncate text-center text-sm font-semibold text-text-2 group-hover:text-text">{u.display_name}</span>
              <span className="-mt-2 text-xs text-text-3">{u.ml_user_id ? "MovieLens history" : `${u.n_ratings} rated`}</span>
            </button>
          ))}
        </section>
      )}

      <section className="grid w-full gap-4 md:grid-cols-2">
        <form
          className="flex flex-col gap-5 rounded-3xl bg-surface-1 p-6 ring-1 ring-line sm:p-8"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-2xl bg-brand text-white" aria-hidden>
              <UserPlus className="size-5" />
            </span>
            <div>
              <h2 className="text-lg font-bold">New profile</h2>
              <p className="text-sm text-text-3">Start cold and watch it learn your taste.</p>
            </div>
          </div>
          <TextField value={name} onChange={setName} aria-label="Profile name" className="flex flex-col gap-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-text-3">Name</Label>
            <Input placeholder="e.g. Aysel" data-testid="new-profile-name" maxLength={80} className={field} />
          </TextField>
          <Button type="submit" variant="primary" size="lg" isDisabled={!name.trim() || create.isPending} data-testid="create-profile" className="rounded-full">
            Create profile
          </Button>
          {create.error && <p className="text-sm text-[#ff5a6e]">{(create.error as Error).message}</p>}
        </form>

        <form
          className="flex flex-col gap-5 rounded-3xl bg-surface-1 p-6 ring-1 ring-line sm:p-8"
          onSubmit={(e) => {
            e.preventDefault();
            if (mlValid) fromMl.mutate();
          }}
        >
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-2xl bg-surface-3 text-white" aria-hidden>
              <Database className="size-5" />
            </span>
            <div>
              <h2 className="text-lg font-bold">Watch as a MovieLens viewer</h2>
              <p className="text-sm text-text-3">Load one of 6,040 real rating histories.</p>
            </div>
          </div>
          <TextField value={mlId} onChange={setMlId} aria-label="MovieLens user id" className="flex flex-col gap-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-text-3">MovieLens user id (1–6040)</Label>
            <Input inputMode="numeric" data-testid="ml-user-id" className={`${field} tabular`} />
          </TextField>
          <Button type="submit" variant="secondary" size="lg" isDisabled={!mlValid || fromMl.isPending} data-testid="open-ml-user" className="rounded-full">
            Open history
          </Button>
          {fromMl.error && <p className="text-sm text-[#ff5a6e]">{(fromMl.error as Error).message}</p>}
        </form>
      </section>
    </div>
  );
}
