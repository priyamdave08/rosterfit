import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { ErrorState, Skeleton } from "./components/States";
import { useTeam } from "./lib/team";
import { LineupLab } from "./pages/LineupLab";

const DraftRoom = lazy(() => import("./pages/DraftRoom").then((m) => ({ default: m.DraftRoom })));
const Moves = lazy(() => import("./pages/Moves").then((m) => ({ default: m.Moves })));
const PlayerCards = lazy(() => import("./pages/PlayerCards").then((m) => ({ default: m.PlayerCards })));
const ModelCardPage = lazy(() => import("./pages/ModelCard").then((m) => ({ default: m.ModelCardPage })));

export function App() {
  const { error, isLoading, team } = useTeam();
  return (
    <Shell>
      {error ? (
        <ErrorState error={error} onRetry={() => window.location.reload()} />
      ) : isLoading ? (
        <Skeleton height={480} label="Loading teams and rosters" />
      ) : (
        <Suspense fallback={<Skeleton height={480} label="Opening workspace" />}>
          <Routes>
            <Route path="/" element={<LineupLab key={team} />} />
            <Route path="/draft" element={<DraftRoom key={team} />} />
            <Route path="/moves" element={<Moves key={team} />} />
            <Route path="/players" element={<PlayerCards />} />
            <Route path="/model" element={<ModelCardPage />} />
            <Route
              path="*"
              element={
                <div>
                  <h1>Page not found</h1>
                  <p style={{ marginTop: 8 }}>
                    That workspace doesn't exist. <Link to="/">Go to the Lineup Lab</Link>.
                  </p>
                </div>
              }
            />
          </Routes>
        </Suspense>
      )}
    </Shell>
  );
}
