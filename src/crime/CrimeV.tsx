import React, { useEffect, useState } from 'react';
import { AbsoluteFill, Audio, Img, Sequence, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

// Vertical (1080×1920) true-crime video laid out as the owner's sample 00-video-mau/MAU-HO-SO.mp4: a case file on a
// dark board. Black-and-white press prints with a white border, slightly turned; paper tapes slapped on when the voice
// names a thing; typed cards, a ticked notebook list, a case folder; big typewriter numbers; cut-out objects; red
// strings between prints; a chapter head at the top; the spoken words in a small white box under the board. Every
// position comes from scripts/crime/layout.py via build.py: this file only draws the plan and animates entrances.
type View = [number, number, number, number];
type Box = [number, number, number, number];
type Ring = { s: number; box: View; shape: 'ellipse' | 'rect'; color: string };
type Base = { s: number; e?: number };
export type PhotoI = Base & { type: 'photo'; src: string; w: number; h: number; box: Box; view: View; rot: number; ai: boolean;
  credit: string; drift: number; zoom?: { to: View; s: number; e: number }; rings: Ring[] };
export type StickerI = Base & { type: 'sticker'; src: string; w: number; h: number; box: Box; rot: number; ai: boolean; credit: string };
export type TapeI = Base & { type: 'tape'; text: string; color: 'yellow' | 'red' | 'white'; px: number; x: number; y: number;
  align: 'left' | 'right' | 'center'; rot: number };
export type Row = { l: string; r: string; s: number; color: string };
export type CardI = Base & { type: 'card'; style: 'paper' | 'lined' | 'folder'; box: Box; rot: number; head: string; rows: Row[];
  tab: string; corner: string; note: { text: string; s: number } | null; stamp: { text: string; s: number } | null };
export type StatI = Base & { type: 'stat'; x: number; y: number; rows: { n: string; text: string; s: number; color: string }[] };
export type StringI = Base & { type: 'string'; a: [number, number]; b: [number, number] };
export type Item = PhotoI | StickerI | TapeI | CardI | StatI | StringI;
export type Head = { kicker: string; title: string; mode: 'top' | 'mid'; from: 'top' | 'mid' | null; s: number };
export type Scene = { s: number; e: number; scene: number; head: Head | null; items: Item[]; credit: string };
type FontChunk = { family: string; file: string; range: string; weight: string; style: string };
type Faces = { sub: string; mono: string; serif: string; hand: string };
export type PlanC = { duration: number; lang: 'ja' | 'de'; title: string; aiTag: string; faces: Faces; bg: string | null;
  scenes: Scene[]; subs: { s: number; e: number; text: string }[]; voice: { s: number; src: string }[]; music: string | null;
  musicVolume: number; fonts: FontChunk[] };

// layout.py
const SUB_Y = 1600, SUB_W = 940, SUB_PX = 40, CREDIT_Y = 1872, BORDER = 14;
const HEAD_TOP = { kicker: 196, title: 284 }, HEAD_MID = { kicker: 820, title: 922 };
const ROW_H = { paper: 96, lined: 80, folder: 96 };
const STAT_ROW = 170;
const PAPER = '#ebe6da', INK = '#1b1a18', RED = '#b8231b';
const TAPE = { yellow: { bg: '#f1cf3b', fg: '#1d1a12' }, red: { bg: '#c3261e', fg: '#fbf6ee' }, white: { bg: '#ece8df', fg: '#151515' } };

const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);
const ease = (x: number) => { const p = clamp01(x); return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2; };
const easeOut = (x: number) => 1 - Math.pow(1 - clamp01(x), 3);
const backOut = (x: number) => { const p = clamp01(x), c = 1.7; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); };
const hash = (s: string) => { let h = 2166136261; for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619); return h >>> 0; };
const rng = (seed: number) => () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const fam = (f: string, fb: string) => `"${f}", ${fb}`;

