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
import { TeamProvider } from "./lib/team";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60_000, retry: 1, refetchOnWindowFocus: false } },
});

startSmoothScroll();

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
