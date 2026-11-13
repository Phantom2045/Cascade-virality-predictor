import { useQuery } from "@tanstack/react-query";
import { Info, Search } from "lucide-react";
import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  api,
  type PredictCascadeResult,
  type TreeGraphResponse,
  type TreeNodePayload,
  type ValidationReport,
} from "../api/client";
import { ChartFrame } from "../components/ChartFrame";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { ProbabilityGauge } from "../components/ProbabilityGauge";
import { TreeView } from "../components/TreeView";
import { UploadZone } from "../components/UploadZone";
import { Chip } from "../components/ui/Badge";
import { Card, CardHeader, CardTitle } from "../components/ui/Card";
import { AnalyzePanelSkeleton, Skeleton } from "../components/ui/Skeleton";
import { StatTile } from "../components/ui/StatTile";
import { cn } from "../lib/cn";
import { formatDuration, formatMetric } from "../lib/format";

const TopFactorsChart = lazy(() => import("../components/charts/TopFactorsChart"));

function buildClientTreePreview(
  csvText: string,
  targetCascadeId: string,
  windowSeconds: number
): TreeGraphResponse | null {
  const lines = csvText
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length < 2) return null;

  const headers = lines[0].split(",").map((h) => h.trim());
  const cIdx = headers.indexOf("cascade_id");
  const pIdx = headers.indexOf("parent_id");
  const chIdx = headers.indexOf("child_id");
  const tIdx = headers.indexOf("timestamp");
  if (cIdx < 0 || pIdx < 0 || chIdx < 0 || tIdx < 0) return null;

  const childrenByParent = new Map<string, string[]>();
  const parentOf = new Map<string, string | null>();
  const tsOf = new Map<string, number>();
  const allNodes = new Set<string>();
  const edges: { parent_id: string; child_id: string; timestamp: number }[] = [];

  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(",").map((p) => p.trim());
    if (parts.length < 4) continue;
    if (parts[cIdx] !== targetCascadeId) continue;
    const rawParent = parts[pIdx];
    const parent =
      !rawParent || ["nan", "none", "null"].includes(rawParent.toLowerCase()) ? null : rawParent;
    const child = parts[chIdx];
    const ts = Number(parts[tIdx]);
    if (!child || !Number.isFinite(ts) || ts < 0 || ts > windowSeconds) continue;

    allNodes.add(child);
    if (!tsOf.has(child) || ts < (tsOf.get(child) ?? ts)) tsOf.set(child, ts);
    if (parent && parent !== child) {
      allNodes.add(parent);
      if (!tsOf.has(parent)) tsOf.set(parent, 0);
      if (!parentOf.has(child)) {
        parentOf.set(child, parent);
        const list = childrenByParent.get(parent) ?? [];
        list.push(child);
        childrenByParent.set(parent, list);
        edges.push({ parent_id: parent, child_id: child, timestamp: ts });
      }
    } else if (!parentOf.has(child)) {
      parentOf.set(child, null);
    }
  }

  if (allNodes.size === 0) return null;

  const roots = Array.from(allNodes).filter((n) => !parentOf.get(n));
  const depthMap = new Map<string, number>();
  const queue = [...roots];
  for (const r of roots) depthMap.set(r, 0);
  while (queue.length > 0) {
    const curr = queue.shift() as string;
    const d = depthMap.get(curr) ?? 0;
    for (const ch of childrenByParent.get(curr) ?? []) {
      if (!depthMap.has(ch)) {
        depthMap.set(ch, d + 1);
        queue.push(ch);
      }
    }
  }

  const nodes: TreeNodePayload[] = Array.from(allNodes).map((id) => {
    const out = (childrenByParent.get(id) ?? []).length;
    return {
      id,
      parent_id: parentOf.get(id) ?? null,
      timestamp: tsOf.get(id) ?? 0,
      depth: depthMap.get(id) ?? 0,
      is_root: !parentOf.get(id),
      is_leaf: out === 0,
      out_degree: out,
    };
  });

  return {
    cascade_id: targetCascadeId,
    early_window_seconds: windowSeconds,
    root_id: roots[0] ?? null,
    total_nodes: nodes.length,
    total_edges: edges.length,
    returned_nodes: nodes.length,
    truncated: false,
    truncation_notice: null,
    nodes,
    edges,
    stats: {},
  };
}

