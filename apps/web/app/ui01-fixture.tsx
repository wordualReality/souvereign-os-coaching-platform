"use client";

import { useEffect, useRef, useState } from "react";

const endpoint = "/api/arcava-ui01";
const LOOPBACK_PROFILE = "TEST_LOOPBACK_ONLY";
const MEDIA_RIGHTS = "SYNTHETIC_TEST_ONLY";
const MEDIA_USE = "EXTERNAL_NAVIGATION_ONLY";
const PA05_STEP_ID = "66666666-6666-4666-8666-666666666666";
const STEP_STORAGE_KEY = "arcava-ui01-assigned-step";
const EXPECTED_SOURCE = {
  schema_version: 1,
  variant: "KDB_PROTOCOL_VERSION",
  protocol_id: "05000000-0000-4000-8000-000000000009",
  protocol_version_id: "05000000-0000-4000-8000-000000000010",
  owning_module_id: "05000000-0000-4000-8000-000000000013",
  taxonomy_version_id: "05000000-0000-4000-8000-000000000014",
} as const;
const MEDIA_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "youtu.be",
  "skool.com",
  "www.skool.com",
]);

type Fixture = { journey_version_id: string; client_id: string };
type SourceRef = {
  schema_version: number;
  variant: string;
  protocol_id: string;
  protocol_version_id: string;
  owning_module_id: string;
  taxonomy_version_id: string;
  relation_ids: unknown[];
};
type AssignedStep = {
  journey_version_id: string;
  step_id: string;
  title: string;
  source_ref: SourceRef;
  profile: string;
};
type Result = {
  status: number;
  error?: { code: string };
  data?: {
    assignment_id?: string;
    journey_version_id: string;
    status?: string;
    title?: string;
    step_id?: string;
    source_ref?: Record<string, unknown>;
    profile?: string;
    media_link?: {
      url?: string;
      title?: string;
      rights_state?: string;
      use?: string;
      visibility?: string;
    };
  };
};

function sameSource(value: unknown): value is SourceRef {
  if (!value || typeof value !== "object") return false;
  const source = value as SourceRef;
  return source.schema_version === EXPECTED_SOURCE.schema_version
    && source.variant === EXPECTED_SOURCE.variant
    && source.protocol_id === EXPECTED_SOURCE.protocol_id
    && source.protocol_version_id === EXPECTED_SOURCE.protocol_version_id
    && source.owning_module_id === EXPECTED_SOURCE.owning_module_id
    && source.taxonomy_version_id === EXPECTED_SOURCE.taxonomy_version_id
    && Array.isArray(source.relation_ids)
    && source.relation_ids.length === 0;
}

function allowlistedMediaUrl(raw: unknown): string | null {
  if (typeof raw !== "string" || raw.length < 12 || raw.length > 2048) return null;
  for (let i = 0; i < raw.length; i++) {
    const c = raw.charCodeAt(i);
    if (c <= 0x20 || raw[i] === "\\" || raw[i] === "<" || raw[i] === ">" || raw[i] === '"' || raw[i] === "'") {
      return null;
    }
  }
  if (raw.includes("@")) return null;
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  if (parsed.username || parsed.password) return null;
  if (parsed.port) return null;
  const host = parsed.hostname;
  if (host !== host.toLowerCase() || !MEDIA_HOSTS.has(host)) return null;
  if ([...host].every(ch => ch === "." || (ch >= "0" && ch <= "9"))) return null;
  const prefix = "https://" + host;
  if (!raw.startsWith(prefix)) return null;
  if (raw.length > prefix.length) {
    const next = raw.charAt(prefix.length);
    if (next !== "/" && next !== "?" && next !== "#") return null;
  }
  return raw;
}

function clickableMediaHref(data: Result["data"], versionId: string | undefined): string | null {
  if (!data || !versionId) return null;
  const media = data.media_link;
  if (!media) return null;
  if (data.journey_version_id !== versionId) return null;
  if (data.step_id !== PA05_STEP_ID) return null;
  if (data.profile !== LOOPBACK_PROFILE || !sameSource(data.source_ref)) return null;
  if (media.rights_state !== MEDIA_RIGHTS) return null;
  if (media.use !== MEDIA_USE) return null;
  if (media.visibility !== "ACTIVE") return null;
  return allowlistedMediaUrl(media.url);
}

