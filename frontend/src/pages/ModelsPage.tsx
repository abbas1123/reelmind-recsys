import { useQuery } from "@tanstack/react-query";
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
const VIZ = ["var(--viz-1)", "var(--viz-2)", "var(--viz-3)", "var(--viz-4)"];
const axisTick = { fill: "var(--viz-text-2)", fontSize: 11, fontFamily: "IBM Plex Mono, monospace" };

export default function ModelsPage() {
  const report = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation, retry: false });
  const eda = useQuery({ queryKey: ["eda"], queryFn: api.eda, retry: false });
  if (report.isLoading) return <CenterSpinner label="Loading evaluation report" />;
  if (report.error || !report.data) return <ErrorAlert error={report.error ?? "No report"} onRetry={() => report.refetch()} />;
  return <Report r={report.data} eda={eda.data} />;
}

function Figure({ n, kind = "Fig.", title, caption, aside, children }: {
  n: number;
  kind?: string;
  title: string;
  caption?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <figure className="flex flex-col gap-4 border-t border-rule pt-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <figcaption className="max-w-3xl">
          <span className="kicker">
            {kind} {n}
          </span>
          <h2 className="mt-1.5 font-display text-[28px] leading-tight tracking-[-0.01em]">{title}</h2>
          {caption && <p className="mt-1.5 text-[13.5px] leading-relaxed text-paper-3">{caption}</p>}
        </figcaption>
        {aside}
      </div>
      {children}
    </figure>
  );
}

function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string; payload: Record<string, unknown> }>;
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border border-rule-strong bg-ink-raised px-3 py-2 text-[12px] shadow-xl">
      <p className="mb-1 font-medium text-paper">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-2 font-mono text-[11px] text-paper-3">
          <span className="inline-block h-2 w-2" style={{ background: p.color }} />
          {p.name} <span className="text-paper tabular">{fmt(p.value)}</span>
          {Array.isArray(p.payload.ci) && (
            <span className="tabular">
              CI [{fmt((p.payload.ci as number[])[0])}, {fmt((p.payload.ci as number[])[1])}]
            </span>
          )}
        </p>
      ))}
    </div>
  );
}

