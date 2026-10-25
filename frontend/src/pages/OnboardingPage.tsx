import { Button } from "@heroui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../api/client";
import { CenterSpinner, ErrorAlert } from "../components/Feedback";
import { Poster } from "../components/Poster";
import { RatingStars } from "../components/RatingStars";
import { genreColor } from "../lib/genre";
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
    <div className="mx-auto flex max-w-6xl flex-col gap-8 pb-24">
      <header className="flex flex-col gap-4">
        <div className="flex items-center gap-2" aria-label={`Step ${step} of 2`}>
          {[1, 2].map((s) => (
            <span key={s} className={`h-1.5 w-12 rounded-full ${s <= step ? "bg-brand" : "bg-surface-3"}`} />
          ))}
          <span className="ml-2 text-xs font-semibold text-text-3">Step {step} of 2</span>
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-5xl">{step === 1 ? "What do you love to watch?" : "Rate a few you’ve seen"}</h1>
        <p className="max-w-2xl text-text-2">
          {step === 1
            ? `Pick at least ${MIN_GENRES} genres. Until you have rated five films they steer your cold-start picks.`
            : "Every rating is folded into the trained models instantly — nothing is retrained. Skip anything you haven't seen."}
        </p>
      </header>

      {step === 1 && (
        <>
          {genres.isLoading && <CenterSpinner label="Loading genres" />}
          {genres.error && <ErrorAlert error={genres.error} onRetry={() => genres.refetch()} />}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" role="group" aria-label="Genres">
            {genres.data?.map((g) => {
              const on = picked.includes(g.name);
              return (
                <button
                  key={g.name}
                  type="button"
                  aria-pressed={on}
                  data-testid={`genre-${g.name}`}
                  onClick={() => toggle(g.name)}
                  className={`relative flex h-28 flex-col justify-between overflow-hidden rounded-2xl p-4 text-left font-bold text-white outline-none transition duration-200 focus-visible:ring-2 focus-visible:ring-white ${
                    on ? "scale-[1.02] ring-2 ring-white" : "opacity-80 hover:opacity-100"
                  }`}
                  style={{ background: `linear-gradient(135deg, ${genreColor(g.name)}, ${genreColor(g.name)}99)` }}
                >
                  <span className="text-lg leading-tight">{g.name}</span>
                  <span className="flex items-center justify-between text-xs font-semibold text-white/80">
                    {g.n_items} films
                    <span className={`grid size-6 place-items-center rounded-full ${on ? "bg-white text-black" : "bg-black/25"}`} aria-hidden>
                      {on && <Check className="size-4" />}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
          {savePrefs.error && <ErrorAlert error={savePrefs.error} />}
        </>
      )}

      {step === 2 && (
        <>
          {candidates.isLoading && <CenterSpinner label="Finding well-known titles" />}
          {candidates.error && <ErrorAlert error={candidates.error} />}
          {rate.error && <ErrorAlert error={rate.error} />}
          <div className="grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {candidates.data?.map((item) => (
              <div key={item.id} className="flex flex-col gap-2" data-testid="onboarding-item">
                <div className={`relative aspect-[2/3] overflow-hidden rounded-xl ring-1 transition ${ratings[item.id] ? "ring-2 ring-gold" : "ring-white/5"}`}>
                  <Poster item={item} />
                </div>
                <p className="truncate text-sm font-semibold" title={item.title}>
                  {item.title}
                </p>
                <RatingStars size="sm" value={ratings[item.id] ?? null} label={`Rate ${item.title}`} onChange={(r) => rate.mutate({ id: item.id, r })} />
              </div>
            ))}
          </div>
        </>
      )}

      <div className="fixed inset-x-0 bottom-[60px] z-30 border-t border-line bg-bg/90 backdrop-blur-xl lg:bottom-0 lg:left-[248px]">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          {step === 1 ? (
            <>
              <span className="truncate text-sm text-text-3">
                {picked.length}/{MIN_GENRES} selected{picked.length ? ` · ${picked.join(", ")}` : ""}
              </span>
              <Button
                variant="primary"
                className="rounded-full px-6"
                isDisabled={picked.length < MIN_GENRES || savePrefs.isPending}
                onPress={() => savePrefs.mutate()}
                data-testid="genres-continue"
              >
                Continue
              </Button>
            </>
          ) : (
            <>
              <span className="text-sm font-semibold text-text-2 tabular" data-testid="rated-count">
                {nRated} rated
              </span>
              <div className="flex gap-2">
                <Button variant="ghost" className="rounded-full" onPress={() => setStep(1)}>
                  Back
                </Button>
                <Button variant="primary" className="rounded-full px-6" onPress={finish} data-testid="onboarding-finish">
                  {nRated ? "See my picks" : "Skip for now"}
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