export function AnalyzePage() {
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const [uploadState, setUploadState] = useState<{
    loading: boolean;
    error: ApiError | Error | null;
    validationReport: ValidationReport | null;
    predictions: PredictCascadeResult[];
    selectedUploadCascade: string | null;
    csvText: string | null;
  }>({
    loading: false,
    error: null,
    validationReport: null,
    predictions: [],
    selectedUploadCascade: null,
    csvText: null,
  });

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "/") return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }
      e.preventDefault();
      searchInputRef.current?.focus();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const cascadesQuery = useQuery({
    queryKey: ["cascades", search],
    queryFn: () => api.getCascades({ limit: 50, offset: 0, search }),
    retry: false,
  });

  useEffect(() => {
    if (
      !selectedId &&
      !uploadState.selectedUploadCascade &&
      cascadesQuery.data &&
      cascadesQuery.data.items.length > 0
    ) {
      setSelectedId(cascadesQuery.data.items[0].cascade_id);
    }
  }, [cascadesQuery.data, selectedId, uploadState.selectedUploadCascade]);

  const treeQuery = useQuery({
    queryKey: ["cascade-tree", selectedId],
    queryFn: () => api.getCascadeTree(selectedId as string),
    enabled: Boolean(selectedId) && !uploadState.selectedUploadCascade,
    retry: false,
  });

  const predictQuery = useQuery({
    queryKey: ["predict-id", selectedId],
    queryFn: () => api.predictById(selectedId as string),
    enabled: Boolean(selectedId) && !uploadState.selectedUploadCascade,
    retry: false,
  });

  const handleUploadCsv = async (file: File) => {
    setUploadState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const csvText =
        typeof file.text === "function"
          ? await file.text()
          : await new Promise<string>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(String(reader.result ?? ""));
              reader.onerror = () => reject(reader.error ?? new Error("Failed to read file."));
              reader.readAsText(file);
            });
      const validation = await api.validateCsv(file);
      let predictions: PredictCascadeResult[] = [];
      try {
        const predRes = await api.predictCsv(file);
        predictions = predRes.predictions;
      } catch (err) {
        if (err instanceof ApiError && err.code === "MODEL_NOT_TRAINED") {
          setUploadState({
            loading: false,
            error: err,
            validationReport: validation.validation_report,
            predictions: [],
            selectedUploadCascade: validation.cascade_ids[0] ?? null,
            csvText,
          });
          return;
        }
        throw err;
      }

      setSelectedId(null);
      setUploadState({
        loading: false,
        error: null,
        validationReport: validation.validation_report,
        predictions,
        selectedUploadCascade: predictions[0]?.cascade_id ?? validation.cascade_ids[0] ?? null,
        csvText,
      });
    } catch (err) {
      setUploadState((prev) => ({
        ...prev,
        loading: false,
        error: err as Error,
      }));
    }
  };

  const activeUploadPrediction = uploadState.predictions.find(
    (p) => p.cascade_id === uploadState.selectedUploadCascade
  );

  const activePrediction: PredictCascadeResult | null = uploadState.selectedUploadCascade
    ? (activeUploadPrediction ?? null)
    : (predictQuery.data?.predictions[0] ?? null);

  const uploadedTreePreview: TreeGraphResponse | null =
    uploadState.selectedUploadCascade && uploadState.csvText
      ? buildClientTreePreview(
          uploadState.csvText,
          uploadState.selectedUploadCascade,
          activeUploadPrediction?.early_window_seconds ?? 3600
        )
      : null;

  const activeTree = uploadState.selectedUploadCascade ? uploadedTreePreview : (treeQuery.data ?? null);

  const noDataset =
    cascadesQuery.error instanceof ApiError && cascadesQuery.error.code === "NO_DATASET";
  const modelNotTrained =
    (predictQuery.error instanceof ApiError && predictQuery.error.code === "MODEL_NOT_TRAINED") ||
    (uploadState.error instanceof ApiError && uploadState.error.code === "MODEL_NOT_TRAINED");

  const maxEarlyNodes = useMemo(() => {
    const items = cascadesQuery.data?.items ?? [];
    return Math.max(1, ...items.map((i) => i.early_nodes));
  }, [cascadesQuery.data]);

  const predFeatures = activePrediction?.features ?? {};
  const statItems = activePrediction && Object.keys(predFeatures).length > 0
    ? [
        { label: "Nodes", value: formatMetric(predFeatures.num_nodes ?? Number.NaN, 0) },
        { label: "Edges", value: formatMetric(predFeatures.num_edges ?? Number.NaN, 0) },
        { label: "Max depth", value: formatMetric(predFeatures.max_depth ?? Number.NaN, 0) },
        { label: "Branching", value: formatMetric(predFeatures.avg_branching ?? Number.NaN, 2) },
        { label: "Virality idx", value: formatMetric(predFeatures.structural_virality ?? Number.NaN, 2) },
        { label: "Event rate", value: `${formatMetric(predFeatures.event_rate ?? Number.NaN, 2)}/s` },
      ]
    : [];

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[300px_minmax(0,1fr)_340px]">
      {/* Cascade picker + upload (3rd on mobile, 1st on desktop) */}
      <section
        aria-label="Cascade selection and CSV upload"
        className="order-3 space-y-4 lg:order-1"
      >
        <Card className="p-4 space-y-3">
          <CardHeader className="mb-1">
            <CardTitle>Dataset Cascades</CardTitle>
            {cascadesQuery.data && (
              <span className="font-mono text-[11px] text-text-3">
                {cascadesQuery.data.dataset_name} ({cascadesQuery.data.total})
              </span>
            )}
          </CardHeader>

          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-text-3"
              strokeWidth={1.5}
              aria-hidden="true"
            />
            <input
              ref={searchInputRef}
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search cascade ID..."
              aria-label="Search cascade ID"
              className="w-full rounded-xl border border-subtle bg-bg-0/90 py-2 pl-8 pr-8 text-xs text-text-1 placeholder:text-text-3 focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
            <kbd
              aria-hidden="true"
              className="pointer-events-none absolute right-2.5 top-2 rounded border border-subtle bg-bg-2 px-1.5 py-0.5 font-mono text-[10px] text-text-3"
            >
              /
            </kbd>
          </div>

          {cascadesQuery.isLoading && (
            <div className="space-y-2 py-2" aria-busy="true">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          )}

          {noDataset && (
            <EmptyState
              title="No Real Dataset Loaded"
              description="Place a public propagation dataset under backend/data/raw/ or upload a canonical CSV below."
              showSetupSteps={true}
            />
          )}

          {cascadesQuery.error && !noDataset && (
            <ErrorBanner
              code={cascadesQuery.error instanceof ApiError ? cascadesQuery.error.code : undefined}
              message={cascadesQuery.error.message}
              onRetry={() => void cascadesQuery.refetch()}
            />
          )}

          {cascadesQuery.data && cascadesQuery.data.items.length === 0 && (
            <p className="py-4 text-center text-xs text-text-3">No matching cascades found.</p>
          )}

          {cascadesQuery.data && cascadesQuery.data.items.length > 0 && (
            <ul className="max-h-72 space-y-1.5 overflow-y-auto pr-1" aria-label="Cascade list">
              {cascadesQuery.data.items.map((item) => {
                const isSelected =
                  !uploadState.selectedUploadCascade && selectedId === item.cascade_id;
                const barWidth = Math.max(8, Math.round((item.early_nodes / maxEarlyNodes) * 100));
                const dotColor =
                  item.is_viral === true
                    ? "bg-viral"
                    : item.is_viral === false
                      ? "bg-calm"
                      : "bg-text-3";

                return (
                  <li key={item.cascade_id}>
                    <button
                      type="button"
                      onClick={() => {
                        setUploadState((prev) => ({
                          ...prev,
                          selectedUploadCascade: null,
                        }));
                        setSelectedId(item.cascade_id);
                      }}
                      className={cn(
                        "w-full rounded-xl border px-3 py-2 text-left text-xs transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                        isSelected
                          ? "border-accent/60 bg-accent/10 text-text-1"
                          : "border-subtle bg-bg-0/60 text-text-2 hover:border-accent/35 hover:bg-bg-2/70"
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="inline-flex items-center gap-2 truncate font-mono font-medium text-text-1">
                          <span
                            aria-hidden="true"
                            className={cn("h-2 w-2 shrink-0 rounded-full", dotColor)}
                          />
                          <span className="truncate">{item.cascade_id}</span>
                        </span>
                        {item.excluded && (
                          <span className="rounded bg-bg-2 px-1.5 py-0.5 font-mono text-[10px] text-text-3">
                            &lt;3 edges
                          </span>
                        )}
                      </div>

                      <div className="mt-1.5 flex items-center justify-between gap-2">
                        <div className="h-1 flex-1 overflow-hidden rounded-full bg-bg-2">
                          <div
                            className="h-full rounded-full bg-accent/75"
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                        <span className="font-mono text-[10px] text-text-3 tabular-nums">
                          {item.early_nodes} → {item.final_size} ·{" "}
                          {formatDuration(item.observation_horizon_seconds)}
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card className="p-4 space-y-3">
          <CardHeader className="mb-1">
            <CardTitle>Upload Canonical CSV</CardTitle>
          </CardHeader>
          <UploadZone
            onFileSelected={handleUploadCsv}
            validationReport={uploadState.validationReport}
            isLoading={uploadState.loading}
          />
          {uploadState.error &&
            !(uploadState.error instanceof ApiError && uploadState.error.code === "MODEL_NOT_TRAINED") && (
              <ErrorBanner
                code={uploadState.error instanceof ApiError ? uploadState.error.code : undefined}
                message={uploadState.error.message}
              />
            )}
          {uploadState.predictions.length > 1 && (
            <div className="space-y-1">
              <label htmlFor="upload-cascade-select" className="text-xs text-text-2">
                Uploaded cascade
              </label>
              <select
                id="upload-cascade-select"
                value={uploadState.selectedUploadCascade ?? ""}
                onChange={(e) =>
                  setUploadState((prev) => ({
                    ...prev,
                    selectedUploadCascade: e.target.value,
                  }))
                }
                className="w-full rounded-xl border border-subtle bg-bg-0 px-2.5 py-1.5 font-mono text-xs text-text-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                {uploadState.predictions.map((p) => (
                  <option key={p.cascade_id} value={p.cascade_id}>
                    {p.cascade_id}
                  </option>
                ))}
              </select>
            </div>
          )}
        </Card>
      </section>

      {/* Center: Tree canvas (2nd on mobile & desktop) */}
      <section aria-label="Propagation tree viewer" className="order-2 min-w-0">
        {treeQuery.isLoading && !uploadState.selectedUploadCascade ? (
          <Card className="p-5 space-y-4">
            <div className="flex justify-between">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-8 w-28" />
            </div>
            <Skeleton className="h-[440px] w-full rounded-xl" />
          </Card>
        ) : treeQuery.error && !uploadState.selectedUploadCascade ? (
          <ErrorBanner
            code={treeQuery.error instanceof ApiError ? treeQuery.error.code : undefined}
            message={treeQuery.error.message}
            onRetry={() => void treeQuery.refetch()}
          />
        ) : activeTree ? (
          <TreeView graph={activeTree} />
        ) : (
          <EmptyState
            title="Select or Upload a Cascade"
            description="Choose a real cascade from the dataset or upload a canonical edge CSV to inspect its early propagation tree."
            showSetupSteps={false}
          />
        )}
      </section>

      {/* Prediction panel (1st on mobile, 3rd on desktop) */}
      <section
        aria-label="Prediction and explanation"
        className="order-1 space-y-4 lg:order-3"
      >
        {modelNotTrained ? (
          <EmptyState
            title="Model Not Trained Yet"
            description="Train the Random Forest and baseline pipelines on your real dataset to enable early virality predictions."
            showSetupSteps={true}
          />
        ) : predictQuery.isLoading && !uploadState.selectedUploadCascade ? (
          <AnalyzePanelSkeleton />
        ) : predictQuery.error && !uploadState.selectedUploadCascade ? (
          <ErrorBanner
            code={predictQuery.error instanceof ApiError ? predictQuery.error.code : undefined}
            message={predictQuery.error.message}
            onRetry={() => void predictQuery.refetch()}
          />
        ) : activePrediction ? (
          <>
            <Card className="space-y-4">
              <CardHeader className="mb-0">
                <div>
                  <CardTitle>Early Virality Prediction</CardTitle>
                  <p className="mt-1 font-mono text-xs text-text-3">
                    {activePrediction.cascade_id}
                  </p>
                </div>
                <Chip variant="cyan">
                  {formatDuration(activePrediction.early_window_seconds)} window
                </Chip>
              </CardHeader>

              {activePrediction.excluded ? (
                <div
                  role="status"
                  className="flex items-start gap-3 rounded-xl border border-subtle bg-bg-2/75 p-4 text-xs text-text-2"
                >
                  <Info
                    className="mt-0.5 h-4 w-4 shrink-0 text-accent-2"
                    strokeWidth={1.5}
                    aria-hidden="true"
                  />
                  <div>
                    <p className="font-semibold text-text-1">Cascade Excluded</p>
                    <p className="mt-1 leading-relaxed">{activePrediction.exclusion_reason}</p>
                  </div>
                </div>
              ) : (
                <>
                  <ProbabilityGauge
                    probability={activePrediction.virality_probability ?? 0}
                    threshold={activePrediction.decision_threshold}
                    predictedViral={Boolean(activePrediction.predicted_viral)}
                  />
                  <p className="text-center text-xs text-text-3">
                    Viral class defined as final size &ge;{" "}
                    <span className="font-mono font-medium text-text-1">
                      {activePrediction.virality_threshold_size}
                    </span>{" "}
                    nodes (training quantile).
                  </p>
                </>
              )}
            </Card>

            {!activePrediction.excluded && (activePrediction.top_factors ?? []).length > 0 && (
              <ChartFrame
                title="Top Contributing Factors"
                subtitle="Approximate, based on global importance"
                summary={`Diverging factor contribution chart for cascade ${activePrediction.cascade_id}.`}
              >
                <Suspense fallback={<Skeleton className="h-52 w-full" />}>
                  <TopFactorsChart factors={activePrediction.top_factors ?? []} />
                </Suspense>
              </ChartFrame>
            )}

            {statItems.length > 0 && (
              <Card className="p-4 space-y-3">
                <CardTitle>Early Graph Statistics</CardTitle>
                <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-2">
                  {statItems.map((st) => (
                    <StatTile
                      key={st.label}
                      compact
                      label={st.label}
                      value={st.value}
                    />
                  ))}
                </div>
              </Card>
            )}
          </>
        ) : (
          <EmptyState
            title="No Prediction Selected"
            description="Select a cascade from the dataset or upload a CSV file."
            showSetupSteps={false}
          />
        )}
      </section>
    </div>
  );
}
