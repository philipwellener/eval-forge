import { useEffect, useState, useCallback, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchRuns, Run } from "../api/client";

const STATUS_OPTIONS = ["", "pending", "running", "completed", "failed"] as const;

function statusBadge(status: Run["status"]) {
  const cls: Record<string, string> = {
    pending: "badge badge-pending",
    running: "badge badge-running",
    completed: "badge badge-completed",
    failed: "badge badge-failed",
  };
  return <span className={cls[status] ?? "badge"}>{status}</span>;
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function RunsList() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [envFilter, setEnvFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchRuns({
        environment: envFilter || undefined,
        status: statusFilter || undefined,
      });
      setRuns(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load runs");
    } finally {
      setLoading(false);
    }
  }, [envFilter, statusFilter]);

  // Initial load + filter changes
  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  // Auto-poll when active runs exist
  useEffect(() => {
    const hasActive = runs.some((r) => r.status === "pending" || r.status === "running");
    if (hasActive) {
      intervalRef.current = setInterval(load, 5000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [runs, load]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === runs.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(runs.map((r) => r.id)));
    }
  };

  const environments = ["reach", "pick_place", "cluttered"];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-100">Evaluation Runs</h1>
        <button
          className="btn-primary"
          disabled={selected.size < 2}
          onClick={() => {
            const ids = [...selected].join(",");
            navigate(`/compare?run_ids=${ids}`);
          }}
        >
          Compare selected ({selected.size})
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <select
          className="select-input"
          value={envFilter}
          onChange={(e) => setEnvFilter(e.target.value)}
        >
          <option value="">All environments</option>
          {environments.map((env) => (
            <option key={env} value={env}>
              {env}
            </option>
          ))}
        </select>

        <select
          className="select-input"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.filter(Boolean).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        {loading && (
          <span className="text-xs text-gray-500 animate-pulse">Loading...</span>
        )}
      </div>

      {error && (
        <div className="rounded-md border border-red-800 bg-red-900/30 px-4 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="table-header">
              <th className="px-3 py-2 text-left">
                <input
                  type="checkbox"
                  checked={runs.length > 0 && selected.size === runs.length}
                  onChange={toggleAll}
                  className="accent-cyan-500"
                />
              </th>
              <th className="px-3 py-2 text-left">Policy ID</th>
              <th className="px-3 py-2 text-left">Environment</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-right">Success Rate</th>
              <th className="px-3 py-2 text-right">Episodes</th>
              <th className="px-3 py-2 text-left">Submitted</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} className="table-row">
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(run.id)}
                    onChange={() => toggleSelect(run.id)}
                    className="accent-cyan-500"
                  />
                </td>
                <td className="px-3 py-2">
                  <Link
                    to={`/runs/${run.id}`}
                    className="font-mono text-cyan-400 hover:text-cyan-300 hover:underline"
                  >
                    {run.policy_id}
                  </Link>
                </td>
                <td className="px-3 py-2 text-gray-300">{run.environment}</td>
                <td className="px-3 py-2">{statusBadge(run.status)}</td>
                <td className="px-3 py-2 text-right font-mono">
                  {run.success_rate != null ? `${(run.success_rate * 100).toFixed(1)}%` : "\u2014"}
                </td>
                <td className="px-3 py-2 text-right font-mono">{run.num_runs}</td>
                <td className="px-3 py-2 text-gray-400">{fmtTime(run.submitted_at)}</td>
              </tr>
            ))}
            {!loading && runs.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-gray-500">
                  No runs found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
