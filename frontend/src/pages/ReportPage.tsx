import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Info, Star } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ApiError, api, type ModelMetricsEntry } from "../api/client";
import { ChartFrame } from "../components/ChartFrame";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { Badge, Chip } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader, CardTitle } from "../components/ui/Card";
import { InlineAlert } from "../components/ui/InlineAlert";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { ReportSkeleton } from "../components/ui/Skeleton";
import { StatTile } from "../components/ui/StatTile";
import { cn } from "../lib/cn";
import { formatDuration, formatMetric, formatPct } from "../lib/format";

const GLASS_TOOLTIP_STYLE = {
  backgroundColor: "rgba(12, 19, 36, 0.9)",
  backdropFilter: "blur(12px)",
  border: "1px solid rgba(148, 163, 255, 0.16)",
  borderRadius: "12px",
  color: "#E6EBFF",
  fontSize: "12px",
  fontFamily: "JetBrains Mono Variable",
};

const AXIS_TICK_STYLE = {
  fill: "#7D8BB0",
  fontSize: 12,
  fontFamily: "JetBrains Mono Variable",
};

function DeltaSparkline({ positive }: { positive: boolean }) {
  return (
    <svg viewBox="0 0 36 16" className="h-4 w-9 shrink-0" aria-hidden="true" fill="none">
      <path
        d={positive ? "M2 13L11 9L20 10L34 3" : "M2 4L12 7L22 6L34 12"}
        stroke={positive ? "#34D399" : "#F59E0B"}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function formatDelta(val: number, base: number, lowerIsBetter = false): {
  text: string;
  tone: "positive" | "negative" | "neutral";
} {
  const diff = val - base;
  if (!Number.isFinite(diff)) return { text: "—", tone: "neutral" };
  const improved = lowerIsBetter ? diff < -1e-4 : diff > 1e-4;
  const worsened = lowerIsBetter ? diff > 1e-4 : diff < -1e-4;
  const sign = diff > 0 ? "+" : "";
  return {
    text: `${sign}${diff.toFixed(3)} vs naive`,
    tone: improved ? "positive" : worsened ? "negative" : "neutral",
  };
}

export function ReportPage() {
  const [importanceMode, setImportanceMode] = useState<"permutation" | "impurity">("permutation");
  const [caveatsExpanded, setCaveatsExpanded] = useState(false);
  const [showTechnical, setShowTechnical] = useState(false);

  const reportQuery = useQuery({
    queryKey: ["report"],
    queryFn: () => api.getReport(),
    retry: false,
  });

  const report = reportQuery.data;

  const bestTemporalModel = useMemo<ModelMetricsEntry | undefined>(() => {
    if (!report || report.temporal_test_results.length === 0) return undefined;
    return [...report.temporal_test_results].sort((a, b) => b.pr_auc - a.pr_auc)[0];
  }, [report]);

  if (reportQuery.isLoading) {
    return <ReportSkeleton />;
  }

  if (reportQuery.error) {
    if (
      reportQuery.error instanceof ApiError &&
      (reportQuery.error.code === "MODEL_NOT_TRAINED" || reportQuery.error.code === "NO_DATASET")
    ) {
      return (
        <EmptyState
          title="Evaluation Report Not Available"
          description={reportQuery.error.message}
          showSetupSteps={true}
        />
      );
    }
    return (
      <ErrorBanner
        code={reportQuery.error instanceof ApiError ? reportQuery.error.code : undefined}
        message={reportQuery.error.message}
        onRetry={() => void reportQuery.refetch()}
      />
    );
  }

  if (!report) return null;

  const ds = report.dataset_summary;
  const rfMetrics = report.temporal_test_results.find((m) => m.model_key === "rf");
  const naiveMetrics = report.temporal_test_results.find((m) => m.model_key === "naive_edges");
  const headline = bestTemporalModel ?? rfMetrics;

  interface ModelCurveData {
    roc?: { fpr: number[]; tpr: number[] };
    pr?: { recall: number[]; precision: number[] };
  }
  const curvesObj = report.curves as { temporal_test?: Record<string, ModelCurveData> };
  const rocCurves: Record<string, ModelCurveData> = curvesObj.temporal_test ?? {};
  const rfRoc = rocCurves.rf?.roc;
  const naiveRoc = rocCurves.naive_edges?.roc;
  const rocChartData =
    rfRoc?.fpr.map((fpr: number, idx: number) => ({
      fpr: Number(fpr.toFixed(3)),
      rf_tpr: rfRoc.tpr[idx] ?? 0,
      naive_tpr: naiveRoc?.tpr[Math.min(idx, (naiveRoc?.tpr.length ?? 1) - 1)] ?? null,
    })) ?? [];

  const rfPr = rocCurves.rf?.pr;
  const prChartData =
    rfPr?.recall.map((rec: number, idx: number) => ({
      recall: Number(rec.toFixed(3)),
      rf_precision: rfPr.precision[idx] ?? 0,
    })) ?? [];

  const cm = rfMetrics?.confusion_matrix ?? [
    [0, 0],
    [0, 0],
  ];
  const cmMax = Math.max(1, cm[0]?.[0] ?? 0, cm[0]?.[1] ?? 0, cm[1]?.[0] ?? 0, cm[1]?.[1] ?? 0);
  const row0Total = Math.max(1, (cm[0]?.[0] ?? 0) + (cm[0]?.[1] ?? 0));
  const row1Total = Math.max(1, (cm[1]?.[0] ?? 0) + (cm[1]?.[1] ?? 0));

  // Best-per-column tracking for comparison table
  const maxPrAuc = Math.max(...report.temporal_test_results.map((r) => r.pr_auc));
  const maxRocAuc = Math.max(...report.temporal_test_results.map((r) => r.roc_auc));
  const maxRecall = Math.max(...report.temporal_test_results.map((r) => r.recall));
  const maxPrecision = Math.max(...report.temporal_test_results.map((r) => r.precision));

  const prDelta = formatDelta(headline?.pr_auc ?? Number.NaN, naiveMetrics?.pr_auc ?? Number.NaN);
  const recDelta = formatDelta(headline?.recall ?? Number.NaN, naiveMetrics?.recall ?? Number.NaN);

  const sortedImportances = [...report.feature_importance]
    .sort((a, b) =>
      importanceMode === "permutation"
        ? Math.abs(b.permutation_importance_mean) - Math.abs(a.permutation_importance_mean)
        : (b.impurity_importance ?? 0) - (a.impurity_importance ?? 0)
    )
    .slice(0, 12);

  const visibleLimitations = caveatsExpanded ? report.limitations : report.limitations.slice(0, 3);

  return (
    <div className="space-y-6">
      {/* Baseline comparison notice */}
      <InlineAlert
        tone={report.beats_naive_baseline ? "info" : "warning"}
        title={`Naive Baseline Verdict · Best model: ${headline?.display_name ?? "Random Forest"}`}
        message={report.baseline_comparison_note}
      />

      {/* Header strip: headline KPIs (full metrics remain in the table below) */}
      <section aria-label="Temporal test KPI summary" className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatTile
          label="PR-AUC (Headline)"
          value={formatMetric(headline?.pr_auc ?? Number.NaN)}
          delta={prDelta.text}
          deltaTone={prDelta.tone}
          sparkline={<DeltaSparkline positive={prDelta.tone === "positive"} />}
          sublabel={
            headline?.pr_auc_ci
              ? `95% CI [${formatMetric(headline.pr_auc_ci.low)}, ${formatMetric(headline.pr_auc_ci.high)}]`
              : undefined
          }
          accent="cyan"
        />
        <StatTile
          label="Recall (Viral class)"
          value={formatPct(headline?.recall ?? 0)}
          delta={recDelta.text}
          deltaTone={recDelta.tone}
          sparkline={<DeltaSparkline positive={recDelta.tone === "positive"} />}
          sublabel={`Virality >= ${report.virality_threshold_size} nodes (q=${report.virality_quantile.toFixed(2)})`}
          accent="viral"
        />
      </section>

      {/* Dataset Summary + Log-Scale Distribution */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <Card className="space-y-4 lg:col-span-12">
          <CardHeader className="mb-0">
            <CardTitle>Dataset Summary · {ds.dataset_name}</CardTitle>
            <Chip variant="neutral">hash {ds.dataset_hash.slice(0, 8)}</Chip>
          </CardHeader>
          <p className="text-xs leading-relaxed text-text-2">{ds.source_description}</p>
          {showTechnical && (
            <p className="rounded-xl border border-subtle bg-bg-0/75 p-3 text-xs leading-relaxed text-text-2">
              <span className="font-semibold text-accent-2">Tree &amp; horizon note: </span>
              {ds.reconstruction_note}
            </p>
          )}

          <dl className="grid grid-cols-2 gap-2.5 text-xs">
            <div className="rounded-xl border border-subtle bg-bg-2/50 p-3">
              <dt className="text-[11px] uppercase tracking-[0.06em] text-text-3">Window / Horizon</dt>
              <dd className="mt-1 font-mono text-text-1 tabular-nums">
                {formatDuration(ds.early_window_seconds)} /{" "}
                {formatDuration(ds.observation_horizon_seconds)}
              </dd>
            </div>
            <div className="rounded-xl border border-subtle bg-bg-2/50 p-3">
              <dt className="text-[11px] uppercase tracking-[0.06em] text-text-3">Eligible / Raw</dt>
              <dd className="mt-1 font-mono text-text-1 tabular-nums">
                {ds.eligible_cascades} / {ds.total_cascades_raw}
              </dd>
            </div>
            <div className="rounded-xl border border-subtle bg-bg-2/50 p-3">
              <dt className="text-[11px] uppercase tracking-[0.06em] text-text-3">Splits (T / V / Te)</dt>
              <dd className="mt-1 font-mono text-text-1 tabular-nums">
                {ds.split_counts.train ?? 0} / {ds.split_counts.val ?? 0} /{" "}
                {ds.split_counts.test ?? 0}
              </dd>
            </div>
          </dl>
        </Card>

        {showTechnical && (
        <ChartFrame
          title="Final Cascade Size Distribution (Log-Scale Bins)"
          subtitle="Heavy-tailed final node counts across observed cascades."
          summary="Bar chart of final cascade size distribution on log-scale size buckets."
          className="lg:col-span-6"
        >
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ds.size_histogram_log}>
                <CartesianGrid stroke="rgba(230,235,255,0.06)" vertical={false} />
                <XAxis
                  dataKey="bin_label"
                  tick={AXIS_TICK_STYLE}
                  axisLine={{ stroke: "#7D8BB0", strokeWidth: 1 }}
                  tickLine={false}
                />
                <YAxis
                  tick={AXIS_TICK_STYLE}
                  axisLine={{ stroke: "#7D8BB0", strokeWidth: 1 }}
                  tickLine={false}
                />
                <Tooltip contentStyle={GLASS_TOOLTIP_STYLE} cursor={{ fill: "rgba(79,140,255,0.08)" }} />
                <Bar
                  dataKey="count"
                  name="Cascades"
                  fill="#4F8CFF"
                  radius={[6, 6, 0, 0]}
                  animationDuration={800}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartFrame>
        )}
      </section>

      {/* Model comparison table */}
      <Card className="space-y-3 overflow-x-auto">
        <CardHeader className="mb-0">
          <CardTitle>Temporal Test Set Model Comparison (Chronological Split)</CardTitle>
          <span className="inline-flex items-center gap-1 text-[11px] text-text-3">
            <Star className="h-3 w-3 text-viral" strokeWidth={1.75} aria-hidden="true" />
            Best value per metric
          </span>
        </CardHeader>

        <div className="max-h-96 overflow-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 z-10 border-b border-subtle bg-bg-1 text-[11px] uppercase tracking-[0.06em] text-text-3">
              <tr>
                <th className="py-2.5 pr-4">Model</th>
                <th className="py-2.5 pr-4">PR-AUC (95% CI)</th>
                <th className="py-2.5 pr-4">ROC-AUC (95% CI)</th>
                <th className="py-2.5 pr-4">Recall</th>
                <th className="py-2.5">Precision</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-subtle">
              {report.temporal_test_results.map((row) => {
                const isNaive = row.model_key === "naive_edges";
                return (
                  <tr
                    key={row.model_key}
                    className={cn(
                      "transition-colors hover:bg-bg-2/40",
                      isNaive && "outline-dashed outline-1 -outline-offset-1 outline-accent/60 bg-accent/5"
                    )}
                  >
                    <td className="py-3 pr-4 font-medium text-text-1">
                      <span className="inline-flex flex-wrap items-center gap-2">
                        <span>{row.display_name}</span>
                        {isNaive && <Badge variant="accent">baseline</Badge>}
                      </span>
                    </td>
                    <td className="py-3 pr-4 font-mono tabular-nums text-accent-2">
                      <span className="inline-flex items-center gap-1">
                        {formatMetric(row.pr_auc)}
                        {row.pr_auc >= maxPrAuc - 1e-9 && (
                          <Star className="h-3 w-3 text-viral" strokeWidth={1.75} aria-label="Best PR-AUC" />
                        )}
                      </span>
                      {row.pr_auc_ci && (
                        <span className="ml-1.5 text-[11px] text-text-3">
                          [{formatMetric(row.pr_auc_ci.low, 2)}, {formatMetric(row.pr_auc_ci.high, 2)}]
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-4 font-mono tabular-nums text-text-1">
                      <span className="inline-flex items-center gap-1">
                        {formatMetric(row.roc_auc)}
                        {row.roc_auc >= maxRocAuc - 1e-9 && (
                          <Star className="h-3 w-3 text-viral" strokeWidth={1.75} aria-label="Best ROC-AUC" />
                        )}
                      </span>
                      {row.roc_auc_ci && (
                        <span className="ml-1.5 text-[11px] text-text-3">
                          [{formatMetric(row.roc_auc_ci.low, 2)}, {formatMetric(row.roc_auc_ci.high, 2)}]
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-4 font-mono tabular-nums text-text-1">
                      <span className="inline-flex items-center gap-1">
                        {formatMetric(row.recall)}
                        {row.recall >= maxRecall - 1e-9 && (
                          <Star className="h-3 w-3 text-viral" strokeWidth={1.75} aria-label="Best Recall" />
                        )}
                      </span>
                    </td>
                    <td className="py-3 font-mono tabular-nums text-text-2">
                      <span className="inline-flex items-center gap-1">
                        {formatMetric(row.precision)}
                        {row.precision >= maxPrecision - 1e-9 && (
                          <Star className="h-3 w-3 text-viral" strokeWidth={1.75} aria-label="Best Precision" />
                        )}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Advanced technical details (collapsed by default) */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-text-1">Technical evaluation details</h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowTechnical((v) => !v)}
          aria-expanded={showTechnical}
        >
          {showTechnical ? (
            <>
              <span>Hide details</span>
              <ChevronUp className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
            </>
          ) : (
            <>
              <span>Show curves &amp; sensitivity</span>
              <ChevronDown className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
            </>
          )}
        </Button>
      </div>

      {showTechnical && (
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <ChartFrame
          title="ROC Curve (Temporal Test)"
          subtitle="Random Forest vs Naive num_edges baseline"
          summary="ROC curve comparing Random Forest and naive baseline true positive vs false positive rates."
        >
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={rocChartData}>
                <CartesianGrid stroke="rgba(230,235,255,0.06)" vertical={false} />
                <XAxis
                  dataKey="fpr"
                  tick={AXIS_TICK_STYLE}
                  axisLine={{ stroke: "#7D8BB0", strokeWidth: 1 }}
                  tickLine={false}
                />
                <YAxis
                  domain={[0, 1]}
                  tick={AXIS_TICK_STYLE}
                  axisLine={{ stroke: "#7D8BB0", strokeWidth: 1 }}
                  tickLine={false}
                />
                <Tooltip contentStyle={GLASS_TOOLTIP_STYLE} cursor={{ stroke: "#4F8CFF", strokeWidth: 1 }} />
                <Legend wrapperStyle={{ fontSize: "11px" }} />
                <Area
                  type="monotone"
                  dataKey="rf_tpr"
                  name="Random Forest"
                  stroke="#22D3EE"
                  fill="#22D3EE"
                  fillOpacity={0.12}
                  strokeWidth={2.5}
                  dot={false}
                  animationDuration={800}
                />
                <Area
                  type="monotone"
                  dataKey="naive_tpr"
                  name="Naive (num_edges)"
                  stroke="#F59E0B"
                  fill="#F59E0B"
                  fillOpacity={0.08}
                  strokeWidth={2}
                  dot={false}
                  animationDuration={800}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartFrame>

        <ChartFrame
          title="Precision-Recall Curve (RF)"
          subtitle="Headline evaluation for imbalanced positives"
          summary="Precision-Recall curve for Random Forest on the temporal test split."
        >
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={prChartData}>
                <CartesianGrid stroke="rgba(230,235,255,0.06)" vertical={false} />
                <XAxis
                  dataKey="recall"
                  tick={AXIS_TICK_STYLE}
                  axisLine={{ stroke: "#7D8BB0", strokeWidth: 1 }}
                  tickLine={false}
                />
                <YAxis
                  domain={[0, 1]}
                  tick={AXIS_TICK_STYLE}
                  axisLine={{ stroke: "#7D8BB0", strokeWidth: 1 }}
                  tickLine={false}
                />
                <Tooltip contentStyle={GLASS_TOOLTIP_STYLE} cursor={{ stroke: "#38BDF8", strokeWidth: 1 }} />
                <Area
                  type="monotone"
                  dataKey="rf_precision"
                  name="RF Precision"
                  stroke="#38BDF8"
                  fill="#38BDF8"
                  fillOpacity={0.12}
                  strokeWidth={2.5}
                  dot={false}
                  animationDuration={800}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartFrame>

        <Card className="flex flex-col justify-between space-y-3">
          <CardHeader className="mb-0">
            <CardTitle>Confusion Matrix (Random Forest)</CardTitle>
            <span className="font-mono text-[11px] text-text-3">Count · Row %</span>
          </CardHeader>

          <div className="grid grid-cols-2 gap-2.5 text-center text-xs flex-1 items-stretch">
            {[
              {
                label: "True Negative",
                count: cm[0]?.[0] ?? 0,
                pct: (cm[0]?.[0] ?? 0) / row0Total,
                rgb: "56, 189, 248",
                textClass: "text-calm",
              },
              {
                label: "False Positive",
                count: cm[0]?.[1] ?? 0,
                pct: (cm[0]?.[1] ?? 0) / row0Total,
                rgb: "245, 158, 11",
                textClass: "text-viral",
              },
              {
                label: "False Negative",
                count: cm[1]?.[0] ?? 0,
                pct: (cm[1]?.[0] ?? 0) / row1Total,
                rgb: "248, 113, 113",
                textClass: "text-danger",
              },
              {
                label: "True Positive",
                count: cm[1]?.[1] ?? 0,
                pct: (cm[1]?.[1] ?? 0) / row1Total,
                rgb: "245, 158, 11",
                textClass: "text-viral",
              },
            ].map((cell) => {
              const alpha = 0.06 + 0.22 * (cell.count / cmMax);
              return (
                <div
                  key={cell.label}
                  className="flex flex-col justify-center rounded-xl border border-subtle p-4"
                  style={{ backgroundColor: `rgba(${cell.rgb}, ${alpha.toFixed(2)})` }}
                >
                  <p className="text-[11px] uppercase tracking-[0.06em] text-text-2">{cell.label}</p>
                  <p className={cn("mt-1 font-mono text-2xl font-semibold tabular-nums", cell.textClass)}>
                    {cell.count}
                  </p>
                  <p className="mt-0.5 font-mono text-[11px] text-text-3 tabular-nums">
                    {formatPct(cell.pct)}
                  </p>
                </div>
              );
            })}
          </div>
        </Card>
      </section>
      )}

      {/* Feature Importance + Threshold Sensitivity */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <ChartFrame
          title="Feature Importance"
          subtitle="Clustering coefficient is 0.0 on pure trees and retained explicitly."
          summary={`Ranked horizontal bar chart of ${importanceMode} feature importance.`}
          headerRight={
            <SegmentedControl
              ariaLabel="Feature importance metric"
              value={importanceMode}
              onChange={setImportanceMode}
              options={[
                { value: "permutation", label: "Permutation" },
                { value: "impurity", label: "Impurity" },
              ]}
            />
          }
          className={showTechnical ? "lg:col-span-7" : "lg:col-span-12"}
        >
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={sortedImportances}
                layout="vertical"
                margin={{ left: 16, right: 16 }}
              >
                <CartesianGrid stroke="rgba(230,235,255,0.06)" vertical={false} />
                <XAxis
                  type="number"
                  tick={AXIS_TICK_STYLE}
                  axisLine={{ stroke: "#7D8BB0", strokeWidth: 1 }}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="feature"
                  width={138}
                  tick={{ fill: "#9AA6C7", fontSize: 11, fontFamily: "JetBrains Mono Variable" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip contentStyle={GLASS_TOOLTIP_STYLE} cursor={{ fill: "rgba(79,140,255,0.08)" }} />
                <Bar
                  dataKey={
                    importanceMode === "permutation"
                      ? "permutation_importance_mean"
                      : "impurity_importance"
                  }
                  name={
                    importanceMode === "permutation"
                      ? "Permutation (PR-AUC drop)"
                      : "RF Impurity"
                  }
                  fill={importanceMode === "permutation" ? "#22D3EE" : "#4F8CFF"}
                  radius={[0, 6, 6, 0]}
                  animationDuration={700}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartFrame>

        {showTechnical && (
        <Card className="space-y-4 lg:col-span-5">
          <CardTitle>Threshold Quantile Sensitivity</CardTitle>
          <table className="w-full text-left text-xs">
            <thead className="border-b border-subtle text-[11px] uppercase tracking-[0.06em] text-text-3">
              <tr>
                <th className="py-2">Quantile</th>
                <th className="py-2">Size &ge;</th>
                <th className="py-2">Pos Rate</th>
                <th className="py-2">RF PR-AUC</th>
                <th className="py-2">Naive PR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-subtle">
              {report.threshold_sensitivity.map((s) => (
                <tr key={s.quantile} className="text-text-2">
                  <td className="py-2.5 font-mono text-text-1">q={s.quantile.toFixed(2)}</td>
                  <td className="py-2.5 font-mono tabular-nums">{s.threshold_size}</td>
                  <td className="py-2.5 font-mono tabular-nums">{formatPct(s.positive_rate_test)}</td>
                  <td className="py-2.5 font-mono tabular-nums text-accent-2">
                    {formatMetric(s.rf_pr_auc)}
                  </td>
                  <td className="py-2.5 font-mono tabular-nums text-viral">
                    {formatMetric(s.naive_pr_auc)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="border-t border-subtle pt-4 space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-viral">
              Optimistic Random Split Comparison
            </p>
            <p className="text-xs leading-relaxed text-text-3">
              Stratified random splits mix future and past cascades and typically inflate scores
              relative to the primary chronological temporal split:
            </p>
            <ul className="space-y-1 font-mono text-xs text-text-2 tabular-nums">
              {report.random_split_comparison.map((r) => (
                <li key={r.model_key}>
                  {r.display_name}: PR-AUC {formatMetric(r.pr_auc)} · ROC-AUC{" "}
                  {formatMetric(r.roc_auc)}
                </li>
              ))}
            </ul>
          </div>
        </Card>
        )}
      </section>

      {/* Collapsible Caveat Panel */}
      <Card className="border-l-2 border-l-accent space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-accent-2" strokeWidth={1.5} aria-hidden="true" />
            <CardTitle>Limitations of the Evidence</CardTitle>
          </div>
          {report.limitations.length > 3 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCaveatsExpanded((v) => !v)}
              aria-expanded={caveatsExpanded}
            >
              {caveatsExpanded ? (
                <>
                  <span>Collapse</span>
                  <ChevronUp className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                </>
              ) : (
                <>
                  <span>Show all ({report.limitations.length})</span>
                  <ChevronDown className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                </>
              )}
            </Button>
          )}
        </div>

        <ul className="list-inside list-disc space-y-1.5 text-xs leading-relaxed text-text-2">
          {visibleLimitations.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
