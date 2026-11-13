import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { TreeGraphResponse, TreeNodePayload } from "../api/client";
import { TreeView } from "../components/TreeView";

describe("TreeView", () => {
  it("renders a single-node cascade", () => {
    const graph: TreeGraphResponse = {
      cascade_id: "single",
      early_window_seconds: 3600,
      root_id: "n0",
      total_nodes: 1,
      total_edges: 0,
      returned_nodes: 1,
      truncated: false,
      truncation_notice: null,
      nodes: [
        {
          id: "n0",
          parent_id: null,
          timestamp: 0,
          depth: 0,
          is_root: true,
          is_leaf: true,
          out_degree: 0,
        },
      ],
      edges: [],
      stats: {},
    };
    render(<TreeView graph={graph} />);
    expect(
      screen.getByRole("img", { name: /Propagation tree for cascade single/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Node n0, depth 0/i })).toBeInTheDocument();
  });

  it("renders a deep chain and supports keyboard navigation and time scrubber", () => {
    const nodes: TreeNodePayload[] = [0, 1, 2, 3, 4].map((d) => ({
      id: `n${d}`,
      parent_id: d === 0 ? null : `n${d - 1}`,
      timestamp: d * 100,
      depth: d,
      is_root: d === 0,
      is_leaf: d === 4,
      out_degree: d === 4 ? 0 : 1,
    }));
    const graph: TreeGraphResponse = {
      cascade_id: "chain",
      early_window_seconds: 500,
      root_id: "n0",
      total_nodes: 5,
      total_edges: 4,
      returned_nodes: 5,
      truncated: false,
      truncation_notice: null,
      nodes,
      edges: [],
      stats: {},
    };
    render(<TreeView graph={graph} />);
    expect(screen.getByText(/5 \/ 5 node\(s\) · 4 edge\(s\)/i)).toBeInTheDocument();

    const n0 = screen.getByRole("button", { name: /Node n0, depth 0/i });
    const n1 = screen.getByRole("button", { name: /Node n1, depth 1/i });
    n0.focus();
    fireEvent.keyDown(n0, { key: "ArrowDown" });
    expect(document.activeElement).toBe(n1);
    fireEvent.keyDown(n1, { key: "ArrowUp" });
    expect(document.activeElement).toBe(n0);

    const scrubber = screen.getByLabelText(/Filter propagation tree by elapsed time/i);
    fireEvent.change(scrubber, { target: { value: "150" } });
    expect(screen.getByText(/2 \/ 5 node\(s\) · 4 edge\(s\)/i)).toBeInTheDocument();
  });

  it("caps and shows collapse notice when tree exceeds 500 nodes", () => {
    const nodes: TreeNodePayload[] = [
      {
        id: "n0",
        parent_id: null,
        timestamp: 0,
        depth: 0,
        is_root: true,
        is_leaf: false,
        out_degree: 520,
      },
    ];
    for (let i = 1; i <= 520; i++) {
      nodes.push({
        id: `n${i}`,
        parent_id: "n0",
        timestamp: i,
        depth: 1,
        is_root: false,
        is_leaf: true,
        out_degree: 0,
      });
    }
    const graph: TreeGraphResponse = {
      cascade_id: "huge",
      early_window_seconds: 3600,
      root_id: "n0",
      total_nodes: 521,
      total_edges: 520,
      returned_nodes: 521,
      truncated: false,
      truncation_notice: null,
      nodes,
      edges: [],
      stats: {},
    };
    render(<TreeView graph={graph} />);
    expect(screen.getByText(/Large tree auto-collapsed/i)).toBeInTheDocument();
  });
});
