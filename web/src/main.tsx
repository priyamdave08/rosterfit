import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/archivo/400.css";
import "@fontsource/archivo/500.css";
import "@fontsource/archivo/600.css";
import "@fontsource/archivo/700.css";
import "@fontsource/archivo-narrow/600.css";
import "@fontsource/graduate/400.css";
import "./styles/base.css";
import { App } from "./App";
import { startSmoothScroll } from "./lib/motion";
import { retryWhileWaking, wakeDelay } from "./lib/api";
import { lineupsQuery } from "./lib/queries";
import { TeamProvider } from "./lib/team";
import { initialTeam } from "./lib/teamStorage";

const queryClient = new QueryClient({
  // The free API sleeps when idle; queries keep retrying while it wakes instead of failing.
  defaultOptions: { queries: { staleTime: 5 * 60_000, retry: retryWhileWaking, retryDelay: wakeDelay, refetchOnWindowFocus: false } },
});

startSmoothScroll();

// The Lineup Lab needs only the team to start ranking, so don't wait for /ui/meta to arrive first.
if (window.location.pathname === "/")
  void queryClient.prefetchQuery({ ...lineupsQuery(initialTeam()), retry: retryWhileWaking, retryDelay: wakeDelay });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <TeamProvider>
          <App />
        </TeamProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