// torn paper: an uneven polygon; `side` jags the left and right edges (tapes), else all four slightly
const torn = (seed: string, side = true) => {
  const r = rng(hash(seed)); const p: string[] = [];
  const j = (a: number) => (r() * a).toFixed(2);
  for (let i = 0; i <= 6; i++) p.push(`${(i * 100) / 6}% ${side ? j(4) : j(2.5)}%`);
  for (let i = 1; i <= 5; i++) p.push(`${(100 - (side ? +j(2.2) : +j(1))).toFixed(2)}% ${(i * 100) / 6}%`);
  for (let i = 6; i >= 0; i--) p.push(`${(i * 100) / 6}% ${(100 - (side ? +j(5) : +j(3))).toFixed(2)}%`);
  for (let i = 5; i >= 1; i--) p.push(`${side ? j(2.2) : j(1)}% ${(i * 100) / 6}%`);
  return `polygon(${p.join(',')})`;
};

let fontsLoading: Promise<void> | null = null;
const useFonts = (fonts: FontChunk[], faces: Faces, text: string) => {
  const [h] = useState(() => delayRender('fonts'));
  useEffect(() => {
    (fontsLoading ??= (async () => {
      for (const c of fonts)
        document.fonts.add(new FontFace(c.family, `url(${staticFile(c.file)}) format('woff2')`, { weight: c.weight, style: c.style, unicodeRange: c.range }));
      const want = [`400 40px "${faces.sub}"`, `600 40px "${faces.sub}"`, `400 40px "${faces.mono}"`, `700 40px "${faces.mono}"`,
        `700 40px "${faces.serif}"`, `italic 700 40px "${faces.serif}"`, `400 40px "${faces.hand}"`];
      await Promise.all(want.map((w) => document.fonts.load(w, text)));
    })()).then(() => continueRender(h)).catch((e) => cancelRender(e));
  }, [h, fonts, faces, text]);
};

// region of the picture shown at time t: a zoom when asked for, else a slow push-in (by `drift` over the scene)
export const viewAt = (p: PhotoI, t: number, s: number, e: number): View => {
  if (p.zoom) {
    const k = ease((t - p.zoom.s) / Math.max(0.1, p.zoom.e - p.zoom.s));
    return p.view.map((v, i) => v + (p.zoom!.to[i] - v) * k) as View;
  }
  if (!p.drift) return p.view;
  const k = clamp01((t - s) / Math.max(0.5, e - s)) * p.drift / 2;
  const [a, b, c, d] = p.view, w = c - a, h = d - b;
  return [a + w * k, b + h * k, c - w * k, d - h * k];
};

// a hand-drawn ring: an ellipse with an uneven radius that overshoots its start
const ringPath = (cx: number, cy: number, rx: number, ry: number, seed: string) => {
  const r = rng(hash(seed)); const pts: string[] = []; const a0 = -1.9 + r() * 0.4;
  for (let i = 0; i <= 48; i++) {
    const a = a0 + (i / 48) * Math.PI * 2.18, k = 1 + (r() - 0.5) * 0.035 + (i / 48) * 0.07;
    pts.push(`${(cx + Math.cos(a) * rx * k).toFixed(1)},${(cy + Math.sin(a) * ry * k).toFixed(1)}`);
  }
  return 'M' + pts.join(' L');
};

const AiTag: React.FC<{ tag: string; F: Faces; style?: React.CSSProperties }> = ({ tag, F, style }) => (
  <div style={{ position: 'absolute', padding: '4px 12px', borderRadius: 4, background: 'rgba(0,0,0,.66)', color: 'rgba(255,255,255,.92)',
    fontFamily: fam(F.sub, 'sans-serif'), fontWeight: 600, fontSize: 22, letterSpacing: '0.03em', whiteSpace: 'nowrap', ...style }}>{tag}</div>
);

