import { useApi } from "../lib/api";
import { Async, ChartCard } from "../components/ui";
import { Bars, LineSeries } from "../charts/charts";
import { fmtPct } from "../lib/fmt";
import { EditionLogoWall, useEditionList } from "../components/editions/EditionGallery";
import { Snowflake, Sun } from "lucide-react";

/** Summer / Winter Olympics: every edition of the season (upcoming ones say Coming soon), then the season's charts, shown directly. */
export default function EditionsPage({ season }: { season: "summer" | "winter" }) {
  const q = useApi<any[]>("/games", { season });
  const { items } = useEditionList(season);
  const S = season === "summer" ? "Summer" : "Winter";
  const held = items.filter((i) => !i.upcoming);
  return (
    <div data-season={season}>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-line pb-3">
        <h1 className="h-display flex items-center gap-3 text-5xl leading-none">{season === "summer" ? <Sun className="h-9 w-9 text-accent" /> : <Snowflake className="h-9 w-9 text-accent" />}{S} Olympics</h1>
        <span className="text-sm text-muted">{held.length} editions · {held[0]?.year}–{held[held.length - 1]?.year}{items.length > held.length ? ` · ${items.length - held.length} coming soon` : ""}</span>
      </header>
      <EditionLogoWall items={[...items].reverse()} />
      <Async q={q}>{(rows) => {
        const data = rows.map((g) => ({ label: `${g.year}`, city: g.host_city, athletes: g.athletes, nocs: g.nocs, events: g.events, sports: g.sports, female_share: g.female_share }));
        return (
          <section className="mt-12" aria-labelledby="season-charts">
            <h2 id="season-charts" className="h-display mb-4 border-b border-line pb-2 text-3xl">{S} Games in numbers</h2>
            <div className="grid gap-4 xl:grid-cols-2">
              <ChartCard title="Athletes per edition"><Bars data={data} x="label" series={[{ key: "athletes", name: "Athletes", color: "var(--ed-primary)" }]} /></ChartCard>
              <ChartCard title="NOCs per edition"><Bars data={data} x="label" series={[{ key: "nocs", name: "NOCs", color: "#0085C7" }]} /></ChartCard>
              <ChartCard title="Events and sports"><LineSeries data={data} x="label" yLabel="Count" series={[{ key: "events", name: "Events", color: "#DF0024", dot: true }, { key: "sports", name: "Sports", color: "#009F3D", dot: true }]} /></ChartCard>
              <ChartCard title="Female share of athletes"><LineSeries data={data} x="label" yLabel="Female share" yFormat={(v) => fmtPct(v, 0)} series={[{ key: "female_share", name: "Women", color: "#E86AA6", dot: true }]} /></ChartCard>
            </div>
          </section>);
      }}</Async>
    </div>
  );
}

