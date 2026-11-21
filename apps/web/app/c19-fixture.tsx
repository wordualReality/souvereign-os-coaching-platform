"use client";

import { useState } from "react";

const endpoint = "/api/arcava-c19";

type Source = {
  candidate_id: string;
  version: string;
  content_hash: string;
  purpose?: string;
  rights_state?: string;
  lifecycle?: string;
};
type Step = { step_id: string; title: string; ordinal?: number; source: Source };
type Draft = {
  draft_id?: string;
  title?: string;
  revision?: number;
  status?: string;
  publication_state?: string;
  origin?: string;
  digest?: string;
  review_state?: string;
  review_label?: string;
  review_receipt?: { reviewer_id?: string; digest?: string; revision?: number; test_only?: boolean };
  steps?: Step[];
  learning_goal?: string;
};

function snapshot(title: string, steps: Step[]) {
  return JSON.stringify({
    title,
    steps: steps.map(step => ({
      id: step.step_id,
      title: step.title,
      candidate: step.source.candidate_id,
      version: step.source.version,
      hash: step.source.content_hash,
    })),
  });
}

export function C19GoalDraftFixture() {
  const [goal, setGoal] = useState("Build a calm two-source practice");
  const [title, setTitle] = useState("Calm practice draft");
  const [steps, setSteps] = useState<Step[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saveKey, setSaveKey] = useState<string | null>(null);
  const [reviewKey, setReviewKey] = useState<string | null>(null);
  const [persisted, setPersisted] = useState<string>(snapshot("Calm practice draft", []));
  const dirty = snapshot(title, steps) !== persisted;

  async function run(action: "propose" | "save" | "load" | "review", extra: Record<string, unknown> = {}) {
    if (action === "review" && dirty) {
      setStatus("HTTP 422 UNSAVED_CHANGES");
      setNotice("Save or reload the persisted draft before review.");
      return;
    }
    setPending(true);
    setStatus(null);
    setNotice(null);
    try {
      const key = action === "save" ? (saveKey ?? crypto.randomUUID())
        : action === "review" ? (reviewKey ?? crypto.randomUUID())
        : undefined;
      if (action === "save" && !saveKey) setSaveKey(key ?? null);
      if (action === "review" && !reviewKey) setReviewKey(key ?? null);
      const body = action === "review"
        ? { action, draft_id: draft?.draft_id, expected_revision: draft?.revision, key, ...extra }
        : {
          action,
          learning_goal: goal,
          title,
          steps,
          draft_id: draft?.draft_id,
          expected_revision: draft?.revision,
          key,
          ...extra,
        };
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        signal: AbortSignal.timeout(4000),
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      setStatus(`HTTP ${response.status}${payload.error?.code ? " " + payload.error.code : ""}`);
      if (response.ok && payload.data) {
        if (payload.data.steps) setSteps(payload.data.steps);
        if (payload.data.draft_id) setDraft(payload.data);
        if (typeof payload.data.title === "string") setTitle(payload.data.title);
        if (typeof payload.data.learning_goal === "string") setGoal(payload.data.learning_goal);
        if (payload.data.draft_id) {
          const nextTitle = typeof payload.data.title === "string" ? payload.data.title : title;
          const nextSteps = payload.data.steps ?? steps;
          setPersisted(snapshot(nextTitle, nextSteps));
        }
        if (action === "save") setReviewKey(null);
        setNotice(null);
      } else {
        setNotice(payload.error?.retryable
          ? "Proposal adapter is temporarily unavailable. The saved draft was not changed."
          : "This outline is not available.");
      }
    } catch {
      setStatus("HTTP 0 FETCH_REJECTED");
      setNotice("Proposal adapter is temporarily unavailable. The saved draft was not changed.");
    } finally {
      setPending(false);
    }
  }

  async function load() { await run("load"); }

  return (
    <section aria-label="C19 local goal draft fixture">
      <h2>TEST_ONLY goal to sourced draft</h2>
      <p>NO_LIVE_KDB. TrustedKdbVerifier=NONE. Two synthetic course candidates only.</p>
      <p>
        <label>Learning goal <input data-c19-goal value={goal} maxLength={200}
          onChange={event => setGoal(event.target.value)} /></label>
      </p>
      <p>
        <label>Draft title <input data-c19-title value={title} maxLength={200}
          onChange={event => { setTitle(event.target.value); setSaveKey(null); }} /></label>
      </p>
      <p>
        <button type="button" disabled={pending} onClick={() => run("propose")}>Propose sourced outline</button>
        <button type="button" disabled={pending || steps.length === 0} onClick={() => run("save")}>Save draft</button>
        <button type="button" disabled={pending} onClick={load}>Reload saved draft</button>
        <button type="button" disabled={pending || !draft?.draft_id}
          onClick={() => run("review")}>Confirm local review</button>
        <button type="button" disabled={pending} onClick={() => run("propose", { force_adapter_error: true })}>
          Simulate adapter failure
        </button>
        <button type="button" disabled={pending} onClick={() => run("propose", { force_fetch_timeout: true })}>
          Simulate fetch timeout
        </button>
      </p>
      {draft?.draft_id ? (
        <p data-c19-revision={String(draft.revision ?? "")}>
          Saved revision {draft.revision} · status {draft.status} · {draft.publication_state}
        </p>
      ) : <p data-c19-revision="">No draft saved in this local fixture.</p>}
      <aside aria-label="C19 local draft review" data-c19-review="true" data-c19-dirty={dirty ? "true" : "false"}>
        <p data-c19-review-label="true">LOCAL TEST REVIEW, NOT PUBLISHING</p>
        <p data-c19-review-id={draft?.draft_id ?? ""}>Draft {draft?.draft_id ?? "unsaved"}</p>
        <p data-c19-review-state={draft?.review_state ?? "NONE"}>Review {draft?.review_state ?? "NONE"}</p>
        <p data-c19-digest={draft?.digest ?? ""}>Digest {draft?.digest ?? "none"}</p>
        <p data-c19-review-actor={draft?.review_receipt?.reviewer_id ?? ""}>
          Reviewer {draft?.review_receipt?.reviewer_id ?? "none"}
        </p>
        <ol>
          {steps.map(step => (
            <li key={"review-" + step.step_id}>
              {step.title} · {step.source.candidate_id}@{step.source.version}
              · {step.source.rights_state ?? "SYNTHETIC_TEST_ONLY"}
              · {step.source.lifecycle ?? "ACTIVE"}
            </li>
          ))}
        </ol>
      </aside>
      <ol data-c19-steps={String(steps.length)}>
        {steps.map((step, index) => (
          <li key={step.step_id} data-c19-step={step.step_id}>
            <input
              aria-label={"Step title " + (index + 1)}
              value={step.title}
              onChange={event => {
                setSaveKey(null);
                setSteps(current => current.map((row, rowIndex) =>
                  rowIndex === index ? { ...row, title: event.target.value } : row));
              }}
            />
            <span data-c19-source={step.source.candidate_id}>{step.source.candidate_id}@{step.source.version}</span>
            <span data-c19-hash={step.source.content_hash}>{step.source.content_hash}</span>
            <button type="button" disabled={pending || index === 0} onClick={() => {
              setSaveKey(null);
              setSteps(current => {
                const next = current.slice();
                [next[index - 1], next[index]] = [next[index], next[index - 1]];
                return next;
              });
            }}>Move up</button>
            <button type="button" disabled={pending || index === steps.length - 1} onClick={() => {
              setSaveKey(null);
              setSteps(current => {
                const next = current.slice();
                [next[index + 1], next[index]] = [next[index], next[index + 1]];
                return next;
              });
            }}>Move down</button>
            <button type="button" disabled={pending || steps.length < 2} onClick={() => {
              setSaveKey(null);
              setSteps(current => current.filter((_, rowIndex) => rowIndex !== index));
            }}>Remove step</button>
          </li>
        ))}
      </ol>
      {notice ? <p data-c19-notice="true">{notice}</p> : null}
      {status ? <p role="status" data-c19-status="true">{status}</p> : null}
    </section>
  );
}
