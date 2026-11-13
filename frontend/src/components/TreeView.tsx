import { hierarchy, tree as d3Tree } from "d3-hierarchy";
import { Maximize2, Minus, Plus } from "lucide-react";
import {
  memo,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import type { TreeGraphResponse, TreeNodePayload } from "../api/client";
import { formatDuration, formatSecondsClock } from "../lib/format";
import { Button } from "./ui/Button";

interface TreeViewProps {
  graph: TreeGraphResponse;
}

interface HierarchyDatum {
  id: string;
  payload: TreeNodePayload | null;
  children: HierarchyDatum[];
}

interface PositionedNode {
  x: number;
  y: number;
  payload: TreeNodePayload;
}

interface PositionedLink {
  key: string;
  sourceId: string;
  targetId: string;
  sourceColor: string;
  targetColor: string;
  sx: number;
  sy: number;
  tx: number;
  ty: number;
  targetTime: number;
}

const MAX_RENDER_NODES = 500;

function nodeColor(payload: TreeNodePayload): string {
  if (payload.is_root) return "#22D3EE";
  if (payload.is_leaf) return "#38BDF8";
  return "#4F8CFF";
}

function buildHierarchyInput(
  nodes: TreeNodePayload[],
  maxRenderNodes: number
): { rootData: HierarchyDatum | null; collapsedCount: number; maxRenderedDepth: number } {
  if (nodes.length === 0) {
    return { rootData: null, collapsedCount: 0, maxRenderedDepth: 0 };
  }

  let selected = nodes;
  let maxDepthObserved = nodes.reduce((m, n) => Math.max(m, n.depth), 0);
  if (nodes.length > maxRenderNodes) {
    for (let dCap = maxDepthObserved; dCap >= 1; dCap--) {
      const filtered = nodes.filter((n) => n.depth <= dCap);
      if (filtered.length <= maxRenderNodes || dCap === 1) {
        selected = filtered.slice(0, maxRenderNodes);
        maxDepthObserved = dCap;
        break;
      }
    }
  }

  const collapsedCount = Math.max(0, nodes.length - selected.length);
  const byId = new Map<string, HierarchyDatum>();
  for (const n of selected) {
    byId.set(n.id, { id: n.id, payload: n, children: [] });
  }

  const topRoots: HierarchyDatum[] = [];
  for (const n of selected) {
    const datum = byId.get(n.id);
    if (!datum) continue;
    if (n.parent_id && byId.has(n.parent_id)) {
      byId.get(n.parent_id)?.children.push(datum);
    } else {
      topRoots.push(datum);
    }
  }

  if (topRoots.length === 1) {
    return { rootData: topRoots[0], collapsedCount, maxRenderedDepth: maxDepthObserved };
  }

  return {
    rootData: { id: "__forest_super_root__", payload: null, children: topRoots },
    collapsedCount,
    maxRenderedDepth: maxDepthObserved,
  };
}

interface TreeCanvasProps {
  cascadeId: string;
  width: number;
  height: number;
  nodes: PositionedNode[];
  links: PositionedLink[];
  depthLevels: { depth: number; y: number }[];
  scrubberTime: number;
  pan: { x: number; y: number };
  zoom: number;
  highlightIds: Set<string> | null;
  highlightLinks: Set<string> | null;
  selectedNodeId: string | null;
  onHoverNode: (node: TreeNodePayload | null) => void;
  onSelectNode: (node: TreeNodePayload) => void;
  onNodeKeyDown: (e: KeyboardEvent<SVGGElement>, node: TreeNodePayload) => void;
  registerNodeRef: (id: string, el: SVGGElement | null) => void;
}

const TreeSvgCanvas = memo(function TreeSvgCanvas({
  cascadeId,
  width,
  height,
  nodes,
  links,
  depthLevels,
  scrubberTime,
  pan,
  zoom,
  highlightIds,
  highlightLinks,
  selectedNodeId,
  onHoverNode,
  onSelectNode,
  onNodeKeyDown,
  registerNodeRef,
}: TreeCanvasProps) {
  const uid = useId().replace(/:/g, "");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-full w-full select-none"
      role="img"
      aria-label={`Propagation tree for cascade ${cascadeId}`}
    >
      <defs>
        {links.map((l) => (
          <linearGradient
            key={`g-${l.key}`}
            id={`${uid}-${l.key}`}
            x1="0%"
            y1="0%"
            x2="0%"
            y2="100%"
          >
            <stop offset="0%" stopColor={l.sourceColor} />
            <stop offset="100%" stopColor={l.targetColor} />
          </linearGradient>
        ))}
      </defs>

      <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
        {/* Depth horizontal guide bands */}
        {depthLevels.map(({ depth, y }) => (
          <g key={`d-${depth}`} aria-hidden="true">
            <line
              x1={16}
              y1={y}
              x2={width - 16}
              y2={y}
              stroke="rgba(148, 163, 255, 0.07)"
              strokeDasharray="3 5"
              strokeWidth={1}
            />
            <text
              x={14}
              y={y - 6}
              fill="#7D8BB0"
              className="font-mono"
              style={{ fontSize: "10px" }}
            >
              D{depth}
            </text>
          </g>
        ))}

        {/* Smooth cubic Bezier edges */}
        {links.map((link) => {
          if (link.targetTime > scrubberTime) return null;
          const isPath = highlightLinks ? highlightLinks.has(link.key) : false;
          const dimmed = highlightLinks !== null && !isPath;
          const midY = (link.sy + link.ty) / 2;

          return (
            <path
              key={link.key}
              d={`M ${link.sx} ${link.sy} C ${link.sx} ${midY}, ${link.tx} ${midY}, ${link.tx} ${link.ty}`}
              fill="none"
              stroke={isPath ? "#22D3EE" : `url(#${uid}-${link.key})`}
              strokeWidth={isPath ? 2.25 : 1.25}
              strokeOpacity={dimmed ? 0.14 : isPath ? 0.95 : 0.55}
              className="transition-opacity duration-150"
            />
          );
        })}

        {/* Nodes */}
        {nodes.map(({ x, y, payload }) => {
          if (payload.timestamp > scrubberTime) return null;
          const isHighlighted = highlightIds ? highlightIds.has(payload.id) : false;
          const dimmed = highlightIds !== null && !isHighlighted;
          const isSelected = selectedNodeId === payload.id;
          const r = payload.is_root ? 8.5 : payload.is_leaf ? 4 : 5.5;
          const fill = nodeColor(payload);
          const fillOpacity = payload.is_root ? 1 : payload.is_leaf ? 0.72 : 0.85;

          return (
            <g
              key={payload.id}
              ref={(el) => registerNodeRef(payload.id, el)}
              transform={`translate(${x}, ${y})`}
              tabIndex={0}
              role="button"
              aria-label={`Node ${payload.id}, depth ${payload.depth}, time ${payload.timestamp}s, ${payload.out_degree} children`}
              aria-pressed={isSelected}
              onMouseEnter={() => onHoverNode(payload)}
              onMouseLeave={() => onHoverNode(null)}
              onFocus={() => onHoverNode(payload)}
              onBlur={() => onHoverNode(null)}
              onClick={(e) => {
                e.stopPropagation();
                onSelectNode(payload);
              }}
              onKeyDown={(e) => onNodeKeyDown(e, payload)}
              className="cursor-pointer focus:outline-none"
              style={{ opacity: dimmed ? 0.2 : 1 }}
            >
              {payload.is_root && (
                <circle
                  r={13}
                  fill="none"
                  stroke="#22D3EE"
                  strokeWidth={1.5}
                  className="animate-root-pulse"
                />
              )}
              {(isHighlighted || isSelected) && !payload.is_root && (
                <circle r={r + 4} fill="none" stroke="#22D3EE" strokeWidth={1.5} strokeOpacity={0.9} />
              )}
              <circle
                r={r}
                fill={fill}
                fillOpacity={fillOpacity}
                stroke="#070B16"
                strokeWidth={1.5}
                className="animate-node-pop"
              />
            </g>
          );
        })}
      </g>
    </svg>
  );
});