function readStoredStep(versionId: string | undefined): AssignedStep | null {
  if (!versionId || typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STEP_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AssignedStep;
    if (parsed.journey_version_id !== versionId) return null;
    if (parsed.step_id !== PA05_STEP_ID || parsed.profile !== LOOPBACK_PROFILE) return null;
    if (!parsed.title || !sameSource(parsed.source_ref)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function storeStep(step: AssignedStep | null) {
  if (typeof sessionStorage === "undefined") return;
  if (!step) sessionStorage.removeItem(STEP_STORAGE_KEY);
  else sessionStorage.setItem(STEP_STORAGE_KEY, JSON.stringify(step));
}

export function Ui01Fixture({ action }: { action: "assign" | "open" }) {
  const [fixture, setFixture] = useState<Fixture | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [mediaUrl, setMediaUrl] = useState("");
  const [step, setStep] = useState<AssignedStep | null>(null);
  const [mediaHref, setMediaHref] = useState<string | null>(null);
  const [mediaTitle, setMediaTitle] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const retry = useRef<{ body: string; key: string } | null>(null);
  const mediaRetry = useRef<{ url: string; title: string; key: string } | null>(null);
  const mediaWithdrawKey = useRef<string | null>(null);
  const client = action === "open";

  const progressKeys = useRef<Partial<Record<"complete" | "share" | "revoke", string>>>({});

  useEffect(() => {
    const controller = new AbortController();
    fetch(endpoint, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) return;
        const body = await response.json() as Fixture;
        setFixture(body);
        if (action === "open") setStep(readStoredStep(body.journey_version_id));
      })
      .catch(() => {});
    return () => controller.abort();
  }, [action]);

  function applyStep(next: AssignedStep | null) {
    setStep(next);
    storeStep(next);
  }

  function clearMedia() {
    setMediaHref(null);
    setMediaTitle(null);
  }

  async function run(operation: "assign" | "open" | "send" | "list" | "complete" | "share" | "revoke" | "own" | "released"
    | "attach-media" | "view-media" | "withdraw-media") {
    setPending(true);
    setResult(null);
    setNotice(null);
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
      const payload = await response.json();
      setResult({ ...payload, status: response.status });
      if (response.ok && operation === "revoke") delete progressKeys.current.share;
      if (response.ok && operation === "share") delete progressKeys.current.revoke;
      if (operation === "open") {
        if (response.ok && payload.data?.title && payload.data.journey_version_id === fixture?.journey_version_id
          && payload.data.step_id === PA05_STEP_ID && payload.data.profile === LOOPBACK_PROFILE
          && sameSource(payload.data.source_ref)) {
          applyStep({
            journey_version_id: payload.data.journey_version_id,
            step_id: payload.data.step_id,
            title: payload.data.title,
            source_ref: payload.data.source_ref,
            profile: payload.data.profile,
          });
        } else {
          applyStep(null);
          clearMedia();
          setNotice("This step is not available.");
        }
      }
      if (operation === "view-media" || operation === "withdraw-media") {
        if (client && operation === "view-media" && response.ok) {
          const href = clickableMediaHref(payload.data, fixture?.journey_version_id);
          if (href) {
            setMediaHref(href);
            setMediaTitle(typeof payload.data?.media_link?.title === "string"
              ? payload.data.media_link.title : "External test media");
          } else {
            clearMedia();
            setNotice("Step media is not available.");
          }
        } else {
          clearMedia();
          if (client && (operation === "withdraw-media" || !response.ok)) {
            setNotice("Step media is not available.");
          }
        }
      }
    } catch {
      setResult({ status: 503, error: { code: "FIXTURE_UNAVAILABLE" } });
      if (operation === "open" || operation === "view-media") {
        if (operation === "open") applyStep(null);
        clearMedia();
        setNotice("This step is not available.");
      }
    } finally {
      setPending(false);
    }
  }

  if (!fixture) return null;
  return (
    <section aria-label="Synthetic local journey fixture">
      <h2>Synthetic local PA-05 fixture</h2>
      <p>TEST_ONLY. NO_LIVE_KDB. TrustedKdbVerifier=NONE. {LOOPBACK_PROFILE}.</p>
      <p>Published journey version: {fixture.journey_version_id}</p>
      <p>Test client: {fixture.client_id}</p>
      {client && step ? (
        <article data-assigned-step="active" aria-label="Assigned client step">
          <p data-test-only="true">TEST_ONLY · NO_LIVE_KDB · source pin PA-05</p>
          <h3 data-step-title={step.title}>{step.title}</h3>
          <p data-step-id={step.step_id}>Step {step.step_id}</p>
          <p data-step-version={step.journey_version_id}>Journey version {step.journey_version_id}</p>
          <p data-source-pin="PA-05">
            Source PA-05 · {step.source_ref.variant} · {step.source_ref.protocol_version_id}
          </p>
        </article>
      ) : client ? (
        <p data-assigned-step="empty">No assigned step is open in this local fixture.</p>
      ) : null}
      {client && mediaHref ? (
        <p>
          <a
            data-external-media="true"
            href={mediaHref}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open coach media{mediaTitle ? `: ${mediaTitle}` : ""}
          </a>
        </p>
      ) : null}
      {notice ? <p data-step-notice="true">{notice}</p> : null}
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
        {result?.data ? <pre data-debug-json="true">{JSON.stringify(result.data, null, 2)}</pre> : null}
      </div>
    </section>
  );
}
