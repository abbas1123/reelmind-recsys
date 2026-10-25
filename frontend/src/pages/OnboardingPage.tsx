import { Button } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../api/client";
import { CoverArt } from "../components/CoverArt";
import { CenterSpinner, ErrorAlert } from "../components/Feedback";
import { RatingStars } from "../components/RatingStars";
import { GENRE_TONES } from "../lib/genre";
import { useProfile } from "../state/profile";

const MIN_GENRES = 3;

export default function OnboardingPage() {
  const { profile, profileId, refresh } = useProfile();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [step, setStep] = useState<1 | 2>(1);
  const [picked, setPicked] = useState<string[]>(profile?.preferred_genres ?? []);
  const [ratings, setRatings] = useState<Record<number, number>>({});
  const genres = useQuery({ queryKey: ["genres"], queryFn: api.genres });
  const candidates = useQuery({
    queryKey: ["onboarding", picked],
    queryFn: () => api.onboardingCandidates(picked, 18),
    enabled: step === 2,
  });

  const savePrefs = useMutation({
    mutationFn: () => api.setPreferences(profileId!, picked),
    onSuccess: () => {
      refresh();
      setStep(2);
    },
  });
  const rate = useMutation({
    mutationFn: ({ id, r }: { id: number; r: number }) => api.rate(profileId!, id, r),
    onSuccess: (_, v) => setRatings((prev) => ({ ...prev, [v.id]: v.r })),
  });

  const finish = () => {
    qc.invalidateQueries({ queryKey: ["recs"] });
    refresh();
    navigate("/home");
  };
  const toggle = (g: string) => setPicked((p) => (p.includes(g) ? p.filter((x) => x !== g) : [...p, g]));
  const nRated = Object.keys(ratings).length;

  return (
    <div className="flex flex-col gap-10">
      <header className="grid gap-6 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <p className="kicker">Onboarding · step {step} of 2</p>
          <h1 className="mt-3 font-display text-[48px] leading-[0.95] tracking-[-0.02em] sm:text-[64px]">
            {step === 1 ? "What do you watch?" : "Rate what you know."}
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-paper-2">
            {step === 1
              ? `Choose at least ${MIN_GENRES} genres. Until you have rated five films they steer the cold-start ranking.`
              : "Each rating is folded into the trained models instantly — nothing is retrained. Skip anything you haven't seen."}
          </p>
        </div>
        <ol className="flex gap-1 font-mono text-[11px]" aria-label="Progress">
          {[1, 2].map((s) => (
            <li key={s} className={`h-1 w-16 ${s <= step ? "bg-amber" : "bg-rule"}`} aria-current={s === step ? "step" : undefined}>
              <span className="sr-only">Step {s}</span>
            </li>
          ))}
        </ol>
      </header>

      {step === 1 && (
        <>
          {genres.isLoading && <CenterSpinner label="Loading genres" />}
          {genres.error && <ErrorAlert error={genres.error} onRetry={() => genres.refetch()} />}
          <div className="grid grid-cols-2 gap-px border border-rule bg-rule sm:grid-cols-3 lg:grid-cols-6" role="group" aria-label="Genres">
            {genres.data?.map((g) => {
              const on = picked.includes(g.name);
              const tone = GENRE_TONES[g.name] ?? ["#2a2622", "#eee7dc", "#9a8f7d"];
              return (
                <button
                  key={g.name}
                  type="button"
                  aria-pressed={on}
                  data-testid={`genre-${g.name}`}
                  onClick={() => toggle(g.name)}
                  className="group relative flex h-28 flex-col justify-between overflow-hidden p-3 text-left outline-none transition-colors focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-amber"
                  style={
                    on
                      ? { background: tone[0], color: tone[1], boxShadow: "inset 0 0 0 2px var(--amber)" }
                      : { background: "var(--ink)" }
                  }
                >
                  <span className="pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full opacity-70" style={{ background: tone[2], opacity: on ? 0.9 : 0.12 }} />
                  <span className="relative flex items-center justify-between font-mono text-[10px]">
                    <span className={on ? "opacity-90" : "text-paper-3"}>{g.n_items} films</span>
                    <span
                      className={`grid h-4 w-4 place-items-center rounded-full border text-[9px] ${on ? "border-transparent bg-amber text-amber-ink" : "border-rule-strong"}`}
                      aria-hidden
                    >
                      {on ? "✓" : ""}
                    </span>
                  </span>
                  <span className={`relative font-display text-[26px] leading-none ${on ? "" : "text-paper-2 group-hover:text-paper"}`}>{g.name}</span>
                </button>
              );
            })}
          </div>
          {savePrefs.error && <ErrorAlert error={savePrefs.error} />}
          <div className="flex items-center gap-4 border-t border-rule pt-5">
            <Button
              variant="primary"
              isDisabled={picked.length < MIN_GENRES || savePrefs.isPending}
              onPress={() => savePrefs.mutate()}
              data-testid="genres-continue"
            >
              Continue
            </Button>
            <span className="font-mono text-[11px] text-paper-3 tabular">
              {picked.length}/{MIN_GENRES} chosen{picked.length ? ` — ${picked.join(", ")}` : ""}
            </span>
          </div>
        </>
      )}

      {step === 2 && (
        <>
          {candidates.isLoading && <CenterSpinner label="Finding well-known titles" />}
          {candidates.error && <ErrorAlert error={candidates.error} />}
          {rate.error && <ErrorAlert error={rate.error} />}
          <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 md:grid-cols-6">
            {candidates.data?.map((item) => (
              <div key={item.id} className="flex flex-col gap-2" data-testid="onboarding-item">
                <CoverArt item={item} />
                <p className="truncate text-[13px] font-medium" title={item.title}>
                  {item.title}
                </p>
                <RatingStars size="sm" value={ratings[item.id] ?? null} label={`Rate ${item.title}`} onChange={(r) => rate.mutate({ id: item.id, r })} />
              </div>
            ))}
          </div>
          <div className="sticky bottom-0 -mx-5 flex items-center justify-between gap-3 border-t border-rule bg-ink/95 px-5 py-4 backdrop-blur sm:-mx-8 sm:px-8">
            <span className="font-mono text-[12px] text-paper-2 tabular" data-testid="rated-count">
              {nRated} rated
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" onPress={() => setStep(1)}>
                Back
              </Button>
              <Button variant="primary" onPress={finish} data-testid="onboarding-finish">
                {nRated ? "See my programme" : "Skip for now"}
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
