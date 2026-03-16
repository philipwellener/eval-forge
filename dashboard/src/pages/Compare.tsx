import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,

  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from "recharts";
import { fetchCompare, fetchRuns, CompareData, EpisodeResult } from "../api/client";

const COLORS = ["#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

const chartTheme = {
  grid: "#1f2937",
  axis: "#6b7280",
  tooltip: { bg: "#111827", border: "#374151" },
};

function computeStats(results: EpisodeResult[]) {
  if (!results.length) return { successRate: null, avgTime: null, avgLatency: null, avgMem: null };
  const successRate = results.reduce((s, r) => s + r.success, 0) / results.length;
  const avgTime = results.reduce((s, r) => s + r.wall_clock_time, 0) / results.length;
  const avgLatency = results.reduce((s, r) => s + (r.inference_latency ?? 0), 0) / results.length;
  const avgMem = results.reduce((s, r) => s + (r.peak_memory_mb ?? 0), 0) / results.length;
  return { successRate, avgTime, avgLatency, avgMem };
}

export default function Compare() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const runIdsParam = searchParams.get("run_ids")?.split(",").filter(Boolean) ?? [];
  const [resolvedIds, setResolvedIds] = useState<string[]>(runIdsParam);

  // If no run_ids in URL, auto-load the most recent completed runs
  useEffect(() => {
    if (runIdsParam.length >= 2) {
      setResolvedIds(runIdsParam);
      return;
    }
    fetchRuns({ status: "completed" })
      .then((runs) => {
        const ids = runs.slice(0, 6).map((r) => r.id);
        setResolvedIds(ids);
      })
      .catch(() => setResolvedIds([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.toString()]);

  useEffect(() => {
    if (resolvedIds.length < 2) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchCompare(resolvedIds)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load comparison"))
      .finally(() => setLoading(false));
  }, [resolvedIds]);

  if (!loading && resolvedIds.length < 2) {
    return (
      <div className="py-16 text-center">
        <p className="text-gray-500">No completed runs to compare yet. Submit some evaluations first.</p>
      </div>
    );
  }

  if (loading) {
    return <div className="py-12 text-center text-gray-500 animate-pulse">Loading comparison...</div>;
  }

  if (error || !data) {
    return (
      <div className="rounded-md border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-300">
        {error ?? "No comparison data"}
      </div>
    );
  }

  const { runs, results } = data;

  // Compute stats from results
  const runStats = runs.map((run) => {
    const runResults = results[run.id] ?? [];
    const stats = computeStats(runResults);
    return { ...run, ...stats };
  });

  // Chart data
  const successData = runStats.map((r, i) => ({
    name: `${r.environment} (${r.policy_id.slice(0, 8)})`,
    success_rate: r.successRate != null ? +(r.successRate * 100).toFixed(1) : 0,
    fill: COLORS[i % COLORS.length],
  }));

  const timeData = runStats.map((r, i) => ({
    name: `${r.environment} (${r.policy_id.slice(0, 8)})`,
    avg_time: r.avgTime ?? 0,
    fill: COLORS[i % COLORS.length],
  }));

  const latencyData = runStats.map((r, i) => ({
    name: `${r.environment} (${r.policy_id.slice(0, 8)})`,
    avg_latency: (r.avgLatency ?? 0) * 1000,
    fill: COLORS[i % COLORS.length],
  }));

  // Find best values for highlighting — only consider runs with >0% success
  const viable = runStats.filter((r) => (r.successRate ?? 0) > 0);
  const bestSuccessRate = Math.max(...runStats.map((r) => r.successRate ?? -1));
  const completionTimes = viable.filter((r) => r.avgTime != null).map((r) => r.avgTime!);
  const bestCompletionTime = completionTimes.length ? Math.min(...completionTimes) : Infinity;
  const latencies = viable.filter((r) => r.avgLatency != null).map((r) => r.avgLatency!);
  const bestLatency = latencies.length ? Math.min(...latencies) : Infinity;
  const memories = viable.filter((r) => r.avgMem != null).map((r) => r.avgMem!);
  const bestMemory = memories.length ? Math.min(...memories) : Infinity;

  function winnerCls(val: number | null, best: number, successRate: number | null, lower = false) {
    if (val == null) return "";
    // Don't highlight metrics for runs with 0% success
    if (lower && (successRate ?? 0) === 0) return "";
    const isWinner = lower ? val <= best : val >= best;
    return isWinner ? "bg-emerald-900/40 text-emerald-300" : "";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-gray-100">
        Compare Runs <span className="text-gray-500">({runs.length})</span>
      </h1>

      {/* Charts row */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Success rate */}
        <div className="card">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Success Rate (%)
          </h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={successData}>
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="name" tick={{ fill: chartTheme.axis, fontSize: 10 }} />
              <YAxis domain={[0, 100]} tick={{ fill: chartTheme.axis, fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: chartTheme.tooltip.bg,
                  border: `1px solid ${chartTheme.tooltip.border}`,
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#e5e7eb",
                }}
                itemStyle={{ color: "#e5e7eb" }}
                labelStyle={{ color: "#9ca3af" }}
              />
              <Bar dataKey="success_rate" name="Success %" radius={[3, 3, 0, 0]}>
                {successData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Avg completion time */}
        <div className="card">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Avg Completion Time (s)
          </h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={timeData}>
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="name" tick={{ fill: chartTheme.axis, fontSize: 10 }} />
              <YAxis tick={{ fill: chartTheme.axis, fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: chartTheme.tooltip.bg,
                  border: `1px solid ${chartTheme.tooltip.border}`,
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#e5e7eb",
                }}
                itemStyle={{ color: "#e5e7eb" }}
                labelStyle={{ color: "#9ca3af" }}
              />
              <Bar dataKey="avg_time" name="Time (s)" radius={[3, 3, 0, 0]}>
                {timeData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Avg latency */}
        <div className="card">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Avg Inference Latency (ms)
          </h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={latencyData}>
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="name" tick={{ fill: chartTheme.axis, fontSize: 10 }} />
              <YAxis tick={{ fill: chartTheme.axis, fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: chartTheme.tooltip.bg,
                  border: `1px solid ${chartTheme.tooltip.border}`,
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#e5e7eb",
                }}
                itemStyle={{ color: "#e5e7eb" }}
                labelStyle={{ color: "#9ca3af" }}
              />
              <Bar dataKey="avg_latency" name="Latency (ms)" radius={[3, 3, 0, 0]}>
                {latencyData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Comparison table */}
      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="table-header">
              <th className="px-3 py-2 text-left">Policy</th>
              <th className="px-3 py-2 text-left">Environment</th>
              <th className="px-3 py-2 text-right">Success Rate</th>
              <th className="px-3 py-2 text-right">Avg Time (s)</th>
              <th className="px-3 py-2 text-right">Avg Latency (ms)</th>
              <th className="px-3 py-2 text-right">Avg Memory (MB)</th>
              <th className="px-3 py-2 text-right">Episodes</th>
            </tr>
          </thead>
          <tbody>
            {runStats.map((run, i) => (
              <tr key={run.id} className="table-row">
                <td className="px-3 py-2">
                  <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                  <span className="font-mono text-cyan-400">{run.policy_id.slice(0, 8)}</span>
                </td>
                <td className="px-3 py-2 text-gray-300">{run.environment}</td>
                <td className={`px-3 py-2 text-right font-mono ${winnerCls(run.successRate, bestSuccessRate, run.successRate)}`}>
                  {run.successRate != null ? `${(run.successRate * 100).toFixed(1)}%` : "\u2014"}
                </td>
                <td className={`px-3 py-2 text-right font-mono ${winnerCls(run.avgTime, bestCompletionTime, run.successRate, true)}`}>
                  {run.avgTime != null ? run.avgTime.toFixed(3) : "\u2014"}
                </td>
                <td className={`px-3 py-2 text-right font-mono ${winnerCls(run.avgLatency, bestLatency, run.successRate, true)}`}>
                  {run.avgLatency != null ? (run.avgLatency * 1000).toFixed(2) : "\u2014"}
                </td>
                <td className={`px-3 py-2 text-right font-mono ${winnerCls(run.avgMem, bestMemory, run.successRate, true)}`}>
                  {run.avgMem != null ? run.avgMem.toFixed(0) : "\u2014"}
                </td>
                <td className="px-3 py-2 text-right font-mono">{run.num_runs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
