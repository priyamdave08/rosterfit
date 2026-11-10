// Route chunks, loaded on first visit and preloaded when a tab is hovered or focused
// (React best practices: bundle-preload), so switching workspaces rarely waits on the network.
export const loadDraftRoom = () => import("../pages/DraftRoom");
export const loadMoves = () => import("../pages/Moves");
export const loadPlayerCards = () => import("../pages/PlayerCards");
export const loadModelCard = () => import("../pages/ModelCard");

const byPath: Record<string, () => Promise<unknown>> = {
  "/draft": loadDraftRoom,
  "/moves": loadMoves,
  "/players": loadPlayerCards,
  "/model": loadModelCard,
};

export function preloadRoute(path: string): void {
  void byPath[path]?.().catch(() => undefined);
}