const Photo: React.FC<{ it: PhotoI; t: number; sc: Scene; tag: string; F: Faces }> = ({ it, t, sc, tag, F }) => {
  const [x, y, bw, bh] = it.box;
  const iw = bw - 2 * BORDER, ih = bh - 2 * BORDER;
  const [v0, v1, v2, v3] = viewAt(it, t, it.s, sc.e);
  const sx = iw / ((v2 - v0) * it.w), sy = ih / ((v3 - v1) * it.h);
  const k = easeOut((t - it.s) / 0.22);
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: bw, height: bh, background: '#eeeae2', opacity: it.s > sc.s + 0.01 ? k : 1,
      transform: `rotate(${it.rot}deg) scale(${it.s > sc.s + 0.01 ? 1.05 - 0.05 * k : 1})`,
      boxShadow: '0 18px 40px rgba(0,0,0,.6), 0 3px 8px rgba(0,0,0,.5)' }}>
      <div style={{ position: 'absolute', left: BORDER, top: BORDER, width: iw, height: ih, overflow: 'hidden', background: '#111' }}>
        <Img src={staticFile(it.src)} style={{ position: 'absolute', left: -v0 * it.w * sx, top: -v1 * it.h * sy, width: it.w * sx, height: it.h * sy, maxWidth: 'none' }} />
        <div style={{ position: 'absolute', inset: 0, boxShadow: 'inset 0 0 40px rgba(0,0,0,.35)' }} />
        <svg width={iw} height={ih} style={{ position: 'absolute', left: 0, top: 0, overflow: 'visible' }}>
          {it.rings.filter((r) => t >= r.s).map((r, i) => {
            const X = (f: number) => ((f - v0) / (v2 - v0)) * iw, Y = (f: number) => ((f - v1) / (v3 - v1)) * ih;
            const [a, b, c, d] = r.box;
            const st = { fill: 'none', stroke: r.color === 'red' ? '#d1281e' : '#f2cc2f', strokeWidth: 7, strokeLinecap: 'round' as const,
              strokeLinejoin: 'round' as const, strokeDasharray: 1, strokeDashoffset: 1 - easeOut((t - r.s) / 0.55),
              filter: 'drop-shadow(0 0 4px rgba(0,0,0,.6))' };
            return r.shape === 'rect'
              ? <rect key={i} pathLength={1} x={X(a)} y={Y(b)} width={X(c) - X(a)} height={Y(d) - Y(b)} rx={8} style={st} />
              : <path key={i} pathLength={1} d={ringPath((X(a) + X(c)) / 2, (Y(b) + Y(d)) / 2, (X(c) - X(a)) / 2, (Y(d) - Y(b)) / 2, it.src + i)} style={st} />;
          })}
        </svg>
        {it.ai ? <AiTag tag={tag} F={F} style={{ left: 10, bottom: 10 }} /> : null}
      </div>
    </div>
  );
};

const Sticker: React.FC<{ it: StickerI; t: number; tag: string; F: Faces }> = ({ it, t, tag, F }) => {
  const [x, y, w, h] = it.box;
  const k = backOut((t - it.s) / 0.32);
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, opacity: clamp01((t - it.s) / 0.08),
      transform: `rotate(${it.rot}deg) scale(${0.55 + 0.45 * k})` }}>
      <Img src={staticFile(it.src)} style={{ width: w, height: h, filter: 'drop-shadow(0 14px 22px rgba(0,0,0,.6))' }} />
      {it.ai ? <AiTag tag={tag} F={F} style={{ left: '50%', bottom: -8, transform: `translateX(-50%) rotate(${-it.rot}deg)` }} /> : null}
    </div>
  );
};

