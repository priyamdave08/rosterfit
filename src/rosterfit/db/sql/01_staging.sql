-- ============================================================================
-- STAGING: clean, typed, de-duplicated views over the raw parquet extracts.
-- Raw tables (raw_*) are registered by warehouse.py from data/processed/*.parquet
-- ============================================================================

-- Normalised name key used for every cross-source join (ESPN <-> B-Ref <-> Torvik).
CREATE OR REPLACE MACRO name_key(n) AS
    trim(regexp_replace(
        regexp_replace(lower(strip_accents(n)), '\b(jr|sr|ii|iii|iv|v)\b\.?', '', 'g'),
        '[^a-z ]', '', 'g'));

-- Basketball-Reference position string -> numeric 1 (PG) .. 5 (C).
CREATE OR REPLACE MACRO pos_num(p) AS
    CASE split_part(p, '-', 1)
        WHEN 'PG' THEN 1 WHEN 'SG' THEN 2 WHEN 'G' THEN 1.5 WHEN 'SF' THEN 3
        WHEN 'GF' THEN 2.5 WHEN 'F' THEN 3.5 WHEN 'PF' THEN 4 WHEN 'FC' THEN 4.5
        WHEN 'C' THEN 5 ELSE 3 END;

-- One row per player x team stint x season. Multi-team "2TM/3TM/TOT" rows are
-- flagged so marts can choose season totals or per-team stints.
CREATE OR REPLACE VIEW stg_player_stint AS
WITH adv AS (
    SELECT * EXCLUDE (ranker, awards, name_display_href) FROM raw_advanced
), pp AS (
    SELECT season, player_id, team_id, fga_per_poss, fg3a_per_poss, fg3_pct, fg2_pct, efg_pct,
           fta_per_poss, ft_pct, pts_per_poss, ast_per_poss, tov_per_poss, off_rtg, def_rtg
    FROM raw_per_poss
), sh AS (
    SELECT season, player_id, team_id, avg_dist, pct_fga_00_03, pct_fga_03_10, pct_fga_10_16,
           pct_fga_16_xx, pct_fga_fg3a, fg_pct_00_03, fg_pct_03_10, fg_pct_10_16, fg_pct_16_xx,
           fg_pct_fg3a, pct_ast_fg2, pct_ast_fg3, pct_fga_dunk, pct_fg3a_corner3, fg_pct_corner3
    FROM raw_shooting
)
SELECT
    adv.*,
    pos_num(adv.pos)                                   AS pos_num,
    name_key(adv.player)                               AS name_key,
    regexp_matches(adv.team_id, '^(TOT|\dTM)$')        AS is_total_row,
    pp.* EXCLUDE (season, player_id, team_id),
    sh.* EXCLUDE (season, player_id, team_id),
    -- Possession-based volume estimates (league pace ~99 poss / 48 min).
    adv.mp * 99.0 / 48.0                               AS est_poss,
    pp.fg3a_per_poss * adv.mp * 99.0 / 48.0 / 100.0    AS est_fg3a,
    pp.fta_per_poss  * adv.mp * 99.0 / 48.0 / 100.0    AS est_fta
FROM adv
LEFT JOIN pp USING (season, player_id, team_id)
LEFT JOIN sh USING (season, player_id, team_id)
WHERE adv.player_id IS NOT NULL;

CREATE OR REPLACE VIEW stg_team_season AS
SELECT
    season, team_abbr, team_name, wins, losses, off_rtg, def_rtg, net_rtg,
    off_rtg - avg(off_rtg) OVER (PARTITION BY season) AS off_rtg_rel,
    def_rtg - avg(def_rtg) OVER (PARTITION BY season) AS def_rtg_rel,
    avg(off_rtg) OVER (PARTITION BY season)           AS lg_off_rtg
FROM raw_team_ratings;

CREATE OR REPLACE VIEW stg_draft AS
SELECT draft_year, pick_overall AS pick, team_id AS draft_team, player, player_id,
       college_name, name_key(player) AS name_key
FROM raw_drafts;

CREATE OR REPLACE VIEW stg_college AS
SELECT *, name_key(player) AS name_key,
       date_diff('day', birth_date, make_date(season, 6, 25)) / 365.25 AS age_at_draft_day
FROM raw_college
WHERE gp >= 1 AND torvik_id IS NOT NULL;
