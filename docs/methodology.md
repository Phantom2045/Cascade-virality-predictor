# Methodology

## 1. Canonical Schema & Graph Construction Rules

Every dataset adapter normalizes propagation records into the canonical edge schema:

`cascade_id, parent_id, child_id, timestamp`

where `timestamp` is elapsed seconds since the cascade root event (`timestamp >= 0`), and root nodes have `parent_id = None` (empty string in CSV).

### Explicit Cleaning Rules (`app/services/validation.py`)
1. **Malformed rows**: Rows missing `cascade_id`, `child_id`, or having non-finite/non-numeric `timestamp` are dropped and counted (`malformed_rows_dropped`).
2. **Negative timestamps**: Rows with `timestamp < 0` are dropped and counted (`negative_timestamps_dropped`).
3. **Self-loops**: Edges where `parent_id == child_id` are dropped and counted (`self_loops_dropped`).
4. **Duplicate edges**: Exact duplicate `(cascade_id, parent_id, child_id)` edges are deduplicated keeping the earliest timestamp (`duplicate_edges_dropped`).
5. **Multiple parents**: If a `child_id` has multiple parents in the same cascade, the **earliest-timestamp parent** is retained and conflicts are counted (`multiple_parents_resolved`).
6. **Cycle breaking**: Directed cycles are detected via `nx.find_cycle` and broken by removing the **latest-timestamp edge** in each cycle (`cycles_detected`, `cycle_edges_removed`).
7. **Forest handling**: Cascades with multiple roots (`in_degree == 0` nodes) are flagged (`multiple_roots_cascades`) and traversed via multi-source BFS starting from all roots at depth `0`.

## 2. Early-Window Truncation & Leakage Guard

Prediction uses only events with `timestamp <= T` (default `T = 3600` seconds, configurable via `--window`).

- `truncate_to_window(df, T)` filters `timestamp <= T` and calls `assert_no_future_events(truncated, T)` on both training and inference paths.
- Cascades with fewer than `min_early_edges = 3` directed edges (`parent_id` not null) in `[0, T]` are **excluded** from training, evaluation, and scoring, with counts reported per split (`excluded_by_split`).

## 3. Feature Formulas (18 Early-Only Features)

> **Note — one provably degenerate feature is retained on purpose.** `clustering_coefficient` is *identically `0.0`* on every cascade, because cleaning removes all directed cycles (see §1.6), so each cascade is a forest, and a forest contains no triangles. Its permutation importance is therefore `0.0` by construction — not by error. It is **retained and explicitly flagged** (in the API response and below) rather than silently dropped, because a zero clustering value is itself a correctness check that the graph is acyclic. Removing it changes no metrics; keeping it documents the invariant.

Let $G = (V, E)$ be the early-window directed graph (`parent -> child`) and $U$ be its simple undirected projection.

| Feature | Formula / Convention | Degenerate / Forest Note |
|---|---|---|
| `num_nodes` | $\|V\|$ | `0` if empty |
| `num_edges` | $\|E\|$ (directed edges) | `0` if empty |
| `max_degree` | $\max_{v \in V} \deg_U(v)$ | `0` if empty |
| `avg_degree` | $\frac{1}{\|V\|} \sum_{v \in V} \deg_U(v)$ | `0` if empty |
| `degree_variance` | $\frac{1}{\|V\|} \sum_{v \in V} (\deg_U(v) - \bar{d})^2$ | Population variance (`ddof=0`) |
| `max_depth` | $\max_{v \in V} \text{depth}(v)$ from multi-source BFS at roots | `0` for single node |
| `avg_depth` | $\frac{1}{\|V\|} \sum_{v \in V} \text{depth}(v)$ | Detached cyclic components start at depth `0` |
| `max_branching` | $\max_{v \in V} \text{out\_deg}_G(v)$ | `0` if no edges |
| `avg_branching` | Mean $\text{out\_deg}_G(v)$ over internal nodes ($\text{out\_deg} > 0$) | `0.0` if no internal nodes |
| `density` | Directed density $\frac{\|E\|}{\|V\|(\|V\| - 1)}$ | `0.0` if $\|V\| \le 1$ |
| `clustering_coefficient` | `nx.average_clustering(U)` | Provably `0.0` on trees/forests (no triangles); retained & flagged as uninformative by design |
| `num_leaves` | $\|\{v \in V : \text{out\_deg}_G(v) = 0\}\|$ | Root counts as leaf if $\|V\|=1$ |
| `leaf_ratio` | `num_leaves / num_nodes` | `0.0` if empty |
| `num_components` | Number of weakly connected components of $G$ | $>1$ for forests |
| `structural_virality` | Wiener index on largest weakly connected component $C$: $\frac{1}{\|C\|(\|C\|-1)} \sum_{u \neq v \in C} d_U(u,v)$ | `0.0` if $\|C\| \le 1$; deterministic 128-source BFS sampling when $\|C\| > 500$ |
| `event_rate` | $\frac{m}{\max(t_m - t_0, 1.0)}$ where $t_0$ is earliest timestamp and $t_m$ is last in-window edge time | `0.0` if $m=0$ |
| `time_to_third_event` | $t_3 - t_0$ (3rd sorted in-window edge minus $t_0$) | `NaN` if $m < 3$, median-imputed by pipeline |
| `median_inter_event_gap` | Median of consecutive differences $\text{diff}([t_0, t_1, \dots, t_m])$ | `0.0` if $m = 0$ |

## 4. Labeling & Splitting Procedure

- **Final size**: Distinct nodes in the full observed cascade over the dataset's observation horizon.
- **Virality threshold**: Fit **strictly on eligible training cascades**:
  $$\tau = \lceil \text{Quantile}_q(\text{train\_final\_sizes}) \rceil, \quad q = 0.80$$
  A cascade is positive (`is_viral = 1`) iff `final_size >= tau`. Ties at $\tau$ are assigned to the positive class.
- **Temporal split (primary)**: Cascades ordered chronologically by `(root_timestamp, cascade_id)` and split 70% train / 10% validation / 20% test by cascade ID.
- **Random split (comparison only)**: Stratified random 70/10/20 split by cascade ID, explicitly labelled as optimistic because it mixes future and past regimes.

## 5. Models, Tuning & Evaluation

All models are `scikit-learn` `Pipeline` objects fit strictly on the training split:
1. **Random Forest** (`SimpleImputer(median)` + `RandomForestClassifier(class_weight="balanced")`, tuned with 5-fold `StratifiedKFold` CV optimizing `average_precision` on train only).
2. **Logistic Regression** (`SimpleImputer(median)` + `StandardScaler` + `LogisticRegression(class_weight="balanced")`).
3. **Naive Baseline** (`num_edges` column only -> `SimpleImputer(median)` + `StandardScaler` + `LogisticRegression(class_weight="balanced")`).
4. **Dummy Baseline** (`DummyClassifier(strategy="prior")`).

Evaluation reports PR-AUC (headline metric due to class imbalance), Recall, Precision, F1, ROC-AUC, Brier score, 95% percentile bootstrap CIs, confusion matrix, ROC/PR/calibration curves, test-set permutation importance (`scoring="average_precision"`), and sensitivity across $q \in \{0.80, 0.90, 0.95\}$.
