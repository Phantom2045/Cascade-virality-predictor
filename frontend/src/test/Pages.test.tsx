import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, type ReportResponse } from "../api/client";
import { AppRoutes } from "../App";

function renderRoute(path: string) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const sampleReport: ReportResponse = {
  dataset_summary: {
    dataset_name: "twitter15",
    dataset_hash: "abc123",
    source_description: "Ma et al. Twitter15",
    reconstruction_note: "Explicit tree edges.",
    observation_horizon_seconds: 86400,
    early_window_seconds: 3600,
    total_cascades_raw: 100,
    eligible_cascades: 90,
    excluded_by_split: { train: 6, val: 1, test: 3 },
    split_counts: { train: 63, val: 9, test: 18 },
    positive_rate_by_split: { train: 0.2, val: 0.22, test: 0.22 },
    size_summary: { min: 4, median: 22, p90: 120, max: 500, mean: 45 },
    size_histogram_log: [{ bin_label: "16-50", min_size: 16, max_size: 50, count: 40 }],
    validation_report: {
      is_valid: true,
      total_rows: 1000,
      valid_edges: 980,
      cascades_count: 100,
      missing_columns: [],
      malformed_rows_dropped: 0,
      negative_timestamps_dropped: 0,
      self_loops_dropped: 2,
      duplicate_edges_dropped: 3,
      multiple_parents_resolved: 1,
      cycles_detected: 0,
      cycle_edges_removed: 0,
      multiple_roots_cascades: 0,
      actions_taken: [],
      warnings: [],
    },
  },
  virality_quantile: 0.8,
  virality_threshold_size: 85,
  beats_naive_baseline: true,
  baseline_comparison_note: "Random Forest outperformed naive num_edges on temporal PR-AUC.",
  temporal_test_results: [
    {
      model_key: "rf",
      display_name: "Random Forest",
      split_name: "temporal_test",
      accuracy: 0.82,
      precision: 0.71,
      recall: 0.75,
      f1: 0.73,
      roc_auc: 0.85,
      pr_auc: 0.78,
      brier_score: 0.14,
      roc_auc_ci: { low: 0.75, high: 0.93 },
      pr_auc_ci: { low: 0.65, high: 0.89 },
      confusion_matrix: [
        [12, 2],
        [1, 3],
      ],
    },
    {
      model_key: "naive_edges",
      display_name: "Naive Baseline (num_edges only)",
      split_name: "temporal_test",
      accuracy: 0.75,
      precision: 0.6,
      recall: 0.6,
      f1: 0.6,
      roc_auc: 0.76,
      pr_auc: 0.64,
      brier_score: 0.19,
      confusion_matrix: [
        [11, 3],
        [2, 2],
      ],
    },
  ],
  random_split_comparison: [
    {
      model_key: "rf",
      display_name: "Random Forest (optimistic random split)",
      split_name: "random_test_optimistic",
      accuracy: 0.86,
      precision: 0.78,
      recall: 0.8,
      f1: 0.79,
      roc_auc: 0.89,
      pr_auc: 0.83,
      brier_score: 0.11,
      confusion_matrix: [
        [13, 1],
        [1, 3],
      ],
    },
  ],
  feature_importance: [
    {
      feature: "num_edges",
      permutation_importance_mean: 0.12,
      permutation_importance_std: 0.02,
      impurity_importance: 0.25,
      note: null,
    },
  ],
  threshold_sensitivity: [
    {
      quantile: 0.8,
      threshold_size: 85,
      positive_rate_train: 0.2,
      positive_rate_test: 0.22,
      rf_pr_auc: 0.78,
      rf_roc_auc: 0.85,
      rf_recall: 0.75,
      naive_pr_auc: 0.64,
    },
  ],
  curves: {
    temporal_test: {
      rf: {
        roc: { fpr: [0, 0.2, 1], tpr: [0, 0.8, 1] },
        pr: { recall: [0, 0.8, 1], precision: [1, 0.75, 0.22] },
      },
      naive_edges: {
        roc: { fpr: [0, 0.3, 1], tpr: [0, 0.6, 1] },
      },
    },
  },
  limitations: ["Evidence comes strictly from the loaded dataset."],
  disclaimer: "Predicts propagation behaviour, not truthfulness.",
};