const Tape: React.FC<{ it: TapeI; t: number; F: Faces }> = ({ it, t, F }) => {
  const k = easeOut((t - it.s) / 0.14);
  const tx = it.align === 'left' ? '0' : it.align === 'right' ? '-100%' : '-50%';
  const c = TAPE[it.color];
  const font = it.color === 'yellow' ? { fontFamily: fam(F.hand, 'cursive'), fontWeight: 400 }
    : it.color === 'red' ? { fontFamily: fam(F.serif, 'serif'), fontWeight: 700 } : { fontFamily: fam(F.mono, 'monospace'), fontWeight: 700 };
  return (
    <div style={{ position: 'absolute', left: it.x, top: it.y, opacity: k, whiteSpace: 'nowrap',
      transform: `translate(${tx}, -50%) rotate(${it.rot}deg) scale(${1.3 - 0.3 * k})`, transformOrigin: it.align === 'left' ? '0 50%' : it.align === 'right' ? '100% 50%' : '50% 50%',
      filter: 'drop-shadow(0 4px 6px rgba(0,0,0,.45))' }}>
      <div style={{ ...font, fontSize: it.px, lineHeight: 1.12, color: c.fg, padding: `${it.px * 0.1}px ${it.px * 0.36}px ${it.px * 0.14}px`,
        background: `linear-gradient(180deg, ${c.bg} 0%, ${c.bg} 70%, rgba(0,0,0,.08) 100%), ${c.bg}`, clipPath: torn(it.text + it.color),
        letterSpacing: it.color === 'white' ? '0.04em' : '0' }}>{it.text}</div>
    </div>
  );
};

// text typed in: characters appear one by one (handwriting appears a little faster)
const typed = (s: string, t: number, t0: number, cps = 32) => (t < t0 ? '' : s.slice(0, Math.max(1, Math.floor((t - t0) * cps) + 1)));

const Card: React.FC<{ it: CardI; t: number; sc: Scene; F: Faces }> = ({ it, t, sc, F }) => {
  const [x, y, w, h] = it.box;
  const k = it.s > sc.s + 0.01 ? easeOut((t - it.s) / 0.32) : 1;
  const mono = fam(F.mono, 'monospace'), serif = fam(F.serif, 'serif'), hand = fam(F.hand, 'cursive');
  const lined = it.style === 'lined', folder = it.style === 'folder';
  const top0 = it.head ? 160 : 50, rh = ROW_H[it.style];
  const bg = folder ? 'radial-gradient(ellipse 90% 80% at 50% 45%, #d6c39a 0%, #c4ad7f 75%, #a89064 100%)'
    : lined ? `repeating-linear-gradient(180deg, transparent 0, transparent ${rh - 2}px, rgba(70,110,190,.35) ${rh - 2}px, rgba(70,110,190,.35) ${rh}px), #f2f0ea`
    : `radial-gradient(ellipse 85% 75% at 50% 40%, #f1ede4 0%, ${PAPER} 70%, #d9d2c2 100%)`;
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, opacity: k, transform: `translateY(${(1 - k) * 70}px) rotate(${it.rot}deg)`,
      filter: 'drop-shadow(0 20px 30px rgba(0,0,0,.55))' }}>
      {folder ? (
        <div style={{ position: 'absolute', left: 30, top: -54, width: 360, height: 70, background: '#cdb88c', borderRadius: '10px 10px 0 0',
          fontFamily: mono, fontWeight: 700, fontSize: 26, color: '#3b2f1c', padding: '14px 22px', letterSpacing: '0.06em', whiteSpace: 'nowrap', overflow: 'hidden' }}>{it.tab}</div>
      ) : null}
      <div style={{ position: 'absolute', inset: 0, background: bg, backgroundPositionY: lined ? top0 - 6 : 0, clipPath: folder ? 'none' : torn(String(it.box), false) }}>
        {lined ? <div style={{ position: 'absolute', left: 92, top: 0, bottom: 0, width: 3, background: 'rgba(200,60,60,.45)' }} /> : null}
        {folder && it.corner ? <div style={{ position: 'absolute', right: 30, top: 22, fontFamily: mono, fontSize: 24, color: '#5a4a30', letterSpacing: '0.08em' }}>{it.corner}</div> : null}
        {it.head ? (
          <>
            <div style={{ position: 'absolute', left: 54, right: 40, top: 44, fontFamily: mono, fontWeight: 700, fontSize: 46, color: '#2a2724',
              letterSpacing: '0.03em', whiteSpace: 'nowrap' }}>{typed(it.head, t, it.s, 40)}</div>
            <div style={{ position: 'absolute', left: 50, right: 50, top: 126, height: 3, background: 'rgba(40,36,32,.55)' }} />
          </>
        ) : null}
        {it.rows.map((r, i) => (t < r.s ? null : (
          <div key={i} style={{ position: 'absolute', left: lined ? 112 : 54, right: 50, top: top0 + i * rh, height: rh, display: 'flex', alignItems: 'center',
            justifyContent: 'space-between', whiteSpace: 'nowrap' }}>
            {lined
              ? <span style={{ fontFamily: hand, fontSize: 54, color: r.color === 'red' ? RED : '#26408f' }}>{'✓ ' + typed(r.l, t, r.s, 45)}</span>
              : <span style={{ fontFamily: serif, fontWeight: 700, fontSize: r.l.length <= 2 ? 80 : 58, color: r.color === 'red' ? RED : INK }}>{typed(r.l, t, r.s)}</span>}
            {r.r ? <span style={{ fontFamily: mono, fontSize: 48, color: r.color === 'red' ? RED : '#6b655c' }}>{typed(r.r, t, r.s + 0.15)}</span> : null}
          </div>
        )))}
      </div>
      {it.note && t >= it.note.s ? (
        <div style={{ position: 'absolute', left: '50%', bottom: 60, transform: `translateX(-50%) rotate(-1.5deg) scale(${1.25 - 0.25 * easeOut((t - it.note.s) / 0.14)})`,
          opacity: easeOut((t - it.note.s) / 0.14), fontFamily: hand, fontSize: 46, color: INK, background: '#f6f3ec', padding: '6px 22px',
          clipPath: torn(it.note.text), whiteSpace: 'nowrap', filter: 'drop-shadow(0 3px 4px rgba(0,0,0,.3))' }}>{it.note.text}</div>
      ) : null}
      {it.stamp && t >= it.stamp.s ? (
        <div style={{ position: 'absolute', left: '50%', top: '64%', opacity: 0.88 * clamp01((t - it.stamp.s) / 0.06),
          transform: `translate(-50%, -50%) rotate(-9deg) scale(${1.7 - 0.7 * easeOut((t - it.stamp.s) / 0.16)})`, fontFamily: mono, fontWeight: 700,
          fontSize: 52, lineHeight: 1.1, color: RED, border: `6px double ${RED}`, padding: '10px 24px', textAlign: 'center', whiteSpace: 'pre-line',
          letterSpacing: '0.04em', mixBlendMode: 'multiply' }}>{it.stamp.text}</div>
      ) : null}
    </div>
  );
};

