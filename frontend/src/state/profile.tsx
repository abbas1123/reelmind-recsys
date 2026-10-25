import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { User } from "../api/types";

const KEY = "reelmind.profileId";

function readStored(): number | null {
  try {
    const v = localStorage.getItem(KEY);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}

interface ProfileCtx {
  profileId: number | null;
  profile: User | undefined;
  isLoading: boolean;
  select: (id: number | null) => void;
  refresh: () => void;
}

const Ctx = createContext<ProfileCtx | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileId] = useState<number | null>(readStored);
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["user", profileId],
    queryFn: () => api.user(profileId!),
    enabled: profileId !== null,
    retry: false,
  });

  const select = useCallback(
    (id: number | null) => {
      try {
        if (id === null) localStorage.removeItem(KEY);
        else localStorage.setItem(KEY, String(id));
      } catch {
        /* storage unavailable: keep in memory */
      }
      setProfileId(id);
      qc.invalidateQueries({ queryKey: ["recs"] });
    },
    [qc],
  );

  // A stored id whose profile was deleted falls back to the profile picker.
  const stale = query.isError && profileId !== null;
  const value = useMemo<ProfileCtx>(
    () => ({
      profileId: stale ? null : profileId,
      profile: stale ? undefined : query.data,
      isLoading: query.isLoading,
      select,
      refresh: () => qc.invalidateQueries({ queryKey: ["user", profileId] }),
    }),
    [profileId, query.data, query.isLoading, select, qc, stale],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useProfile(): ProfileCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useProfile outside ProfileProvider");
  return ctx;
}
