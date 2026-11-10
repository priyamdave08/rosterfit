// Motion setup: Lenis smooth scrolling driven by GSAP's ticker, both off for anyone who asks
// the OS for reduced motion. Motion in RosterFit marks state changes; it never decorates.
import gsap from "gsap";
import Lenis from "lenis";

export const prefersReducedMotion = (): boolean =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let lenis: Lenis | null = null;

export function startSmoothScroll(): () => void {
  if (prefersReducedMotion() || lenis) return () => undefined;
  lenis = new Lenis({ duration: 0.9, easing: (t) => 1 - Math.pow(1 - t, 4), smoothWheel: true });
  const tick = (time: number) => lenis?.raf(time * 1000);
  gsap.ticker.add(tick);
  gsap.ticker.lagSmoothing(0);
  return () => {
    gsap.ticker.remove(tick);
    lenis?.destroy();
    lenis = null;
  };
}

export function scrollToTop(): void {
  if (lenis) lenis.scrollTo(0, { immediate: true });
  else window.scrollTo(0, 0);
}