const Stat: React.FC<{ it: StatI; t: number; F: Faces }> = ({ it, t, F }) => (
  <div style={{ position: 'absolute', left: it.x, top: it.y }}>
    {it.rows.map((r, i) => {
      if (t < r.s) return null;
      const k = easeOut((t - r.s) / 0.25);
      return (
        <div key={i} style={{ position: 'absolute', left: i % 2 ? 150 : 0, top: i * STAT_ROW, width: 900, display: 'flex', alignItems: 'center', gap: 24,
          opacity: k, transform: `translateX(${(1 - k) * -30}px)`, whiteSpace: 'nowrap' }}>
          <span style={{ flexShrink: 0, fontFamily: fam(F.mono, 'monospace'), fontWeight: 700, fontSize: 140, lineHeight: 1,
            color: r.color === 'yellow' ? '#f2c933' : r.color === 'red' ? '#e0392c' : '#efeae1', textShadow: '0 4px 14px rgba(0,0,0,.7)' }}>{r.n}</span>
          <span style={{ fontFamily: fam(F.serif, 'serif'), fontWeight: 700, fontSize: 36, lineHeight: 1.15, color: '#bdb6a9', maxWidth: 480, whiteSpace: 'pre-line' }}>{r.text}</span>
        </div>
      );
    })}
  </div>
);

