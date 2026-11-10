# RosterFit

An NBA front-office tool that answers three questions with one engine:

1. **What is our best lineup?** Every realistic 5-man combination on a roster is scored by a model of offensive and defensive efficiency.
2. **Who should we draft?** Every college player gets a standalone grade (probability of becoming a starter, probability of washing out, expected value), and the tool also measures how well each prospect fits *your* roster.
3. **Does this signing or trade help?** Free agents and trade targets go through the same lineup re-optimisation as draft prospects: add players, remove players, re-score every lineup.

It runs on live 2026-27 rosters and on data back to 2010.

## Results (out of sample)

**Lineup efficiency model.** Predicts a lineup's offensive and defensive rating per 100 possessions from the five players' *previous-season* profiles. Trained on 450 team-seasons, validated leave-one-season-out.

| Target | RosterFit R² | Talent-only baseline (avg BPM) R² |
|---|---|---|
| Net rating | **0.628** (MAE 2.44) | 0.603 (MAE 2.50) |
| Offensive rating | **0.590** | 0.524 |
| Defensive rating | **0.390** | 0.271 |

The fit features (spacing, creation, rim protection, usage balance, paint congestion) matter most on defense, where box-score talent alone explains the least.

**Prospect model.** Trained on 623 drafted college players (2010 to 2022 drafts), validated leave-one-draft-class-out. College stats only; draft position is never an input.

| Metric | College stats | Draft slot alone |
|---|---|---|
| Rank correlation with 4-year NBA value (Spearman) | **0.365** | 0.230 |
| P(hit) AUC, first-round picks only | **0.666** | 0.628 |
| P(hit) AUC, all picks | 0.733 | 0.777 |
| P(bust) AUC, all picks | 0.720 | 0.802 |

How to read this: college stats rank first-round outcomes better than the order players were actually drafted in, and predict four-year value better than draft slot. Draft slot is still better at predicting who washes out of the league. Part of that is information the box score can't see (medicals, interviews, film), and part is mechanical: second-round contracts are non-guaranteed, so those players get cut first.

**College to NBA translation.** Out-of-sample correlation between projected and actual early-career NBA stats: position 0.91, rebounding 0.83 to 0.88, block rate 0.86, rim frequency 0.82, 3PA rate 0.79, assist rate 0.77, BPM 0.48.

## How it works

```
Basketball-Reference ─┐                       ┌─ lineup model (Ridge + gradient boosting)
Bart Torvik (college) ├─ ingest ─ DuckDB SQL ─┼─ prospect models (mixture model + classifiers)
ESPN live rosters ────┘   (cached)   marts    ├─ college → NBA translation
                                              └─ player archetypes (Gaussian mixture)
                                                         │
                       FastAPI  ◄── fit engine ──►  Streamlit dashboard
                                         │
                   AWS: S3 data lake · Athena · Bedrock (Claude) · nightly Fargate refresh
```

### Data
* **Basketball-Reference**: advanced, per-100-possession and shooting-zone tables for every player since 2010-11, team ratings, and every draft class with career outcomes. Pages are cached and requests are spaced to respect the site's rate limit.
* **Bart Torvik**: every Division I player-season since 2010 (BPM, usage, shooting by zone, recruiting rank, birth date, draft pick).
* **ESPN**: current rosters for all 30 teams, refreshed on each run.

Everything lands in DuckDB. SQL in [`src/rosterfit/db/sql`](src/rosterfit/db/sql) builds staging views and analysis marts, including the join that links each draftee to his final college season (by draft year and pick, with a Jaro-Winkler name check; average name similarity 0.997).

### Player profiles
Each NBA player is a 23-stat vector (BPM splits, TS%, usage, assist/turnover/rebound/steal/block rates, 3PA volume and accuracy, rim and mid-range frequency, corner-3 share, ratings, position). Rates are shrunk toward positional means by minutes played, and 3P% is shrunk with an empirical-Bayes beta-binomial prior fit by maximum likelihood (scipy). A rookie who starts 6-for-9 from three does not get graded as a 66% shooter.

### Lineup model
A lineup's features: average talent; counts of shooters, creators, rim protectors, bigs, stars and weak links; a spacing index; usage total, spread and concentration; usage-weighted TS%; size; and interaction terms (creation × spacing, rim protection × ball pressure, paint congestion).

Public 5-man lineup data is paywalled, so the model trains on team-seasons. The catch: a non-linear feature computed on a team's 15-man average is not on the same scale as the same feature on 5 players. RosterFit handles this by **Monte Carlo sampling 150 realistic 5-man lineups per team-season** (players drawn in proportion to minutes) and averaging their features. The model sees lineup-scale inputs in training and in use, so nothing is extrapolated. A test enforces this.

### Prospect model
* **Outcomes as latent trajectories.** Instead of choosing a "bust" cutoff, a group-based finite mixture model is fit to each draftee's four-season path of VORP and minutes. BIC picks six groups, named from their mean paths: *Washout* (never stuck), *Flameout* (got chances, out by year 4), *Empty Minutes* (big minutes, negative value), *Slow Build*, *Starter*, *Star*. Bust = groups out of the league by year 4; hit = groups averaging at least 1.5 VORP.
* **Hierarchical priors for small samples.** Every college rate stat is shrunk toward the historical mean for players of the same recruiting tier and class year, weighted by minutes. An elite freshman two games into the season looks like a typical elite freshman until he plays more.
* **Models.** Regularised logistic regression blended with gradient boosting for P(bust), P(hit) and P(each trajectory); a ridge/boosting blend for expected 4-year VORP. Grades are percentiles of out-of-fold expected value among every draftee since 2010.
* **Explanations.** SHAP attributions for every prospect, nearest-neighbour historical comps, and a separate draftability model trained on every final college season.

