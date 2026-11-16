export default function PlaceholderPage({ title, note }) {
  return (
    <div>
      <h1>{title}</h1>
      <p className="lead">{note}</p>
      <div className="panel">
        This page is wired to the live API shell. Domain tables populate as collectors and ETL
        phases land — the dashboard will not fabricate progress.
      </div>
    </div>
  );
}
