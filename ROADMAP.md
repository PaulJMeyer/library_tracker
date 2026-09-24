# Data Science & Bioinformatics – Learning Roadmap

**Last updated:** September 2026  
**Goal:** Every important skill should be demonstrated through a visible project artifact rather than only listed as theoretical knowledge.

---

## Active Projects

| Project | Description | Current State |
|---|---|---|
| `data-science` | Binary classification portfolio and future datasets | Active — multi-model workflow and ensemble complete |
| `lab-software` | CLI sample management and DNA analysis | Active — layered architecture, FASTA import, tests and CI |
| `bioinformatic-python-tools` | DNA/sequence analysis tools | Active |
| `library-tracker` | Authenticated library scraper with SQLite history | Active — SQLite persistence, history queries and CLI implemented |

---

## Priority Levels

- **P1** — immediate / current development
- **P2** — next major portfolio expansion
- **P3** — long-term specialization

---

## Skill → Project Mapping

### `data-science`

| Skill | Priority | Milestone |
|---|---|---|
| XGBoost | Done | `v1.1` |
| MLP | Done | `v1.1` |
| SVM | Done | `v1.1` |
| Voting Classifier | Done | `v1.1` |
| Threshold tuning | Done | `v1.1` |
| ROC AUC / PR AUC / MCC | Done | `v1.1` |
| MLflow | P2 | experiment tracking |
| SHAP / LIME | P2 | model interpretability |
| Optuna / Bayesian Optimization | P2 | hyperparameter tuning |
| Statistical testing / bootstrapping / power analysis | P2 | statistical analysis project |
| Survival Analysis | P2 | clinical dataset |
| DVC | P3 | data versioning |
| FastAPI | P3 | model serving |
| Docker | P3 | reproducible deployment |
| Streamlit | P3 | interactive demo |
| Cloud deployment | P3 | hosted application |

### `lab-software`

| Skill | Priority | Milestone |
|---|---|---|
| pytest | Done | broad automated test suite |
| type hints | Done | typed application code |
| Pydantic | Done | domain validation |
| GitHub Actions | Done | automated tests/coverage |
| layered architecture | Done | domain / analysis / services / I/O / CLI |
| FASTA import | Done | single- and multi-FASTA |
| Git branches + pull requests | P1 | use consistently for future changes |
| SQLite | P2 | replace JSON persistence if still useful |
| CSV / Excel export | P2 | data export |
| FastAPI | P3 | REST API |
| Docker | P3 | packaging/deployment |

### `bioinformatic-python-tools`

| Skill | Priority | Milestone |
|---|---|---|
| pytest | P2 | automated tests |
| type hints / mypy | P2 | static typing |
| ruff | P2 | linting |
| GitHub Actions | P2 | CI |
| Quarto | P2 | reproducible analysis report |
| Biopython | P2 | FASTA/GenBank extension |
| NetworkX | P3 | biological network analysis |

### `library-tracker`

| Skill / Feature | Status | Milestone |
|---|---|---|
| Multiple-copy detection | Done | `v0.3` |
| Central vs. branch detection | Done | `v0.3` |
| Type hints + mypy | Done | `v0.4` |
| pytest + coverage | Done | `v0.4` |
| HTTP/login mocking | Done | `v0.4` |
| GitHub Actions CI | Done | `v0.4` |
| Scheduled scrape | Done | `v0.4` |
| Branch + PR workflow | Done / ongoing | development workflow |
| SQLite schema | Done | `v0.5` |
| Copy upsert persistence | Done | `v0.5` |
| Availability snapshots | Done | `v0.5` |
| History query | Done | `v0.5` |
| History CLI | Done | `v0.5` |
| Database / repository separation | Done / current refactor | `v0.5` |
| Persist SQLite history across GitHub Actions runs | P1 | `v0.5` |
| Store snapshots only on relevant changes | P1 | `v0.5` |
| Database statistics / status command | P1 | `v0.5` |
| Improve history display | P2 | `v0.6` |
| Streamlit history dashboard | P3 | `v1.0` |

---

## Current Sprint

### Library Tracker — finish SQLite milestone

- [x] Expand tests across application layers
- [x] Type-check production and test code with `mypy`
- [x] Introduce branch + pull-request workflow
- [x] Add SQLite schema
- [x] Store physical copies by `media_number`
- [x] Store timestamped availability snapshots
- [x] Add history queries
- [x] Add CLI access to copy history
- [x] Separate SQLite infrastructure from repository operations
- [ ] Persist SQLite database between scheduled GitHub Actions runs
- [ ] Avoid duplicate snapshots when availability has not changed
- [ ] Add database statistics / status query
- [ ] Update README and technical documentation after final `v0.5` state

Target outcome:

```text
Web scraping
→ HTML parsing
→ typed models
→ tested business logic
→ SQLite persistence
→ historical data
→ SQL queries
→ CLI access
→ scheduled automation
```

At that point the Library Tracker should be considered a complete portfolio project rather than continuously expanded with small features.

---

## Next Portfolio Priority

After the Library Tracker SQLite milestone, development should shift toward a second substantial data project instead of continuously adding libraries or minor scraper features.

Preferred direction:

### Second Data Science Project

Goals:

- larger or more realistic dataset
- clear domain question
- reproducible pipeline
- stronger statistical reasoning
- fewer models, with better justification
- clean train/test strategy
- reusable preprocessing
- meaningful visualizations
- tests for reusable data-processing code where appropriate

Preferred domain:

- life sciences
- healthcare
- biotechnology
- bioinformatics

This would complement the existing diabetes-classification project and better demonstrate independent end-to-end problem solving.

---

## P2 — Medium Term

### Data Science

- [ ] Second end-to-end Data Science project
- [ ] Statistical analysis project
- [ ] SHAP / model interpretability
- [ ] MLflow experiment tracking
- [ ] Survival analysis
- [ ] Optuna or another modern tuning workflow

### Bioinformatics

- [ ] Improve `bioinformatic-python-tools` engineering quality
- [ ] Biopython integration
- [ ] Reproducible report with Quarto
- [ ] Differential-expression project using a public GEO dataset
- [ ] R / Bioconductor / DESeq2 / edgeR

### Software Engineering

- [ ] Add `ruff` consistently across active Python projects
- [ ] Continue feature-branch + pull-request workflow
- [ ] Dockerize one mature project
- [ ] Add FastAPI to a project where an API solves a real problem

---

## P3 — Long Term

- [ ] Streamlit dashboard for Library Tracker availability history
- [ ] Cloud deployment
- [ ] RNA-seq pipeline with Snakemake or Nextflow
- [ ] Single-cell analysis with ScanPy / AnnData
- [ ] Multi-omics demo
- [ ] Biomedical NLP / embeddings / RAG
- [ ] Time-series forecasting
- [ ] Causal inference

---

## Development Workflow

For substantial changes:

```text
master
  ↓
feature / fix / refactor branch
  ↓
small logical commits
  ↓
mypy + pytest locally
  ↓
push branch
  ↓
pull request
  ↓
GitHub Actions
  ↓
merge into master
```

Example:

```bash
git switch master
git pull
git switch -c feature/example
```

After implementation:

```bash
mypy
python -m pytest --cov=library_tracker --cov-report=term-missing -v
git push -u origin feature/example
```

After the pull request is merged:

```bash
git switch master
git pull
git branch -d feature/example
```

The goal is not to create branches for every tiny edit, but to keep meaningful features, fixes, and refactors reviewable and keep `master` in a working state.