const Str: React.FC<{ it: StringI; t: number }> = ({ it, t }) => {
  const k = easeOut((t - it.s) / 0.4);
  const [ax, ay] = it.a, [bx, by] = it.b;
  const mx = (ax + bx) / 2, my = (ay + by) / 2 + Math.hypot(bx - ax, by - ay) * 0.08;
  return (
    <svg width={1080} height={1920} style={{ position: 'absolute', left: 0, top: 0 }}>
      <path d={`M${ax},${ay} Q${mx},${my} ${bx},${by}`} pathLength={1} style={{ fill: 'none', stroke: '#c5261d', strokeWidth: 4.5,
        strokeDasharray: 1, strokeDashoffset: 1 - k, filter: 'drop-shadow(0 3px 3px rgba(0,0,0,.5))' }} />
      {[it.a, k >= 1 ? it.b : null].map((p, i) => (p ? (
        <g key={i}><circle cx={p[0]} cy={p[1]} r={11} fill="#a81c15" /><circle cx={p[0] - 3} cy={p[1] - 3} r={4} fill="#f07a70" /></g>
      ) : null))}
    </svg>
  );
};

const HeadV: React.FC<{ h: Head; t: number; F: Faces }> = ({ h, t, F }) => {
  const at = (m: 'top' | 'mid') => (m === 'mid' ? { ...HEAD_MID, sc: 1.3 } : { ...HEAD_TOP, sc: 1 });
  const to = at(h.mode), from = h.from && h.from !== h.mode ? at(h.from) : to;
  const k = from === to ? 1 : ease((t - h.s) / 0.5);
  const fade = h.from ? 1 : easeOut((t - h.s) / 0.35);
  const ky = from.kicker + (to.kicker - from.kicker) * k, ty = from.title + (to.title - from.title) * k, sc = from.sc + (to.sc - from.sc) * k;
  return (
    <>
      {h.kicker ? (
        <div style={{ position: 'absolute', left: '50%', top: ky, transform: `translate(-50%, -50%) scale(${sc})`, opacity: fade,
          fontFamily: fam(F.mono, 'monospace'), fontWeight: 700, fontSize: 36, letterSpacing: '0.1em', color: '#f3efe6', background: '#121110',
          padding: '4px 16px', whiteSpace: 'nowrap' }}>{h.kicker}</div>
      ) : null}
      {h.title ? (
        <div style={{ position: 'absolute', left: '50%', top: ty, transform: `translate(-50%, -50%) rotate(-1.2deg) scale(${sc})`, opacity: fade,
          filter: 'drop-shadow(0 6px 10px rgba(0,0,0,.55))' }}>
          <div style={{ fontFamily: fam(F.serif, 'serif'), fontStyle: 'italic', fontWeight: 700, fontSize: 56, lineHeight: 1.15, color: '#151413',
            background: '#f2efe8', padding: '6px 26px 10px', whiteSpace: 'nowrap', clipPath: torn(h.title, false) }}>{h.title}</div>
        </div>
      ) : null}
    </>
  );
};

// dust drifting over the board and a stray hair, as the sample's film grain
const Dust: React.FC<{ t: number; scene: number }> = ({ t, scene }) => {
  const r = rng(12345);
  const specks = Array.from({ length: 34 }, () => ({ x: r() * 1080, y: r() * 1920, s: 1.6 + r() * 3.4, v: 6 + r() * 18, p: r() * 6.28, o: 0.18 + r() * 0.45 }));
  const h = rng(hash('hair' + scene));
  const hx = 120 + h() * 840, hy = 200 + h() * 1300;
  return (
    <svg width={1080} height={1920} style={{ position: 'absolute', left: 0, top: 0 }}>
      {specks.map((d, i) => (
        <circle key={i} cx={(d.x + Math.sin(t * 0.3 + d.p) * 20) % 1080} cy={(d.y - t * d.v + 1920 * 4) % 1920} r={d.s} fill="#e8e2d6" opacity={d.o * (0.75 + 0.25 * Math.sin(t * 2 + d.p))} />
      ))}
      <path d={`M${hx},${hy} c 40,-12 70,10 96,-4 s 50,-30 90,-14 s 30,26 64,18`} fill="none" stroke="#d9d2c4" strokeWidth={1.6} opacity={0.2} />
    </svg>
  );
};

