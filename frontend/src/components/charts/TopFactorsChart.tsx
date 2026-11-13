import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FeatureFactor } from "../../api/client";

interface TopFactorsChartProps {
  factors: FeatureFactor[];
}

export default function TopFactorsChart({ factors }: TopFactorsChartProps) {
  const maxAbs = Math.max(
    0.01,
    ...factors.map((f) => Math.abs(f.contribution_score))
  );

  return (
    <div className="h-52 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={factors}
          layout="vertical"
          margin={{ top: 4, right: 12, left: 4, bottom: 4 }}
        >
          <XAxis
            type="number"
            domain={[-maxAbs, maxAbs]}
            tick={{ fill: "#7D8BB0", fontSize: 11, fontFamily: "JetBrains Mono Variable" }}
            axisLine={{ stroke: "#7D8BB0", strokeWidth: 1 }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="feature"
            width={126}
            tick={{ fill: "#9AA6C7", fontSize: 11, fontFamily: "JetBrains Mono Variable" }}
            axisLine={false}
            tickLine={false}
          />
          <ReferenceLine x={0} stroke="rgba(148, 163, 255, 0.25)" strokeWidth={1} />
          <Tooltip
            cursor={{ fill: "rgba(79, 140, 255, 0.08)" }}
            contentStyle={{
              backgroundColor: "rgba(12, 19, 36, 0.92)",
              backdropFilter: "blur(10px)",
              border: "1px solid rgba(148, 163, 255, 0.18)",
              borderRadius: "12px",
              color: "#E6EBFF",
              fontSize: "12px",
              fontFamily: "JetBrains Mono Variable",
            }}
          />
          <Bar dataKey="contribution_score" radius={[4, 4, 4, 4]} animationDuration={600}>
            {factors.map((f) => (
              <Cell
                key={f.feature}
                fill={
                  f.direction === "increases_virality"
                    ? "#F59E0B"
                    : f.direction === "decreases_virality"
                      ? "#38BDF8"
                      : "#7D8BB0"
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
