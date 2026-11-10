-- ============================================================================
-- MARTS: analysis-ready tables consumed by the models and the app.
-- ============================================================================

-- Season totals: one row per player-season (uses the TOT/2TM row for traded players).
CREATE OR REPLACE TABLE mart_player_season AS
SELECT * EXCLUDE (rn)
FROM (
    SELECT *, row_number() OVER (PARTITION BY season, player_id
                                 ORDER BY is_total_row DESC, mp DESC) AS rn
    FROM stg_player_stint
)
WHERE rn = 1;

-- Per-team stints, for minutes-weighted team aggregation.
CREATE OR REPLACE TABLE mart_player_team_season AS
SELECT * FROM stg_player_stint WHERE NOT is_total_row;

CREATE OR REPLACE TABLE mart_team_season AS SELECT * FROM stg_team_season;

-- First four NBA seasons for every drafted player (missing season = 0 minutes, 0 VORP:
-- being out of the league IS the outcome for a bust).
CREATE OR REPLACE TABLE mart_draft_outcomes AS
WITH yrs AS (
    SELECT d.*, y.yr, d.draft_year + y.yr AS season
    FROM stg_draft d CROSS JOIN (SELECT unnest(range(1, 5)) AS yr) y
)
SELECT yrs.draft_year, yrs.pick, yrs.draft_team, yrs.player, yrs.player_id, yrs.college_name,
       yrs.name_key, yrs.yr, yrs.season,
       coalesce(ps.mp, 0)   AS mp,
       coalesce(ps.vorp, 0) AS vorp,
       ps.bpm, ps.ws_per_48
FROM yrs
LEFT JOIN mart_player_season ps ON ps.player_id = yrs.player_id AND ps.season = yrs.season;

-- Link each draftee to his final college season. Torvik carries the draft pick
-- number on every season row, so (draft_year, pick) is the primary key and the
-- Jaro-Winkler name score is a guard against bad matches.
CREATE OR REPLACE TABLE mart_draft_college AS
WITH cand AS (
    SELECT d.draft_year, d.pick, d.player_id, d.player AS nba_name,
           c.* EXCLUDE (pick), c.pick AS torvik_pick,
           jaro_winkler_similarity(d.name_key, c.name_key) AS name_sim
    FROM stg_draft d
    JOIN stg_college c
      ON c.season = d.draft_year
     AND (c.pick = d.pick OR jaro_winkler_similarity(d.name_key, c.name_key) >= 0.93)
)
SELECT * EXCLUDE (rk) FROM (
    SELECT *, row_number() OVER (PARTITION BY draft_year, pick
                                 ORDER BY coalesce(torvik_pick = pick, false) DESC,
                                          name_sim DESC, min_pct DESC) AS rk
    FROM cand WHERE name_sim >= 0.80
) WHERE rk = 1;

-- Count of prior college seasons (experience) for each Torvik player-season.
CREATE OR REPLACE TABLE mart_college_career AS
SELECT torvik_id, season,
       count(*) OVER (PARTITION BY torvik_id ORDER BY season) AS college_seasons,
       lag(bpm) OVER (PARTITION BY torvik_id ORDER BY season)  AS prev_bpm
FROM stg_college;

-- Current draft-eligible prospect pool: most recent college season per player.
CREATE OR REPLACE VIEW mart_prospect_pool AS
SELECT * EXCLUDE (rk) FROM (
    SELECT c.*, cc.college_seasons, cc.prev_bpm,
           row_number() OVER (PARTITION BY c.torvik_id ORDER BY c.season DESC) AS rk
    FROM stg_college c JOIN mart_college_career cc USING (torvik_id, season)
    WHERE c.season >= (SELECT max(season) - 1 FROM stg_college)
      AND c.pick IS NULL
) WHERE rk = 1;
