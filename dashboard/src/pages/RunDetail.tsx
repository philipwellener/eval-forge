import { useEffect, useState, useMemo } from "react";
import { useParams } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { fetchRun, fetchResults, Run, EpisodeResult } from "../api/client";

type SortKey = "episode_index" | "success" | "wall_clock_time" | "inference_latency" | "peak_memory_mb";
type SortDir = "asc" | "desc";

function StatCard({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="card flex flex-col gap-1">
      <span className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</span>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-bold text-gray-100">{value}</span>
        {unit && <span className="text-sm text-gray-500">{unit}</span>}
      </div>
    </div>
  );
}

const chartTheme = {
  grid: "#1f2937",
  axis: "#6b7280",
  tooltip: { bg: "#111827", border: "#374151" },
};

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [results, setResults] = useState<EpisodeResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("episode_index");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([fetchRun(id), fetchResults(id)])
      .then(([r, res]) => {
        setRun(r);
        setResults(res);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [id]);

  const sorted = useMemo(() => {
    const copy = [...results];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [results, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " \u25b2" : " \u25bc";
  };

  if (loading) {
    return <div className="py-12 text-center text-gray-500 animate-pulse">Loading run details...</div>;
  }

  if (error || !run) {
    return (
      <div className="rounded-md border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-300">
        {error ?? "Run not found"}
      </div>
    );
  }

  const successRate = run.success_rate != null ? (run.success_rate * 100).toFixed(1) : "\u2014";
  const avgTime = run.avg_completion_time != null ? run.avg_completion_time.toFixed(3) : "\u2014";
  const avgLatency = results.length > 0
    ? (results.reduce((s, r) => s + (r.inference_latency ?? 0), 0) / results.length * 1000).toFixed(2)
    : "\u2014";
  const avgMem = results.length > 0
    ? (results.reduce((s, r) => s + (r.peak_memory_mb ?? 0), 0) / results.length).toFixed(0)
    : "\u2014";

  const chartData = results
    .slice()
    .sort((a, b) => a.episode_index - b.episode_index)
    .map((r) => ({
      name: `E${r.episode_index}`,
      wall_clock_time: r.wall_clock_time,
      inference_latency: r.inference_latency != null ? r.inference_latency * 1000 : 0,
    }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-lg font-semibold text-gray-100">
          <span className="font-mono text-cyan-400">{run.policy_id.slice(0, 8)}</span>
          <span className="mx-2 text-gray-600">/</span>
          <span className="text-gray-300">{run.environment}</span>
        </h1>
        <p className="mt-1 text-xs text-gray-500">Run ID: {run.id}</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Total Episodes" value={String(run.num_runs)} />
        <StatCard label="Success Rate" value={successRate} unit="%" />
        <StatCard label="Avg Completion" value={avgTime} unit="s" />
        <StatCard label="Avg Latency" value={avgLatency} unit="ms" />
        <StatCard label="Avg Memory" value={avgMem} unit="MB" />
      </div>

      {/* Charts */}
      {chartData.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Completion time chart */}
          <div className="card">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Completion Time per Episode
            </h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
                <XAxis dataKey="name" tick={{ fill: chartTheme.axis, fontSize: 11 }} />
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
                <Bar dataKey="wall_clock_time" name="Time (s)" fill="#06b6d4" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Inference latency chart */}
          <div className="card">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Inference Latency per Episode
            </h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
                <XAxis dataKey="name" tick={{ fill: chartTheme.axis, fontSize: 11 }} />
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
                <Bar dataKey="inference_latency" name="Latency (ms)" fill="#10b981" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Results table */}
      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="table-header">
              <th className="cursor-pointer px-3 py-2 text-left" onClick={() => handleSort("episode_index")}>
                Episode{sortIndicator("episode_index")}
              </th>
              <th className="cursor-pointer px-3 py-2 text-left" onClick={() => handleSort("success")}>
                Result{sortIndicator("success")}
              </th>
              <th className="cursor-pointer px-3 py-2 text-right" onClick={() => handleSort("wall_clock_time")}>
                Time (s){sortIndicator("wall_clock_time")}
              </th>
              <th className="cursor-pointer px-3 py-2 text-right" onClick={() => handleSort("inference_latency")}>
                Latency (ms){sortIndicator("inference_latency")}
              </th>
              <th className="cursor-pointer px-3 py-2 text-right" onClick={() => handleSort("peak_memory_mb")}>
                Memory (MB){sortIndicator("peak_memory_mb")}
              </th>
              <th className="px-3 py-2 text-right">Steps</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.id} className="table-row">
                <td className="px-3 py-2 font-mono text-gray-300">{r.episode_index}</td>
                <td className="px-3 py-2">
                  {r.success ? (
                    <span className="badge badge-completed">pass</span>
                  ) : (
                    <span className="badge badge-failed">fail</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right font-mono">{r.wall_clock_time.toFixed(3)}</td>
                <td className="px-3 py-2 text-right font-mono">
                  {r.inference_latency != null ? (r.inference_latency * 1000).toFixed(2) : "\u2014"}
                </td>
                <td className="px-3 py-2 text-right font-mono">
                  {r.peak_memory_mb != null ? r.peak_memory_mb.toFixed(0) : "\u2014"}
                </td>
                <td className="px-3 py-2 text-right font-mono text-gray-400">{r.steps}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
