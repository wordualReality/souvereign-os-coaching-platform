"use client";

import { useEffect, useState } from "react";

const endpoint = "/api/arcava-ui01";

type Fixture = { journey_version_id: string; client_id: string };
type Result = {
  status: number;
  error?: { code: string };
  data?: { assignment_id?: string; journey_version_id: string; status?: string;
    title?: string; step_id?: string; source_ref?: Record<string, unknown> };
};

export function Ui01Fixture({ action }: { action: "assign" | "open" }) {
  const [fixture, setFixture] = useState<Fixture | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch(endpoint, { signal: controller.signal })
      .then(async response => { if (response.ok) setFixture(await response.json()); })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  async function run() {
    setPending(true);
    setResult(null);
    try {
      const response = await fetch(endpoint, { method: "POST", body: action });
      setResult({ ...await response.json(), status: response.status });
    } catch {
      setResult({ status: 503, error: { code: "FIXTURE_UNAVAILABLE" } });
    } finally {
      setPending(false);
    }
  }

  if (!fixture) return null;
  return (
    <section aria-label="Synthetic local journey fixture">
      <h2>Synthetic local PA-05 fixture</h2>
      <p>Published journey version: {fixture.journey_version_id}</p>
      <p>Test client: {fixture.client_id}</p>
      <button type="button" onClick={run} disabled={pending}>
        {action === "assign" ? "Assign published test Journey" : "Open assigned step"}
      </button>
      <p><a href={action === "assign" ? "/client/member-home" : "/coach/journeys"}>
        {action === "assign" ? "Go to test client" : "Go to test coach"}
      </a></p>
      <div aria-live="polite">
        {result && <p role="status">HTTP {result.status}{result.error && " " + result.error.code}</p>}
        {result?.data && <pre>{JSON.stringify(result.data, null, 2)}</pre>}
      </div>
    </section>
  );
}
