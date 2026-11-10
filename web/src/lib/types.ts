// Response shapes of the RosterFit /ui API (src/rosterfit/api/ui.py). Values are engine
// outputs, already JSON-cleaned server side; the front end only formats them.

export interface Team {
  abbr: string;
  name: string;
  color: string;
  alt_color: string;
}

export interface Meta {
  season: string;
  warehouse_built: string | null;
  teams: Team[];
  labels: { stats: Record<string, string>; college: Record<string, string>; profile: Record<string, string> };
  shooter_help: string;
  memo_writer: "bedrock" | "anthropic" | "none" | string;
  spots: Record<string, [number, number, string]>;
  nba_label_pos: Record<string, [number, number]>;
  college_label_pos: Record<string, [number, number]>;
}

export interface Person {
  id: string;
  name: string;
  short: string;
  jersey: string | null;
  team: string;
  label: string;
  kind: "nba" | "prospect";
}

export interface LineupRow {
  rank: number;
  ids: string[];
  players: Person[];
  net: number;
  off: number;
  def: number;
  shooters: number;
  spacing: number;
  usage_total: number;
}

export interface LineupList {
  count: number;
  lineups: LineupRow[];
}

export interface LineupMetrics {
  net: number;
  off: number;
  def: number;
  shooters: number;
  creators: number;
  rim_protectors: number;
  spacing: number;
  usage_total: number;
}

export interface SpotPlayer {
  player: string;
  id: string | null;
  spot: string;
  x: number;
  y: number;
  kind: "corner" | "wing" | "top" | "dunker" | "elbow";
  radius: number;
}

export interface Driver {
  feature: string;
  label: string;
  value: number;
  net_impact?: number;
  impact_vorp?: number;
}

export interface LineupDetail {
  players: Person[];
  metrics: LineupMetrics;
  realistic: boolean;
  highlight: string | null;
  spacing: { players: SpotPlayer[]; perimeter_threats: number; paint_bodies: number; congested: boolean };
  drivers: Driver[];
  shot_diet: { zone: string; share: number }[];
}

export interface CustomLineup extends LineupDetail {
  rank: number;
  of: number;
  outside: string[];
  best: LineupMetrics;
}

export interface RosterPlayer extends Person {
  source: string;
  archetype: string | null;
  mp: number | null;
  bpm: number;
  obpm: number;
  dbpm: number;
  ts_pct: number;
  usg_pct: number;
  fg3_pct_eb: number;
  fg3a_per_poss: number;
  ast_pct: number;
  blk_pct: number;
}

export interface Prospect {
  torvik_id: number;
  player: string;
  team: string;
  class_yr: string;
  age_at_draft: number | null;
  height_in: number | null;
  bpm: number;
  grade: string;
  grade_score: number;
  expected_vorp_4yr: number;
  hit_prob: number;
  bust_prob: number;
  likeliest_path: string;
  archetype: string | null;
  total_min: number;
  draft_prob: number;
}

export interface Board {
  count: number;
  prospects: Prospect[];
}

export interface Zone {
  freq: number;
  fg: number;
  lg_fg: number;
}

export interface Comp {
  nba_name: string;
  team: string;
  draft_year: number;
  pick: number | null;
  outcome: string;
  vorp_4yr: number;
  mp_4yr: number;
  similarity: number;
}

export interface ProspectReport {
  torvik_id: number;
  profile: Prospect;
  tiers: { path: string; prob: number }[];
  drivers: Driver[];
  zones: Record<string, Zone>;
  comps: Comp[];
}

export interface Memo {
  text: string;
  provider: string;
  model: string | null;
}

export interface FitRow {
  player_id: string;
  player: string;
  grade: string;
  grade_score: number;
  fit_score: number;
  board_score: number;
  gain_vs_current_best: number;
  synergy: number;
  displaces: string;
  bust_prob: number;
  hit_prob: number;
}

export interface DraftFit {
  team: string;
  talent_weight: number;
  rows: FitRow[];
  best_with_top: LineupDetail | null;
}

export interface MovePool {
  mode: "signing" | "trade";
  count: number;
  players: Person[];
  roster: Person[];
}

export interface MoveResult {
  team: string;
  after_best: number;
  ceiling_delta: number;
  after_depth: number;
  depth_delta: number;
  players: (Person & { fit_score: number; best_with: number | null; displaces: string | null; synergy: number | null })[];
  before: LineupRow[];
  after: LineupRow[];
  best_after: LineupDetail;
}

export interface Season {
  season: number;
  team_id: string;
  age: number;
  g: number;
  mp: number;
  per: number;
  ts_pct: number;
  usg_pct: number;
  bpm: number;
  vorp: number;
  ws_per_48: number;
  off_rtg: number;
  def_rtg: number;
}

export interface PlayerCard extends Person {
  archetype: string | null;
  bpm: number;
  ts_pct: number;
  source: string;
  percentiles: { stat: string; label: string; pct: number }[];
  seasons: Season[];
  zones: Record<string, Record<string, Zone>>;
}

export interface TrajectoryGroup {
  name: string;
  n: number;
  vorp4: number;
  mean_mp_path: number[];
  mean_vorp_path: number[];
}

export interface ModelCard {
  lineup_model: Record<string, number>;
  prospect_model: Record<string, number | string[]>;
  trajectory_groups: TrajectoryGroup[];
}
