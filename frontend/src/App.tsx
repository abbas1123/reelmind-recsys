import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router";
import { AppShell } from "./components/AppShell";
import DiscoverPage from "./pages/DiscoverPage";
import HomePage from "./pages/HomePage";
import MePage from "./pages/MePage";
import MoviePage from "./pages/MoviePage";
import OnboardingPage from "./pages/OnboardingPage";
import ProfilesPage from "./pages/ProfilesPage";
import { CenterSpinner } from "./components/Feedback";
import { useProfile } from "./state/profile";

// Recharts is only needed on the dashboard: keep it out of the main bundle.
const ModelsPage = lazy(() => import("./pages/ModelsPage"));

function RequireProfile({ children }: { children: React.ReactNode }) {
  const { profileId } = useProfile();
  return profileId === null ? <Navigate to="/" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<ProfilesPage />} />
        <Route path="/onboarding" element={<RequireProfile><OnboardingPage /></RequireProfile>} />
        <Route path="/home" element={<RequireProfile><HomePage /></RequireProfile>} />
        <Route path="/discover" element={<DiscoverPage />} />
        <Route path="/movie/:id" element={<MoviePage />} />
        <Route path="/me" element={<RequireProfile><MePage /></RequireProfile>} />
        <Route
          path="/models"
          element={
            <Suspense fallback={<CenterSpinner label="Loading dashboard" />}>
              <ModelsPage />
            </Suspense>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
