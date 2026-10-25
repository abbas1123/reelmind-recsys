import { useQuery } from "@tanstack/react-query";
import { Award, Database, Gauge, TrendingUp, Users } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { EdaSummary, EvaluationReport, ModelEntry } from "../api/types";
import { Segmented } from "../components/Controls";
import { CenterSpinner, ErrorAlert, Notice } from "../components/Feedback";

const fmt = (v: number | null | undefined, d = 4) => (v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(d));
const signedPct = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1)}%`;
const VIZ = ["var(--viz-1)", "var(--viz-2)", "var(--viz-3)", "var(--viz-4)"];
const axisTick = { fill: "var(--viz-text-2)", fontSize: 12 };

export default function ModelsPage() {
  const report = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation, retry: false });
  const eda = useQuery({ queryKey: ["eda"], queryFn: api.eda, retry: false });
  if (report.isLoading) return <CenterSpinner label="Loading evaluation report" />;
  if (report.error || !report.data) return <ErrorAlert error={report.error ?? "No report"} onRetry={() => report.refetch()} />;
  return <Report r={report.data} eda={eda.data} />;
}

function Card({ title, caption, aside, children, className = "" }: {
  title: string;
  caption?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`flex flex-col gap-5 rounded-3xl bg-surface-1 p-5 ring-1 ring-line sm:p-7 ${className}`} aria-label={title}>
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-3xl">
          <h2 className="text-lg font-bold tracking-tight">{title}</h2>
          {caption && <p className="mt-1 text-sm leading-relaxed text-text-3">{caption}</p>}
        </div>
        {aside}
      </header>
      {children}
    </section>
  );
}

function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string; payload: Record<string, unknown> }>;
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl bg-surface-3 px-3 py-2 text-xs shadow-2xl ring-1 ring-line-strong">
      <p className="mb-1 font-semibold text-text">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-2 text-text-2">
          <span className="inline-block size-2 rounded-full" style={{ background: p.color }} />
          {p.name} <span className="font-semibold text-text tabular">{fmt(p.value)}</span>
          {Array.isArray(p.payload.ci) && (
            <span className="tabular text-text-3">
              CI [{fmt((p.payload.ci as number[])[0])}, {fmt((p.payload.ci as number[])[1])}]
            </span>
          )}
        </p>
      ))}
    </div>
  );
}

const th = "py-3 pr-4 text-left text-xs font-semibold uppercase tracking-wider text-text-3";
const td = "py-3 pr-4 text-sm tabular";

function Report({ r, eda }: { r: EvaluationReport; eda: EdaSummary | undefined }) {
  const metric = r.protocol.primary_metric;
  const k0 = Math.min(...r.protocol.k_values);
  const kmax = Math.max(...r.protocol.k_values);
  const order = r.selection.ranking.map((x) => String(x.model));
  const models = r.models;
  const selected = r.selection.selected;
  const [coldSplit, setColdSplit] = useState<"test" | "val">("test");
  const hybridParams = models.hybrid?.best_params as { cf?: string; cb?: string; weights?: Record<string, Record<string, number>> } | undefined;

  const barData = useMemo(
    () =>
      order.map((name) => {
        const t = models[name].test!;
        const ci = t.ci95?.[metric];
        const v = t.metrics[metric];
        return { model: name === selected ? `${name} ★` : name, value: v, ci, err: ci ? [v - ci[0], ci[1] - v] : [0, 0] };
      }),
    [order, models, metric, selected],
  );

  const coldModels = ["hybrid", "popularity", hybridParams?.cf, hybridParams?.cb].filter((m): m is string => !!m && !!models[m]);
  const coldKey = coldSplit === "test" ? "test_cold" : "val_cold";
  const coldTasks = Object.keys(models.hybrid?.[coldKey] ?? {}).sort((a, b) => Number(a.split("n").pop()) - Number(b.split("n").pop()));
  const coldData = coldTasks.map((task) => {
    const row: Record<string, number> = { n: Number(task.split("n").pop()) };
    coldModels.forEach((m) => {
      const v = (models[m][coldKey] as Record<string, { metrics: Record<string, number> }> | undefined)?.[task]?.metrics[metric];
      if (v !== undefined) row[m] = v;
    });
    return row;
  });
  const coldUsers = coldTasks.length ? r.protocol.tasks[coldTasks[0]] : 0;
  const best = models[selected].test!;
  const runnerUp = order.find((n) => n !== selected);
  const lift = runnerUp ? best.metrics[metric] / models[runnerUp].test!.metrics[metric] - 1 : 0;
  const pop = models.popularity?.test?.metrics[metric];

  const kpis = [
    { k: "Selected model", v: selected, s: `by validation ${metric}`, icon: Award },
    { k: `Test ${metric}`, v: fmt(best.metrics[metric]), s: best.ci95?.[metric] ? `95% CI ${fmt(best.ci95[metric][0], 3)}–${fmt(best.ci95[metric][1], 3)}` : "", icon: Gauge },
    { k: `vs ${runnerUp}`, v: signedPct(lift), s: "relative test lift", icon: TrendingUp },
    { k: "vs popularity", v: pop ? signedPct(best.metrics[metric] / pop - 1) : "—", s: "the baseline to beat", icon: TrendingUp },
    { k: "Warm test users", v: r.protocol.tasks.test_warm.toLocaleString(), s: `${r.dataset.n_interactions.toLocaleString()} ratings`, icon: Users },
  ];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <p className="text-sm font-semibold text-brand">Insights · model evaluation</p>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-5xl">How well does it recommend?</h1>
        <p className="max-w-3xl text-text-2">
          Eleven models tuned on a validation month and evaluated once on the following two years of MovieLens 1M (global temporal
          split, relevant = rating ≥ {r.protocol.relevance_threshold}). Every number is read from{" "}
          <code className="rounded bg-surface-2 px-1.5 py-0.5 text-[13px] text-text">model_comparison.json</code> — seed {r.seed},{" "}
          {(r.total_seconds / 60).toFixed(1)} min on CPU, generated {new Date(r.generated_at).toLocaleString("en-GB")}.
        </p>
      </header>

      {r.quick_mode && <Notice title="Quick mode">Only one configuration per model was tried. Run the full `recsys train`.</Notice>}

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" data-testid="stat-tiles" aria-label="Key figures">
        {kpis.map(({ k, v, s, icon: Icon }, i) => (
          <div key={k} className={`relative overflow-hidden rounded-3xl p-5 ring-1 ring-line ${i === 0 ? "bg-brand text-white ring-0" : "bg-surface-1"}`}>
            <Icon className={`size-5 ${i === 0 ? "text-white/80" : "text-text-3"}`} aria-hidden />
            <p className={`mt-4 text-xs font-semibold uppercase tracking-wider ${i === 0 ? "text-white/80" : "text-text-3"}`}>{k}</p>
            <p className="mt-1 truncate text-3xl font-extrabold tracking-tight tabular">{v}</p>
            <p className={`mt-1 text-xs ${i === 0 ? "text-white/80" : "text-text-3"}`}>{s}</p>
          </div>
        ))}
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <Card
          title={`Test ${metric} by model`}
          caption={`Warm users (${r.protocol.tasks.test_warm.toLocaleString()}), sorted by the validation score used for selection. Whiskers: 95% bootstrap CI. ★ = selected.`}
        >
          <div className="h-[440px] w-full" data-testid="ndcg-chart">
            <ResponsiveContainer>
              <BarChart data={barData} layout="vertical" margin={{ left: 0, right: 24, top: 4, bottom: 4 }} barCategoryGap={8}>
                <CartesianGrid horizontal={false} stroke="var(--viz-grid)" />
                <XAxis type="number" tick={axisTick} stroke="var(--viz-grid)" tickLine={false} />
                <YAxis type="category" dataKey="model" tick={axisTick} width={136} stroke="var(--viz-grid)" tickLine={false} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--viz-grid)", opacity: 0.5 }} />
                <Bar dataKey="value" name={`test ${metric}`} fill="var(--viz-1)" radius={[0, 6, 6, 0]} maxBarSize={22}>
                  <ErrorBar dataKey="err" width={5} stroke="var(--viz-text-2)" strokeWidth={1} direction="x" />
                  <LabelList dataKey="value" position="insideLeft" offset={10} formatter={(v: unknown) => fmt(Number(v), 3)} fill="#ffffff" fontSize={11} fontWeight={600} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title={`Cold start: ${metric} as ratings arrive`}
          caption={
            <>
              New users; their first <em>n</em> real ratings are revealed and the rest predicted. {coldUsers} users
              {coldSplit === "test" ? " — small, so differences are noisy." : " — used to tune the hybrid, so its line is optimistic."}
            </>
          }
          aside={
            <Segmented
              label="Cold-start split"
              size="sm"
              value={coldSplit}
              onChange={setColdSplit}
              options={[
                { value: "test", label: "Test" },
                { value: "val", label: "Validation" },
              ]}
            />
          }
        >
          <div className="h-[380px] w-full" data-testid="cold-chart">
            <ResponsiveContainer>
              <LineChart data={coldData} margin={{ left: 0, right: 16, top: 4, bottom: 18 }}>
                <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
                <XAxis
                  dataKey="n"
                  type="number"
                  domain={[0, "dataMax"]}
                  ticks={coldData.map((d) => d.n)}
                  tick={axisTick}
                  stroke="var(--viz-grid)"
                  tickLine={false}
                  label={{ value: "ratings revealed", position: "insideBottom", offset: -12, fill: "var(--viz-text-2)", fontSize: 12 }}
                />
                <YAxis tick={axisTick} stroke="var(--viz-grid)" width={44} tickLine={false} />
                <Tooltip content={<ChartTooltip />} labelFormatter={(n) => `${n} ratings revealed`} />
                <Legend verticalAlign="top" height={32} iconType="circle" formatter={(v: string) => <span style={{ color: "var(--viz-text-2)", fontSize: 12 }}>{v}</span>} />
                {coldModels.map((m, i) => (
                  <Line
                    key={m}
                    type="monotone"
                    dataKey={m}
                    name={m}
                    stroke={VIZ[i]}
                    strokeWidth={2.5}
                    dot={{ r: 4, strokeWidth: 2, fill: VIZ[i], stroke: "var(--viz-surface)" }}
                    activeDot={{ r: 6, fill: VIZ[i], stroke: "var(--viz-surface)", strokeWidth: 2 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card title="All ranking metrics · test split" caption={`Beyond-accuracy columns use top-${k0} lists. Novelty = mean −log₂ of an item's popularity share.`}>
        <div className="-mx-5 overflow-x-auto px-5 sm:-mx-7 sm:px-7">
          <table className="w-full min-w-[960px]" data-testid="metrics-table">
            <thead className="border-b border-line">
              <tr>
                {["Model", "Family", `val ${metric}`, `test ${metric}`, "95% CI", `P@${k0}`, `R@${kmax}`, `MAP@${k0}`, `HR@${k0}`, `Cov@${k0}`, `ILD@${k0}`, `Nov@${k0}`].map((h) => (
                  <th key={h} className={th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {order.map((name) => {
                const e: ModelEntry = models[name];
                const t = e.test!;
                const ci = t.ci95?.[metric];
                const sel = name === selected;
                return (
                  <tr key={name} className={`border-b border-line last:border-0 ${sel ? "bg-white/[0.04]" : ""}`} data-testid={`row-${name}`}>
                    <td className="py-3 pr-4 text-sm font-semibold">
                      {name}
                      {sel && <span className="ml-2 rounded-full bg-brand px-2 py-0.5 text-[10px] font-bold uppercase text-white">selected</span>}
                    </td>
                    <td className="py-3 pr-4 text-sm text-text-3">{e.family}</td>
                    <td className={`${td} text-text-2`}>{fmt(e.val?.metrics[metric])}</td>
                    <td className={`${td} font-bold ${sel ? "text-brand" : ""}`} data-testid={`test-${name}`}>
                      {fmt(t.metrics[metric])}
                    </td>
                    <td className={`${td} text-text-3`}>{ci ? `${fmt(ci[0], 3)}–${fmt(ci[1], 3)}` : "—"}</td>
                    <td className={td}>{fmt(t.metrics[`precision@${k0}`])}</td>
                    <td className={td}>{fmt(t.metrics[`recall@${kmax}`])}</td>
                    <td className={td}>{fmt(t.metrics[`map@${k0}`])}</td>
                    <td className={td}>{fmt(t.metrics[`hit_rate@${k0}`])}</td>
                    <td className={td}>{fmt(t.beyond[`coverage@${k0}`], 3)}</td>
                    <td className={td}>{fmt(t.beyond[`ild@${k0}`], 3)}</td>
                    <td className={td}>{fmt(t.beyond[`novelty@${k0}`], 2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Rating prediction" caption="Explicit models are tuned on validation RMSE. Lower RMSE does not mean better top-N ranking.">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[440px]">
              <thead className="border-b border-line">
                <tr>
                  <th className={th}>Model</th>
                  <th className={th}>val RMSE</th>
                  <th className={th}>test RMSE</th>
                  <th className={th}>test MAE</th>
                  <th className={th}>RMSE warm</th>
                </tr>
              </thead>
              <tbody>
                {order
                  .filter((n) => models[n].rating)
                  .map((n) => {
                    const rt = models[n].rating!;
                    return (
                      <tr key={n} className="border-b border-line last:border-0">
                        <td className="py-3 pr-4 text-sm font-semibold">{n}</td>
                        <td className={td}>{fmt(rt.val.rmse)}</td>
                        <td className={td}>{fmt(rt.test.rmse)}</td>
                        <td className={td}>{fmt(rt.test.mae)}</td>
                        <td className={td}>{fmt(rt.test.rmse_warm)}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </Card>

        <Card
          title="Hybrid weights"
          caption={
            <>
              w<sub>cf</sub>·{hybridParams?.cf} + w<sub>cb</sub>·{hybridParams?.cb} + w<sub>pop</sub>·trending, min–max normalised per user and switched by history length.
            </>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[440px]">
              <thead className="border-b border-line">
                <tr>
                  <th className={th}>Bucket</th>
                  <th className={th}>History</th>
                  <th className={th}>w_cf</th>
                  <th className={th}>w_cb</th>
                  <th className={th}>w_pop</th>
                </tr>
              </thead>
              <tbody>
                {hybridParams?.weights &&
                  Object.entries(hybridParams.weights).map(([b, w]) => (
                    <tr key={b} className="border-b border-line last:border-0">
                      <td className="py-3 pr-4 text-sm font-semibold capitalize">{b}</td>
                      <td className={`${td} text-text-3`}>{b === "cold" ? "0" : b === "light" ? "1–4" : "≥ 5"}</td>
                      {(["cf", "cb", "pop"] as const).map((c, i) => (
                        <td key={c} className={td}>
                          <span className="inline-flex items-center gap-2">
                            <span className="inline-block h-2 rounded-full" style={{ width: `${Math.max(w[c] * 56, 2)}px`, background: VIZ[i] }} aria-hidden />
                            {w[c].toFixed(1)}
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card title="Robustness: per-user temporal split" caption="An optimistic protocol (other users' future ratings leak into training). Shown for comparison only; never used for selection.">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px]">
            <thead className="border-b border-line">
              <tr>
                <th className={th}>Model</th>
                <th className={th}>{metric}</th>
                <th className={th}>recall@{kmax}</th>
                <th className={th}>Users</th>
              </tr>
            </thead>
            <tbody>
              {order.map((n) => (
                <tr key={n} className="border-b border-line last:border-0">
                  <td className="py-3 pr-4 text-sm font-semibold">{n}</td>
                  <td className={td}>{fmt(models[n].secondary_test?.metrics[metric])}</td>
                  <td className={td}>{fmt(models[n].secondary_test?.metrics[`recall@${kmax}`])}</td>
                  <td className={`${td} text-text-3`}>{models[n].secondary_test?.n_users.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {eda && (
        <Card
          title="The dataset"
          caption={`${eda.n_interactions.toLocaleString()} ratings from ${eda.n_users.toLocaleString()} users on ${eda.n_items_catalog.toLocaleString()} films (${eda.n_items_unrated} never rated) · sparsity ${(eda.sparsity * 100).toFixed(2)}% · mean ${eda.rating_mean.toFixed(2)} · ${(eda.positive_share * 100).toFixed(1)}% of ratings ≥ 4 · popularity Gini ${eda.item_popularity_gini.toFixed(3)} · ${eda.time_range.min} → ${eda.time_range.max}`}
          aside={<Database className="size-5 text-text-3" aria-hidden />}
        >
          <div className="grid gap-3 md:grid-cols-2">
            {eda.charts.map((c) => (
              <img key={c} src={`/api/model/eda/charts/${c}.png`} alt={`EDA chart: ${c.replaceAll("_", " ")}`} className="w-full rounded-2xl bg-[#fcfcfb]" loading="lazy" />
            ))}
          </div>
        </Card>
      )}

      <Card title="Limitations">
        <ol className="grid gap-x-10 gap-y-3 md:grid-cols-2" lang="az">
          {r.limitations.map((l, i) => (
            <li key={l} className="flex gap-3 text-sm leading-relaxed text-text-2">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-3 text-xs font-bold text-text">{i + 1}</span>
              {l}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