const th = "kicker py-2.5 pr-4 text-left font-normal";
const td = "py-2.5 pr-4 font-mono text-[12.5px] tabular";

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
        return { model: name === selected ? `${name} ●` : name, value: v, ci, err: ci ? [v - ci[0], ci[1] - v] : [0, 0] };
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

  return (
    <div className="flex flex-col gap-14">
      <header className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <div>
          <p className="kicker">Evaluation report · generated {new Date(r.generated_at).toLocaleString("en-GB")}</p>
          <h1 className="mt-4 font-display text-[48px] leading-[0.92] tracking-[-0.02em] sm:text-[72px]">
            Which recommender <em className="text-amber">actually</em> works?
          </h1>
        </div>
        <p className="self-end border-l border-rule pl-5 text-[13.5px] leading-relaxed text-paper-2">
          Eleven models were tuned on a validation month and evaluated once on the following two years of MovieLens 1M (global
          temporal split, relevance = rating ≥ {r.protocol.relevance_threshold}). Every number on this page is read verbatim from{" "}
          <code className="font-mono text-[12px] text-paper">model_comparison.json</code> (seed {r.seed}, {(r.total_seconds / 60).toFixed(1)} min on CPU).
        </p>
      </header>

      {r.quick_mode && <Notice title="Quick mode">Only one configuration per model was tried. Run the full `recsys train`.</Notice>}

      <section className="grid grid-cols-2 border-y border-rule md:grid-cols-5" data-testid="stat-tiles">
        {[
          { k: "Selected model", v: selected, s: `by validation ${metric}` },
          { k: `Test ${metric}`, v: fmt(best.metrics[metric]), s: best.ci95?.[metric] ? `95% CI ${fmt(best.ci95[metric][0], 3)}–${fmt(best.ci95[metric][1], 3)}` : "" },
          { k: `vs ${runnerUp}`, v: `${lift >= 0 ? "+" : ""}${(lift * 100).toFixed(1)}%`, s: "relative test lift" },
          { k: "vs popularity", v: pop ? `+${((best.metrics[metric] / pop - 1) * 100).toFixed(1)}%` : "—", s: "the baseline to beat" },
          { k: "Warm test users", v: r.protocol.tasks.test_warm.toLocaleString(), s: `${r.dataset.n_interactions.toLocaleString()} ratings total` },
        ].map((s, i) => (
          <div key={s.k} className={`py-5 pr-4 ${i > 0 ? "md:border-l md:border-rule md:pl-5" : ""} ${i % 2 === 1 ? "border-l border-rule pl-4 md:pl-5" : ""}`}>
            <p className="kicker">{s.k}</p>
            <p className="mt-2 font-display text-[34px] leading-none tabular">{s.v}</p>
            <p className="mt-1.5 font-mono text-[10.5px] text-paper-3">{s.s}</p>
          </div>
        ))}
      </section>

      <Figure
        n={1}
        title={`Test ${metric}, warm users`}
        caption={`Sorted by the validation score used for model selection; whiskers are 95% bootstrap intervals over ${r.protocol.tasks.test_warm.toLocaleString()} users. ● marks the selected model.`}
      >
        <div className="h-[440px] w-full" data-testid="ndcg-chart">
          <ResponsiveContainer>
            <BarChart data={barData} layout="vertical" margin={{ left: 8, right: 32, top: 4, bottom: 4 }} barCategoryGap={7}>
              <CartesianGrid horizontal={false} stroke="var(--viz-grid)" />
              <XAxis type="number" tick={axisTick} stroke="var(--viz-grid)" tickLine={false} />
              <YAxis type="category" dataKey="model" tick={axisTick} width={140} stroke="var(--viz-grid)" tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--viz-grid)", opacity: 0.5 }} />
              <Bar dataKey="value" name={`test ${metric}`} fill="var(--viz-1)" radius={[0, 2, 2, 0]} maxBarSize={20}>
                <ErrorBar dataKey="err" width={5} stroke="var(--viz-text-2)" strokeWidth={1} direction="x" />
                <LabelList dataKey="value" position="insideLeft" offset={8} formatter={(v: unknown) => fmt(Number(v), 3)} fill="var(--viz-surface)" fontSize={10.5} fontFamily="IBM Plex Mono, monospace" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Figure>

      <Figure
        n={2}
        title={`Cold start: ${metric} as ratings arrive`}
        caption={
          <>
            Users with no training history; their first <em>n</em> real ratings are revealed and the rest predicted. {coldUsers} users in this split
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
        <div className="h-[320px] w-full" data-testid="cold-chart">
          <ResponsiveContainer>
            <LineChart data={coldData} margin={{ left: 0, right: 24, top: 4, bottom: 16 }}>
              <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
              <XAxis
                dataKey="n"
                type="number"
                domain={[0, "dataMax"]}
                ticks={coldData.map((d) => d.n)}
                tick={axisTick}
                stroke="var(--viz-grid)"
                tickLine={false}
                label={{ value: "ratings revealed", position: "insideBottom", offset: -10, fill: "var(--viz-text-2)", fontSize: 11 }}
              />
              <YAxis tick={axisTick} stroke="var(--viz-grid)" width={44} tickLine={false} />
              <Tooltip content={<ChartTooltip />} labelFormatter={(n) => `${n} ratings revealed`} />
              <Legend verticalAlign="top" height={30} iconType="plainline" formatter={(v: string) => <span style={{ color: "var(--viz-text-2)", fontSize: 12 }}>{v}</span>} />
              {coldModels.map((m, i) => (
                <Line
                  key={m}
                  type="linear"
                  dataKey={m}
                  name={m}
                  stroke={VIZ[i]}
                  strokeWidth={2}
                  dot={{ r: 4, strokeWidth: 2, fill: VIZ[i], stroke: "var(--viz-surface)" }}
                  activeDot={{ r: 6, fill: VIZ[i], stroke: "var(--viz-surface)", strokeWidth: 2 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Figure>

      <Figure n={1} kind="Table" title="All ranking metrics, test split" caption={`Beyond-accuracy columns use top-${k0} lists. Novelty = mean −log₂ of an item's popularity share.`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px]" data-testid="metrics-table">
            <thead className="border-b border-rule-strong">
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
                  <tr key={name} className={`border-b border-rule ${sel ? "bg-amber/[0.07]" : ""}`} data-testid={`row-${name}`}>
                    <td className="py-2.5 pr-4 text-[13.5px] font-medium">
                      {sel && <span className="mr-2 text-amber">●</span>}
                      {name}
                    </td>
                    <td className="py-2.5 pr-4 text-[12.5px] text-paper-3">{e.family}</td>
                    <td className={`${td} text-paper-2`}>{fmt(e.val?.metrics[metric])}</td>
                    <td className={`${td} ${sel ? "text-amber" : "text-paper"}`} data-testid={`test-${name}`}>
                      {fmt(t.metrics[metric])}
                    </td>
                    <td className={`${td} text-paper-3`}>{ci ? `${fmt(ci[0], 3)}–${fmt(ci[1], 3)}` : "—"}</td>
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
      </Figure>

      <div className="grid gap-14 lg:grid-cols-2">
        <Figure n={2} kind="Table" title="Rating prediction" caption="Explicit models are tuned on validation RMSE. Lower RMSE does not mean better top-N ranking — compare with Table 1.">
          <table className="w-full">
            <thead className="border-b border-rule-strong">
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
                    <tr key={n} className="border-b border-rule">
                      <td className="py-2.5 pr-4 text-[13.5px] font-medium">{n}</td>
                      <td className={td}>{fmt(rt.val.rmse)}</td>
                      <td className={td}>{fmt(rt.test.rmse)}</td>
                      <td className={td}>{fmt(rt.test.mae)}</td>
                      <td className={td}>{fmt(rt.test.rmse_warm)}</td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </Figure>

        <Figure
          n={3}
          kind="Table"
          title="Hybrid weights"
          caption={
            <>
              s = w<sub>cf</sub>·{hybridParams?.cf} + w<sub>cb</sub>·{hybridParams?.cb} + w<sub>pop</sub>·trending, min–max normalised per user and switched by
              history length. Tuned on validation.
            </>
          }
        >
          <table className="w-full">
            <thead className="border-b border-rule-strong">
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
                  <tr key={b} className="border-b border-rule">
                    <td className="py-2.5 pr-4 text-[13.5px] font-medium">{b}</td>
                    <td className={`${td} text-paper-3`}>{b === "cold" ? "0" : b === "light" ? "1–4" : "≥ 5"}</td>
                    {(["cf", "cb", "pop"] as const).map((c) => (
                      <td key={c} className={td}>
                        <span className="inline-flex items-center gap-2">
                          <span className="inline-block h-1.5 bg-amber" style={{ width: `${w[c] * 48}px` }} aria-hidden />
                          {w[c].toFixed(1)}
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
          </table>
        </Figure>
      </div>

      <Figure n={4} kind="Table" title="Robustness: per-user temporal split" caption="An optimistic protocol (other users' future ratings leak into training). Shown for comparison only and never used for selection.">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px]">
            <thead className="border-b border-rule-strong">
              <tr>
                <th className={th}>Model</th>
                <th className={th}>{metric}</th>
                <th className={th}>recall@{kmax}</th>
                <th className={th}>Users</th>
              </tr>
            </thead>
            <tbody>
              {order.map((n) => (
                <tr key={n} className="border-b border-rule">
                  <td className="py-2.5 pr-4 text-[13.5px] font-medium">{n}</td>
                  <td className={td}>{fmt(models[n].secondary_test?.metrics[metric])}</td>
                  <td className={td}>{fmt(models[n].secondary_test?.metrics[`recall@${kmax}`])}</td>
                  <td className={`${td} text-paper-3`}>{models[n].secondary_test?.n_users.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Figure>

      {eda && (
        <Figure
          n={3}
          title="The dataset"
          caption={`${eda.n_interactions.toLocaleString()} ratings from ${eda.n_users.toLocaleString()} users on ${eda.n_items_catalog.toLocaleString()} films (${eda.n_items_unrated} never rated) · sparsity ${(eda.sparsity * 100).toFixed(2)}% · mean ${eda.rating_mean.toFixed(2)} · ${(eda.positive_share * 100).toFixed(1)}% of ratings ≥ 4 · popularity Gini ${eda.item_popularity_gini.toFixed(3)} · ${eda.time_range.min} → ${eda.time_range.max}`}
        >
          <div className="grid gap-px border border-rule bg-rule md:grid-cols-2">
            {eda.charts.map((c) => (
              <img key={c} src={`/api/model/eda/charts/${c}.png`} alt={`EDA chart: ${c.replaceAll("_", " ")}`} className="w-full bg-[#fcfcfb]" loading="lazy" />
            ))}
          </div>
        </Figure>
      )}

      <section className="border-t border-rule pt-5">
        <p className="kicker">Limitations</p>
        <ol className="mt-4 grid gap-x-12 gap-y-4 md:grid-cols-2" lang="az">
          {r.limitations.map((l, i) => (
            <li key={l} className="grid grid-cols-[2rem_1fr] text-[13.5px] leading-relaxed text-paper-2">
              <span className="font-mono text-[11px] text-paper-3">{String(i + 1).padStart(2, "0")}</span>
              {l}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
