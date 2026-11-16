import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Shell from "./components/Shell";
import { Loading } from "./components/ui";
import OverviewPage from "./pages/OverviewPage";
import EditionsPage from "./pages/EditionsPage";
import EditionPage from "./pages/EditionPage";

// heavier pages load on demand so the first paint stays fast
const CountryPage = lazy(() => import("./pages/CountriesPage").then((m) => ({ default: m.CountryPage })));
const AthletesPage = lazy(() => import("./pages/AthletesPage").then((m) => ({ default: m.AthletesPage })));
const AthletePage = lazy(() => import("./pages/AthletesPage").then((m) => ({ default: m.AthletePage })));
const SportsPage = lazy(() => import("./pages/SportsPage").then((m) => ({ default: m.SportsPage })));
const SportPage = lazy(() => import("./pages/SportsPage").then((m) => ({ default: m.SportPage })));
const ResultsPage = lazy(() => import("./pages/ResultsPage"));
const MedalsPage = lazy(() => import("./pages/MedalsPage"));
const StatisticsPage = lazy(() => import("./pages/StatisticsPage"));
const MachineLearningPage = lazy(() => import("./pages/MachineLearningPage"));
const TeamSportsPage = lazy(() => import("./pages/TeamSportsPage"));
const RecordsPage = lazy(() => import("./pages/RecordsPage"));
const EngineeringPage = lazy(() => import("./pages/EngineeringPage"));
const ComparePage = lazy(() => import("./pages/ComparePage"));
const CompareCountriesPage = lazy(() => import("./pages/CompareCountriesPage"));
const AssetReportPage = lazy(() => import("./pages/AssetReportPage"));
const VisualizationsPage = lazy(() => import("./pages/VisualizationsPage"));
const OlympicsHub = lazy(() => import("./pages/olympic/EventPages").then((m) => ({ default: m.OlympicsHub })));
const EditionEventsPage = lazy(() => import("./pages/olympic/EventPages").then((m) => ({ default: m.EditionEventsPage })));
const EventResultsPage = lazy(() => import("./pages/olympic/EventPages").then((m) => ({ default: m.EventResultsPage })));
const SubResultPage = lazy(() => import("./pages/olympic/EventPages").then((m) => ({ default: m.SubResultPage })));
const MedalsByCountryPage = lazy(() => import("./pages/olympic/MedalsCountryPages").then((m) => ({ default: m.MedalsByCountryPage })));
const CountriesVisualsPage = lazy(() => import("./pages/olympic/MedalsCountryPages").then((m) => ({ default: m.CountriesVisualsPage })));
const CountryEditionPage = lazy(() => import("./pages/olympic/MedalsCountryPages").then((m) => ({ default: m.CountryEditionPage })));
// the original crawler monitor (JS) is kept as-is
const CrawlerPage = lazy(() => import("./pages/legacy/CrawlerPage.jsx"));

/** An old address that moved: keeps its ?filters and does not leave an extra history entry. */
function RedirectKeepSearch({ to }: { to: string }) {
  const { search } = useLocation();
  return <Navigate replace to={`${to}${search}`} />;
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/summer" element={<EditionsPage season="summer" />} />
          <Route path="/winter" element={<EditionsPage season="winter" />} />
          <Route path="/edition/:gamesId" element={<EditionPage />} />
          <Route path="/olympics" element={<OlympicsHub />} />
          <Route path="/olympics/:season" element={<OlympicsHub />} />
          <Route path="/games/:gamesId" element={<EditionPage />} />
          <Route path="/games/:gamesId/results" element={<EditionEventsPage />} />
          <Route path="/games/:gamesId/sports/:sport" element={<EditionEventsPage />} />
          <Route path="/games/:gamesId/events/:eventId" element={<EventResultsPage />} />
          <Route path="/games/:gamesId/events/:eventId/matches/:matchId" element={<SubResultPage />} />
          <Route path="/games/:gamesId/events/:eventId/bouts/:boutId" element={<SubResultPage />} />
          <Route path="/games/:gamesId/events/:eventId/heats/:heatId" element={<SubResultPage />} />
          <Route path="/medals/countries" element={<RedirectKeepSearch to="/countries" />} />
          <Route path="/medals/editions/:gamesId" element={<MedalsByCountryPage />} />
          <Route path="/countries/:noc/editions/:gamesId" element={<CountryEditionPage />} />
          <Route path="/countries" element={<MedalsByCountryPage />} />
          <Route path="/countries/visuals" element={<CountriesVisualsPage />} />
          <Route path="/countries/:noc" element={<CountryPage />} />
          <Route path="/athletes" element={<AthletesPage />} />
          <Route path="/athletes/:id" element={<AthletePage />} />
          <Route path="/sports" element={<SportsPage />} />
          <Route path="/sports/:id" element={<SportPage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/medals" element={<MedalsPage />} />
          <Route path="/statistics" element={<StatisticsPage />} />
          <Route path="/machine-learning" element={<MachineLearningPage />} />
          <Route path="/team-sports" element={<TeamSportsPage />} />
          <Route path="/records" element={<RecordsPage />} />
          <Route path="/engineering" element={<EngineeringPage />} />
          <Route path="/visualizations" element={<VisualizationsPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/compare/countries" element={<CompareCountriesPage />} />
          <Route path="/assets" element={<AssetReportPage />} />
          <Route path="/crawler" element={<CrawlerPage />} />
          <Route path="*" element={<div className="p-10 text-center text-muted">Page not found.</div>} />
        </Route>
      </Routes>
    </Suspense>
  );
}