export const CrimeV: React.FC<PlanC> = (plan) => {
  const F = plan.faces;
  const allText = plan.scenes.map((s) => (s.head ? s.head.kicker + s.head.title : '') + s.credit + s.items.map((i) =>
    'text' in i ? i.text : i.type === 'card' ? i.head + i.tab + i.corner + i.rows.map((r) => r.l + r.r).join('') + (i.note?.text || '') + (i.stamp?.text || '')
      : i.type === 'stat' ? i.rows.map((r) => r.n + r.text).join('') : '').join('')).join('') + plan.subs.map((c) => c.text).join('') + plan.aiTag;
  useFonts(plan.fonts, F, allText);
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  if (!plan.scenes.length) return <AbsoluteFill style={{ backgroundColor: '#1c1a18' }} />;
  const sc = plan.scenes.find((s) => t >= s.s && t < s.e) || plan.scenes[plan.scenes.length - 1];
  const sub = plan.subs.find((c) => t >= c.s && t < c.e);
  const speaking = (tt: number) => plan.subs.some((c) => tt >= c.s - 0.2 && tt < c.e + 0.2);
  const flicker = 1 + 0.025 * Math.sin(t * 11.3) * Math.sin(t * 3.1 + 0.7);
  const shown = sc.items.filter((i) => t >= i.s && (i.e === undefined || t < i.e));
  return (
    <AbsoluteFill style={{ background: '#1f1c19', overflow: 'hidden' }}>
      {plan.bg ? <Img src={staticFile(plan.bg)} style={{ position: 'absolute', inset: 0, width: 1080, height: 1920, filter: `brightness(${flicker.toFixed(4)})` }} /> : null}
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 75% 55% at 50% 45%, rgba(255,240,215,.07) 0%, rgba(0,0,0,0) 55%, rgba(0,0,0,.6) 100%)' }} />
      {shown.map((it, i) => {
        switch (it.type) {
          case 'photo': return <Photo key={i} it={it} t={t} sc={sc} tag={plan.aiTag} F={F} />;
          case 'sticker': return <Sticker key={i} it={it} t={t} tag={plan.aiTag} F={F} />;
          case 'tape': return <Tape key={i} it={it} t={t} F={F} />;
          case 'card': return <Card key={i} it={it} t={t} sc={sc} F={F} />;
          case 'stat': return <Stat key={i} it={it} t={t} F={F} />;
          case 'string': return <Str key={i} it={it} t={t} />;
          default: return null;
        }
      })}
      {sc.head ? <HeadV h={sc.head} t={t} F={F} /> : null}
      <Dust t={t} scene={sc.scene} />
      {sub ? (
        <div style={{ position: 'absolute', left: 540 - SUB_W / 2, width: SUB_W, top: SUB_Y, transform: 'translateY(-50%)', textAlign: 'center' }}>
          <span style={{ fontFamily: fam(F.sub, 'sans-serif'), fontWeight: 600, fontSize: SUB_PX, lineHeight: 1.32, color: '#111', background: '#f4f1ea',
            padding: '5px 16px', borderRadius: 4, boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone', boxShadow: '0 4px 14px rgba(0,0,0,.45)' }}>{sub.text}</span>
        </div>
      ) : null}
      {sc.credit ? (
        <div style={{ position: 'absolute', left: 30, right: 30, top: CREDIT_Y, textAlign: 'center', fontFamily: fam(F.sub, 'sans-serif'), fontWeight: 400,
          fontSize: 22, color: 'rgba(225,218,205,.55)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sc.credit}</div>
      ) : null}
      {plan.voice.map((v, i) => <Sequence key={i} from={Math.round(v.s * fps)}><Audio src={staticFile(v.src)} /></Sequence>)}
      {plan.music ? (
        <Audio src={staticFile(plan.music)} volume={(f) => {
          const tt = f / fps;
          return plan.musicVolume * Math.max(0, Math.min(1, tt / 0.6, (durationInFrames / fps - tt) / 1.4)) * (speaking(tt) ? 0.7 : 1);
        }} />
      ) : null}
    </AbsoluteFill>
  );
};