export function TreeView({ graph }: TreeViewProps) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState<{ x: number; y: number } | null>(null);
  const [hovered, setHovered] = useState<TreeNodePayload | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const windowMax = Math.max(1, graph.early_window_seconds);
  const [scrubberTime, setScrubberTime] = useState(windowMax);

  const nodeRefs = useRef(new Map<string, SVGGElement>());
  const registerNodeRef = useCallback((id: string, el: SVGGElement | null) => {
    if (el) nodeRefs.current.set(id, el);
    else nodeRefs.current.delete(id);
  }, []);

  useEffect(() => {
    setScrubberTime(Math.max(1, graph.early_window_seconds));
    setSelectedId(null);
    setHovered(null);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, [graph.cascade_id, graph.early_window_seconds]);

  const layout = useMemo(() => {
    const { rootData, collapsedCount, maxRenderedDepth } = buildHierarchyInput(
      graph.nodes,
      MAX_RENDER_NODES
    );
    if (!rootData) {
      return {
        nodes: [] as PositionedNode[],
        links: [] as PositionedLink[],
        depthLevels: [] as { depth: number; y: number }[],
        width: 720,
        height: 440,
        collapsedCount,
        maxRenderedDepth,
        parentMap: new Map<string, string | null>(),
        childrenMap: new Map<string, string[]>(),
        siblingsMap: new Map<string, string[]>(),
        nodeById: new Map<string, TreeNodePayload>(),
      };
    }

    const root = hierarchy(rootData);
    const leafCount = Math.max(1, root.leaves().length);
    const depthCount = Math.max(1, root.height);
    const width = Math.max(700, leafCount * 42 + 96);
    const height = Math.max(420, depthCount * 86 + 110);

    const treeLayout = d3Tree<HierarchyDatum>().size([width - 96, height - 100]);
    const laidOut = treeLayout(root);

    const visibleNodes: PositionedNode[] = [];
    const nodeById = new Map<string, TreeNodePayload>();
    const parentMap = new Map<string, string | null>();
    const childrenMap = new Map<string, string[]>();
    const byDepth = new Map<number, string[]>();
    const depthY = new Map<number, number>();

    for (const d of laidOut.descendants()) {
      if (!d.data.payload) continue;
      const p = d.data.payload;
      const px = d.x + 48;
      const py = d.y + 48;
      visibleNodes.push({ x: px, y: py, payload: p });
      nodeById.set(p.id, p);
      parentMap.set(p.id, p.parent_id);
      if (p.parent_id) {
        const list = childrenMap.get(p.parent_id) ?? [];
        list.push(p.id);
        childrenMap.set(p.parent_id, list);
      }
      const dList = byDepth.get(p.depth) ?? [];
      dList.push(p.id);
      byDepth.set(p.depth, dList);
      if (!depthY.has(p.depth)) depthY.set(p.depth, py);
    }

    const siblingsMap = new Map<string, string[]>();
    for (const ids of byDepth.values()) {
      for (const id of ids) siblingsMap.set(id, ids);
    }

    const depthLevels = Array.from(depthY.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([depth, y]) => ({ depth, y }));

    const visibleLinks: PositionedLink[] = laidOut
      .links()
      .filter((l) => l.source.data.payload !== null && l.target.data.payload !== null)
      .map((l) => {
        const src = l.source.data.payload as TreeNodePayload;
        const tgt = l.target.data.payload as TreeNodePayload;
        return {
          key: `${src.id}__${tgt.id}`,
          sourceId: src.id,
          targetId: tgt.id,
          sourceColor: nodeColor(src),
          targetColor: nodeColor(tgt),
          sx: l.source.x + 48,
          sy: l.source.y + 48,
          tx: l.target.x + 48,
          ty: l.target.y + 48,
          targetTime: tgt.timestamp,
        };
      });

    return {
      nodes: visibleNodes,
      links: visibleLinks,
      depthLevels,
      width,
      height,
      collapsedCount,
      maxRenderedDepth,
      parentMap,
      childrenMap,
      siblingsMap,
      nodeById,
    };
  }, [graph.nodes]);

  const activePathTargetId = selectedId ?? hovered?.id ?? null;

  const { highlightIds, highlightLinks } = useMemo(() => {
    if (!activePathTargetId) {
      return { highlightIds: null, highlightLinks: null };
    }
    const ids = new Set<string>();
    const edges = new Set<string>();
    let curr: string | null | undefined = activePathTargetId;
    let guard = 0;
    while (curr && guard < 1000) {
      ids.add(curr);
      const parentId = layout.parentMap.get(curr);
      if (parentId) {
        edges.add(`${parentId}__${curr}`);
      }
      curr = parentId;
      guard++;
    }
    return { highlightIds: ids, highlightLinks: edges };
  }, [activePathTargetId, layout.parentMap]);

  const focusNode = useCallback((id: string | null | undefined) => {
    if (!id) return;
    const el = nodeRefs.current.get(id);
    if (el) el.focus();
  }, []);

  const handleNodeKeyDown = useCallback(
    (e: KeyboardEvent<SVGGElement>, node: TreeNodePayload) => {
      if (e.key === "ArrowUp") {
        e.preventDefault();
        focusNode(layout.parentMap.get(node.id));
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        const children = layout.childrenMap.get(node.id);
        focusNode(children?.[0]);
      } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        const siblings = layout.siblingsMap.get(node.id) ?? [];
        const idx = siblings.indexOf(node.id);
        if (idx >= 0 && siblings.length > 1) {
          const nextIdx =
            e.key === "ArrowRight"
              ? (idx + 1) % siblings.length
              : (idx - 1 + siblings.length) % siblings.length;
          focusNode(siblings[nextIdx]);
        }
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setSelectedId((prev) => (prev === node.id ? null : node.id));
      } else if (e.key === "Escape") {
        e.preventDefault();
        setSelectedId(null);
        setHovered(null);
      }
    },
    [focusNode, layout.childrenMap, layout.parentMap, layout.siblingsMap]
  );

  const handleSelectNode = useCallback((node: TreeNodePayload) => {
    setSelectedId((prev) => (prev === node.id ? null : node.id));
  }, []);

  const fitToView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const visibleCount = layout.nodes.filter((n) => n.payload.timestamp <= scrubberTime).length;
  const activeTooltipNode = hovered ?? (selectedId ? layout.nodeById.get(selectedId) ?? null : null);

  return (
    <div className="panel-surface flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-subtle px-5 py-3.5">
        <div>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-2">
            Early Propagation Tree ({formatDuration(graph.early_window_seconds)} window)
          </h2>
          <p className="mt-0.5 font-mono text-xs text-text-3 tabular-nums">
            {visibleCount} / {graph.total_nodes} node(s) · {graph.total_edges} edge(s)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="mr-2 hidden items-center gap-3 text-[11px] text-text-2 sm:flex">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-accent-2 ring-2 ring-accent-2/30" /> Root
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-accent" /> Internal
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-calm/80" /> Leaf
            </span>
          </div>

          <Button
            type="button"
            variant="icon"
            size="icon"
            aria-label="Zoom out"
            onClick={() => setZoom((z) => Math.max(0.35, Number((z - 0.15).toFixed(2))))}
          >
            <Minus className="h-3.5 w-3.5" strokeWidth={1.5} />
          </Button>
          <Button
            type="button"
            variant="icon"
            size="icon"
            aria-label="Zoom in"
            onClick={() => setZoom((z) => Math.min(3, Number((z + 0.15).toFixed(2))))}
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={1.5} />
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            aria-label="Fit tree to view"
            onClick={fitToView}
            className="h-8 px-2.5 text-xs"
          >
            <Maximize2 className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
            <span className="hidden sm:inline">Fit</span>
          </Button>
        </div>
      </div>

      {/* Subtle inline large-tree notice */}
      {(graph.truncated || layout.collapsedCount > 0) && (
        <div
          role="note"
          className="border-b border-subtle bg-bg-2/60 px-5 py-2 text-xs text-text-2"
        >
          {graph.truncation_notice
            ? graph.truncation_notice
            : `Large tree auto-collapsed at depth ${layout.maxRenderedDepth}: displaying ${layout.nodes.length} of ${graph.nodes.length} nodes (>${MAX_RENDER_NODES} node cap).`}
        </div>
      )}

      {/* Interactive SVG Viewport */}
      <div
        className="relative h-[440px] w-full cursor-grab active:cursor-grabbing bg-bg-0/75"
        onMouseDown={(e) => setDragging({ x: e.clientX - pan.x, y: e.clientY - pan.y })}
        onMouseMove={(e) => {
          if (dragging) {
            setPan({ x: e.clientX - dragging.x, y: e.clientY - dragging.y });
          }
        }}
        onMouseUp={() => setDragging(null)}
        onMouseLeave={() => setDragging(null)}
        onClick={() => setSelectedId(null)}
        onWheel={(e) => {
          e.preventDefault();
          const delta = e.deltaY < 0 ? 0.1 : -0.1;
          setZoom((z) => Math.max(0.35, Math.min(3, Number((z + delta).toFixed(2)))));
        }}
      >
        {layout.nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-text-3">
            No nodes observed in the early window.
          </div>
        ) : (
          <TreeSvgCanvas
            cascadeId={graph.cascade_id}
            width={layout.width}
            height={layout.height}
            nodes={layout.nodes}
            links={layout.links}
            depthLevels={layout.depthLevels}
            scrubberTime={scrubberTime}
            pan={pan}
            zoom={zoom}
            highlightIds={highlightIds}
            highlightLinks={highlightLinks}
            selectedNodeId={selectedId}
            onHoverNode={setHovered}
            onSelectNode={handleSelectNode}
            onNodeKeyDown={handleNodeKeyDown}
            registerNodeRef={registerNodeRef}
          />
        )}

        {/* Glass node tooltip */}
        {activeTooltipNode && (
          <div
            role="tooltip"
            className="glass-surface pointer-events-none absolute top-3 left-3 rounded-xl px-3.5 py-2.5 text-xs"
          >
            <p className="font-mono font-medium text-accent-2">Node {activeTooltipNode.id}</p>
            <p className="mt-1 font-mono text-[11px] text-text-2 tabular-nums">
              Depth D{activeTooltipNode.depth} · {formatDuration(activeTooltipNode.timestamp)} ·{" "}
              {activeTooltipNode.out_degree} child(ren)
            </p>
          </div>
        )}

        {/* Cheap SVG minimap */}
        {layout.nodes.length > 1 && (
          <div
            aria-hidden="true"
            className="glass-surface pointer-events-none absolute right-3 bottom-3 hidden rounded-xl p-1.5 sm:block"
          >
            <svg
              viewBox={`0 0 ${layout.width} ${layout.height}`}
              className="h-14 w-24 opacity-85"
            >
              {layout.nodes.map(({ x, y, payload }) => (
                <circle
                  key={`mm-${payload.id}`}
                  cx={x}
                  cy={y}
                  r={Math.max(4, layout.width / 110)}
                  fill={nodeColor(payload)}
                  fillOpacity={payload.timestamp <= scrubberTime ? 0.85 : 0.15}
                />
              ))}
            </svg>
          </div>
        )}
      </div>

      {/* Early-window time scrubber */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-subtle bg-bg-1/90 px-5 py-3">
        <label
          htmlFor="early-window-scrubber"
          className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-2"
        >
          Early-Window Scrubber
        </label>
        <input
          id="early-window-scrubber"
          type="range"
          min={0}
          max={windowMax}
          step={Math.max(1, Math.round(windowMax / 120))}
          value={scrubberTime}
          onChange={(e) => setScrubberTime(Number(e.target.value))}
          aria-label="Filter propagation tree by elapsed time"
          className="h-1.5 flex-1 min-w-[140px] cursor-pointer accent-[#4F8CFF]"
        />
        <span className="font-mono text-xs text-text-2 tabular-nums">
          t = {formatSecondsClock(scrubberTime)} / {formatSecondsClock(windowMax)}
        </span>
      </div>
    </div>
  );
}
