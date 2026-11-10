import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import { prefersReducedMotion } from "../lib/motion";
import { plural } from "../lib/format";
import type { LineupDetail } from "../lib/types";
import { Court, pctX, pctY, sx, sy } from "./Court";
import { Twill } from "./Twill";
import s from "./SpacingMap.module.css";

const PERIMETER = new Set(["corner", "wing", "top"]);

/**
 * The signature view: the unit's five players stand on the half court as their own jersey
 * numbers, inside a ring sized by how far the defense must stretch to guard them. When the
 * unit changes, players who stay glide to their new spot and new players settle in.
 */
export function SpacingMap({ detail, title }: { detail: LineupDetail; title: string }) {
  const root = useRef<HTMLDivElement>(null);
  const prev = useRef<Map<string, { x: number; y: number; r: number }>>(new Map());
  const byId = new Map(detail.players.map((p) => [p.id, p]));
  // Animate on what is drawn, not on object identity: a refetch that hands back an equal unit
  // must not re-run (and so revert) the glide and the stitch mid-flight.
  const layout = detail.spacing.players.map((sp) => `${sp.id ?? sp.player}@${sp.x},${sp.y},${sp.radius}`).join("|");

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const now = new Map(detail.spacing.players.map((sp) => [sp.id ?? sp.player, { x: sp.x, y: sp.y, r: sp.radius }]));
    const reduced = prefersReducedMotion();
    const ctx = gsap.context(() => {
      if (reduced) return;
      for (const [key, pos] of now) {
        const marker = el.querySelector<HTMLElement>(`div[data-key="${CSS.escape(key)}"]`);
        const ring = el.querySelector<SVGCircleElement>(`circle[data-key="${CSS.escape(key)}"]`);
        if (!marker || !ring) continue;
        const before = prev.current.get(key);
        if (before) {
          // On-screen movement: transform only, strong ease-in-out, under 300ms.
          const layer = marker.parentElement!;
          const dx = ((pctX(before.x) - pctX(pos.x)) / 100) * layer.clientWidth;
          const dy = ((pctY(before.y) - pctY(pos.y)) / 100) * layer.clientHeight;
          if (dx || dy) gsap.fromTo(marker, { x: dx, y: dy }, { x: 0, y: 0, duration: 0.28, ease: "power4.inOut" });
          if (before.x !== pos.x || before.y !== pos.y || before.r !== pos.r)
            gsap.fromTo(ring, { attr: { cx: sx(before.x), cy: sy(before.y), r: before.r } }, { attr: { cx: sx(pos.x), cy: sy(pos.y), r: pos.r }, duration: 0.28, ease: "power4.inOut" });
        } else if (prev.current.size) {
          // A player new to the unit settles in from 95% (never from nothing).
          gsap.fromTo(marker, { opacity: 0, scale: 0.95 }, { opacity: 1, scale: 1, duration: 0.2, ease: "power3.out" });
          gsap.fromTo(ring, { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "power3.out" });
        }
        // Any player new to the unit (a builder swap, a different unit, a roster move) has his
        // outer twill layer stitched back on, once. The dash covers the whole glyph outline.
        if (!before && prev.current.size) {
          const stitch = marker.querySelector<SVGTextElement>("[data-stitch]");
          if (stitch) {
            const len = Math.ceil(Math.max(stitch.getComputedTextLength(), 10) * 5);
            gsap.fromTo(stitch, { strokeDasharray: len, strokeDashoffset: len }, { strokeDashoffset: 0, duration: 0.6, ease: "power3.out", delay: 0.1, clearProps: "strokeDasharray,strokeDashoffset" });
          }
        }
      }
    }, el);
    prev.current = now;
    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed on the drawn layout on purpose
  }, [layout]);

  const { perimeter_threats, paint_bodies, congested } = detail.spacing;
  return (
    <figure className={s.figure} ref={root}>
      <figcaption className={s.title}>{title}</figcaption>
      <Court
        label={`${title}. ${detail.spacing.players.map((sp) => `${sp.player} at ${sp.spot}`).join(", ")}.`}
        svg={detail.spacing.players.map((sp) => {
          const key = sp.id ?? sp.player;
          const isNew = detail.highlight != null && sp.id === detail.highlight;
          const kind = isNew ? "incoming" : PERIMETER.has(sp.kind) ? "perimeter" : "paint";
          return <circle key={key} data-key={key} className={`${s.ring} ${s[kind]}`} cx={sx(sp.x)} cy={sy(sp.y)} r={sp.radius} />;
        })}
        overlay={detail.spacing.players.map((sp) => {
          const key = sp.id ?? sp.player;
          const person = (sp.id && byId.get(sp.id)) || { name: sp.player, jersey: null, short: sp.player.split(" ").pop() ?? sp.player };
          const isNew = detail.highlight != null && sp.id === detail.highlight;
          return (
            <div key={key} data-key={key} className={s.marker} style={{ left: `${pctX(sp.x)}%`, top: `${pctY(sp.y)}%` }}>
              <div className={s.markerInner}>
                <Twill person={person} size="md" incoming={isNew} />
                <span className={s.name}>
                  {"short" in person ? person.short : sp.player}
                  {isNew && <span className={s.newTag}> (new)</span>}
                </span>
              </div>
            </div>
          );
        })}
      />
      <div className={s.summary}>
        <p className={congested ? s.congested : undefined} role={congested ? "alert" : undefined}>
          <strong>{plural(perimeter_threats, "perimeter threat")}</strong> the defense must respect.{" "}
          <strong>{plural(paint_bodies, "player")}</strong> living in the paint.{congested ? " The paint is congested." : ""}
        </p>
        <p className={s.legend}>
          <span className={`${s.key} ${s.perimeter}`} aria-hidden="true" /> Perimeter spot{" "}
          <span className={`${s.key} ${s.paint}`} aria-hidden="true" /> Paint spot
          {detail.highlight && (
            <>
              {" "}
              <span className={`${s.key} ${s.incoming}`} aria-hidden="true" /> Incoming player
            </>
          )}
          . Ring size = how far the defense must stretch to guard him.
        </p>
      </div>
    </figure>
  );
}