describe("Pages and API integration states", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders AnalyzePage empty state when no dataset or model exists", async () => {
    vi.spyOn(api, "getCascades").mockRejectedValue(
      new ApiError(404, "NO_DATASET", "No real dataset found.")
    );
    renderRoute("/");
    expect(await screen.findByText(/No Real Dataset Loaded/i)).toBeInTheDocument();
    expect(screen.getByText(/Predicts spreading behaviour, not truthfulness/i)).toBeInTheDocument();
  });

  it("renders AnalyzePage success state and CSV upload validation flow", async () => {
    vi.spyOn(api, "getCascades").mockResolvedValue({
      dataset_name: "twitter15",
      early_window_seconds: 3600,
      total: 1,
      limit: 50,
      offset: 0,
      items: [
        {
          cascade_id: "c100",
          early_nodes: 5,
          early_edges: 4,
          final_size: 50,
          observation_horizon_seconds: 3600,
          is_viral: true,
          excluded: false,
        },
      ],
    });
    vi.spyOn(api, "getCascadeTree").mockResolvedValue({
      cascade_id: "c100",
      early_window_seconds: 3600,
      root_id: "u0",
      total_nodes: 2,
      total_edges: 1,
      returned_nodes: 2,
      truncated: false,
      truncation_notice: null,
      nodes: [
        {
          id: "u0",
          parent_id: null,
          timestamp: 0,
          depth: 0,
          is_root: true,
          is_leaf: false,
          out_degree: 1,
        },
        {
          id: "u1",
          parent_id: "u0",
          timestamp: 10,
          depth: 1,
          is_root: false,
          is_leaf: true,
          out_degree: 0,
        },
      ],
      edges: [{ parent_id: "u0", child_id: "u1", timestamp: 10 }],
      stats: { num_nodes: 2 },
    });
    vi.spyOn(api, "predictById").mockResolvedValue({
      validation_report: null,
      predictions: [
        {
          cascade_id: "c100",
          excluded: false,
          predicted_viral: true,
          virality_probability: 0.78,
          decision_threshold: 0.5,
          virality_threshold_size: 40,
          early_window_seconds: 3600,
          explanation_note: "Approximate, based on global permutation importance.",
          disclaimer: "Predicts spreading behaviour, not truthfulness.",
          top_factors: [
            {
              feature: "num_edges",
              value: 4,
              training_median: 3,
              importance_weight: 0.1,
              contribution_score: 0.1,
              direction: "increases_virality",
            },
          ],
          features: { num_nodes: 5, num_edges: 4 },
        },
      ],
    });
    vi.spyOn(api, "validateCsv").mockResolvedValue({
      validation_report: sampleReport.dataset_summary.validation_report,
      cascade_ids: ["up1"],
    });
    vi.spyOn(api, "predictCsv").mockResolvedValue({
      validation_report: sampleReport.dataset_summary.validation_report,
      predictions: [
        {
          cascade_id: "up1",
          excluded: true,
          exclusion_reason: "Excluded: minimum 3 required.",
          predicted_viral: null,
          virality_probability: null,
          decision_threshold: 0.5,
          virality_threshold_size: 40,
          early_window_seconds: 3600,
          explanation_note: "Approximate",
          disclaimer: "Predicts spreading behaviour",
          top_factors: [],
          features: {},
        },
      ],
    });

    vi.spyOn(api, "getHealth").mockResolvedValue({
      status: "ok",
      model_loaded: true,
      dataset_loaded: true,
      active_dataset: "twitter15",
      disclaimer: "Predicts spreading behaviour, not truthfulness.",
    });

    renderRoute("/");
    expect(await screen.findByText("Highly viral")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toBeInTheDocument();

    const csvFile = new File(
      ["cascade_id,parent_id,child_id,timestamp\nup1,,u0,0\nup1,u0,u1,5\n"],
      "upload.csv",
      { type: "text/csv" }
    );
    const input = screen.getByLabelText(/Upload canonical cascade CSV/i);
    await userEvent.upload(input, csvFile);

    await waitFor(() => {
      expect(screen.getByLabelText(/CSV validation report/i)).toBeInTheDocument();
      expect(screen.getByText(/Cascade Excluded/i)).toBeInTheDocument();
    });
  });

  it("renders ReportPage loading, empty, error, and success states", async () => {
    vi.spyOn(api, "getHealth").mockResolvedValue({
      status: "ok",
      model_loaded: false,
      dataset_loaded: false,
      active_dataset: null,
      disclaimer: "Predicts spreading behaviour, not truthfulness.",
    });
    vi.spyOn(api, "getReport").mockRejectedValueOnce(
      new ApiError(503, "MODEL_NOT_TRAINED", "Train model first.")
    );
    renderRoute("/report");
    expect(await screen.findByText(/Evaluation Report Not Available/i)).toBeInTheDocument();

    vi.spyOn(api, "getReport").mockRejectedValueOnce(
      new ApiError(500, "INTERNAL_SERVER_ERROR", "Server error.")
    );
    renderRoute("/report");
    expect(await screen.findByRole("alert")).toHaveTextContent("INTERNAL_SERVER_ERROR");

    vi.spyOn(api, "getReport").mockResolvedValueOnce(sampleReport);
    renderRoute("/report");
    expect(await screen.findByText(/Dataset Summary · twitter15/i)).toBeInTheDocument();
    expect(screen.getByText("baseline")).toBeInTheDocument();
  });

  it("renders AboutPage with limitations and ethics", async () => {
    vi.spyOn(api, "getHealth").mockResolvedValue({
      status: "ok",
      model_loaded: false,
      dataset_loaded: false,
      active_dataset: null,
      disclaimer: "Predicts spreading behaviour, not truthfulness.",
    });
    renderRoute("/about");
    expect(
      await screen.findByRole("heading", { name: /Problem & Method/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Honest Limitations/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/Virality is not truthfulness/i)).toBeInTheDocument();
  });

  it("handles API error envelope cleanly in client", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        headers: { get: () => "application/json" },
        json: async () => ({ code: "INVALID_INPUT", message: "Bad CSV columns", details: null }),
      })
    );
    await expect(api.getHealth()).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      code: "INVALID_INPUT",
      message: "Bad CSV columns",
    });
  });
});
