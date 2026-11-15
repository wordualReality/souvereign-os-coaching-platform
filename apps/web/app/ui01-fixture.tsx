"use client";

import { useEffect, useRef, useState } from "react";

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
  const [message, setMessage] = useState("");
  const [mediaUrl, setMediaUrl] = useState("");
  const retry = useRef<{ body: string; key: string } | null>(null);
  const mediaRetry = useRef<{ url: string; title: string; key: string } | null>(null);
  const mediaWithdrawKey = useRef<string | null>(null);

  const progressKeys = useRef<Partial<Record<"complete" | "share" | "revoke", string>>>({});

  useEffect(() => {
    const controller = new AbortController();
    fetch(endpoint, { signal: controller.signal })
      .then(async response => { if (response.ok) setFixture(await response.json()); })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  async function run(operation: "assign" | "open" | "send" | "list" | "complete" | "share" | "revoke" | "own" | "released"
    | "attach-media" | "view-media" | "withdraw-media") {
    setPending(true);
    setResult(null);
    try {
      const messaging = operation === "send" || operation === "list";
      if (operation === "send" && retry.current?.body !== message) {
        retry.current = { body: message, key: crypto.randomUUID() };
      }
      const progress = ["complete", "share", "revoke", "own", "released"].includes(operation);
      const media = operation === "attach-media" || operation === "view-media" || operation === "withdraw-media";
      if (operation === "attach-media" && mediaRetry.current?.url !== mediaUrl) {
        mediaRetry.current = { url: mediaUrl, title: "Synthetic test media", key: crypto.randomUUID() };
      }
      if (operation === "withdraw-media") mediaWithdrawKey.current ??= crypto.randomUUID();
      const roleRoute = endpoint + (action === "assign" ? "/coach" : "/client");
      const route = media ? roleRoute + "/media" : progress ? roleRoute + "/progress" : messaging ? roleRoute : endpoint;
      let body: string = operation;
      if (operation === "send") body = JSON.stringify(retry.current);
      if (operation === "view-media") body = "list";
      if (operation === "attach-media") body = JSON.stringify(mediaRetry.current);
      if (operation === "withdraw-media") body = JSON.stringify({ operation: "withdraw", key: mediaWithdrawKey.current });
      if (operation === "complete" || operation === "share" || operation === "revoke") {
        const key = progressKeys.current[operation] ??= crypto.randomUUID();
        body = JSON.stringify({ operation, key });
      }
      const response = await fetch(route, { method: "POST", body });
      setResult({ ...await response.json(), status: response.status });
      if (response.ok && operation === "revoke") delete progressKeys.current.share;
      if (response.ok && operation === "share") delete progressKeys.current.revoke;
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
      <button type="button" onClick={() => run(action)} disabled={pending}>
        {action === "assign" ? "Assign published test Journey" : "Open assigned step"}
      </button>
      <p><a href={action === "assign" ? "/client/member-home" : "/coach/journeys"}>
        {action === "assign" ? "Go to test client" : "Go to test coach"}
      </a></p>
      <p><label>Step message <input value={message} maxLength={500} onChange={event => {
        retry.current = null;
        setMessage(event.target.value);
      }} /></label></p>
      <button type="button" onClick={() => run("send")} disabled={pending || !message.trim()}>
        Send step message
      </button>
      <button type="button" onClick={() => run("list")} disabled={pending}>View step messages</button>
      {action === "assign" ? (
        <p><label>Step media URL <input data-media-url value={mediaUrl} maxLength={2048} onChange={event => {
          mediaRetry.current = null;
          setMediaUrl(event.target.value);
        }} /></label></p>
      ) : null}
      {action === "assign" ? (
        <button type="button" onClick={() => run("attach-media")} disabled={pending || !mediaUrl.trim()}>
          Attach step media link
        </button>
      ) : null}
      <button type="button" onClick={() => run("view-media")} disabled={pending}>View step media link</button>
      {action === "assign" ? (
        <button type="button" onClick={() => run("withdraw-media")} disabled={pending}>Withdraw step media link</button>
      ) : null}
      {action === "open" ? (
        <fieldset>
          <legend>Step completion and sharing</legend>
          <button type="button" onClick={() => run("complete")} disabled={pending}>Complete step</button>
          <button type="button" onClick={() => run("own")} disabled={pending}>View my step progress</button>
          <button type="button" onClick={() => run("share")} disabled={pending}>Share completed status with assigned coach</button>
          <button type="button" onClick={() => run("revoke")} disabled={pending}>Withdraw progress sharing</button>
        </fieldset>
      ) : (
        <button type="button" onClick={() => run("released")} disabled={pending}>View released step progress</button>
      )}
      <div aria-live="polite">
        {result && <p role="status">HTTP {result.status}{result.error && " " + result.error.code}</p>}
        {result?.data && <pre>{JSON.stringify(result.data, null, 2)}</pre>}
      </div>
    </section>
  );
}