### Fit engine
Drafts, signings and trades are the same operation. For a move the engine reports:
* change in the best lineup's net rating and in top-10 lineup depth;
* the best lineup that includes the new player, and who he displaces;
* **synergy**: how much more he helps this team than he would help the median NBA team (fit, separated from talent);
* a 0-100 fit score, and for prospects a board score blending standalone grade with team fit (weight adjustable in the UI).

### Visuals
* **Shot charts** on a regulation half-court: colour is FG% relative to league average in each zone, bubble size is shot volume. NBA players use Basketball-Reference distance zones (with left/right corner threes); prospects use Torvik's rim / two-point jumper / three zones with Bayes-shrunk percentages. Exact shot locations from stats.nba.com are supported as an optional extra.
* **Spacing maps**: each lineup's five players are placed on the floor with the Hungarian algorithm (scipy `linear_sum_assignment`) matching skills to spots. Each player gets a "gravity" radius based on how far a defense must stretch to respect him, and the map flags congested paint.
* Lineup drivers, shot-diet bars, career-path probabilities, league-percentile radar charts.

### AI scouting memos
One click turns the model outputs (grade, probabilities, SHAP drivers, comps, team fit) into a written memo from Claude, via **Amazon Bedrock** or the Claude API. Claude is instructed to use only the numbers in the packet, so every claim in the memo traces back to a model output. With no provider configured, a deterministic template memo is produced instead.

## AWS

| Service | Role |
|---|---|
| S3 | Data lake: marts as Hive-partitioned Parquet, model artifacts, Athena results |
| Glue Data Catalog + Athena | Serverless SQL over the lake. `rosterfit athena-ddl` emits the table DDL with partition projection (no crawlers); the workgroup caps each query at 1 GB scanned |
| Bedrock | Claude (`anthropic.claude-opus-5-5`) writes scouting memos |
| ECS Fargate + EventBridge | Nightly refresh: re-pull rosters and stats, rebuild marts, retrain, publish to S3 |
| ECS Fargate + ALB (optional) | Hosts the dashboard |
| CDK (Python) | All of the above as code in [`infra/`](infra) |

The VPC uses public subnets and no NAT gateway, so idle cost stays near zero. Nothing deploys automatically; see [Deploying](#deploying-to-aws).

## Running it

```bash
make install        # Python 3.12 venv via uv
make all            # ingest (~7 min first time, cached after) -> SQL marts -> train
make app            # http://localhost:8501
```

Other entry points:

```bash
make api                                   # REST API, docs at http://localhost:8000/docs
.venv/bin/rosterfit lineups SAS            # best Spurs lineups in the terminal
.venv/bin/rosterfit board SAS              # draft board with team fit
.venv/bin/rosterfit scout "Flory Bidunga" --team SAS
make mlflow                                # experiment history
make test
```

To use Claude for memos, set `ANTHROPIC_API_KEY` (Claude API) or `ROSTERFIT_LLM_PROVIDER=bedrock` with AWS credentials and `AWS_REGION`.

### Deploying to AWS

```bash
cd infra && pip install -r requirements.txt
npx aws-cdk@2 bootstrap                    # once per account/region
npx aws-cdk@2 deploy                       # data lake + nightly refresh
npx aws-cdk@2 deploy -c deploy_app=true    # plus the hosted dashboard
```

Then `rosterfit athena-ddl --bucket <BucketName output>` and run the statements in the `rosterfit` Athena workgroup. Bedrock model access for Claude must be enabled in the account.

## Project layout

```
src/rosterfit/
  ingest/     Basketball-Reference, Torvik, ESPN, optional stats.nba.com shots
  db/         DuckDB warehouse + SQL staging and marts
  features/   shrinkage, player profiles, lineup features, archetypes, college features
  models/     lineup model, prospect models, MLflow registry
  engine/     context assembly, lineup optimiser, roster-move fit
  viz/        half-court, shot charts, spacing maps
  cloud/      S3/Athena lake, Bedrock scouting memos
  api/        FastAPI
  app/        Streamlit
infra/        AWS CDK stack
tests/        unit, mocked-AWS and end-to-end tests
```

## Limitations

* Lineup training data is team-season level because public 5-man lineup data is behind a paywall. Absolute lineup ratings run hotter than real five-man samples; rankings and differences are the reliable output.
* The prospect model only sees players who were drafted, so it is calibrated for draft-calibre players. The draftability score is shown alongside it for that reason.
* A college player's NBA projection is his expected early-career (years 1 to 3) profile, so rookies usually grade below established starters in lineup fit. Compare prospects with each other, not with veterans.
* International and G League prospects need college stats to be graded.

## Design influences

The method borrows from published work in front-office analytics, in particular Joshua Fink's (San Antonio Spurs data science): group-based finite mixture models for latent trajectories, Bayesian approaches to noisy measurement, shot charts that encode volume and efficiency separately, and a SQL-first data layer.
