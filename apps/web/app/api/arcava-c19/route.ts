import { NextRequest, NextResponse } from "next/server";

const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const draftCookie = "arcava_c19_draft";
const tenant = "11111111-1111-4111-8111-111111111111";
const CALM = "c19.synthetic.course.calm-foundation";
const FOCUS = "c19.synthetic.course.focus-reset";

function deny(status: number, code: string, retryable = false) {
  return NextResponse.json({ error: { code, retryable } }, { status, headers: { "Cache-Control": "no-store" } });
}

function config(request: NextRequest) {
  const { ARCAVA_UI01_MODE, ARCAVA_UI01_SERVICE_PORT, ARCAVA_UI01_VERSION,
    ARCAVA_UI01_COACH_BEARER, __NEXT_PRIVATE_ORIGIN } = process.env;
  const host = request.headers.get("host");
  if (process.env.NODE_ENV !== "production" || ARCAVA_UI01_MODE !== "TEST_LOOPBACK_ONLY"
      || !host || !/^127\.0\.0\.1:[1-9]\d{0,4}$/.test(host)
      || __NEXT_PRIVATE_ORIGIN !== "http://" + host
      || !ARCAVA_UI01_SERVICE_PORT || !/^[1-9]\d{0,4}$/.test(ARCAVA_UI01_SERVICE_PORT)
      || Number(ARCAVA_UI01_SERVICE_PORT) > 65535
      || !ARCAVA_UI01_VERSION || !uuid.test(ARCAVA_UI01_VERSION)
      || !ARCAVA_UI01_COACH_BEARER) return null;
  return {
    origin: "http://" + host,
    service: "http://127.0.0.1:" + ARCAVA_UI01_SERVICE_PORT + "/project-b/v1/tenants/" + tenant,
    coach: ARCAVA_UI01_COACH_BEARER,
  };
}

function sourcedDraft(data: {
  steps?: Array<{
    step_id?: string;
    title?: string;
    source?: { candidate_id?: string; version?: string; content_hash?: string };
    published_version_ref?: string;
    receipt_sha256?: string;
  }>;
  publication_state?: string;
} | undefined) {
  if (!data) return data;
  return {
    ...data,
    publication_state: data.publication_state ?? "DRAFT",
    steps: (data.steps ?? []).map(step => {
      if (step.source?.candidate_id) return step;
      const ref = step.published_version_ref ?? "";
      const at = ref.lastIndexOf("@");
      return {
        ...step,
        source: {
          candidate_id: at > 0 ? ref.slice(0, at) : ref,
          version: at > 0 ? ref.slice(at + 1) : "",
          content_hash: step.receipt_sha256 ?? "",
        },
      };
    }),
  };
}

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const context = config(request);
  if (!context) return deny(404, "FIXTURE_DISABLED");
  const draftId = request.cookies.get(draftCookie)?.value;
  return NextResponse.json({
    profile: "TEST_LOOPBACK_ONLY",
    test_only: true,
    no_live_kdb: true,
    candidate_ids: [CALM, FOCUS],
    draft_id: draftId && uuid.test(draftId) ? draftId : null,
  }, { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: NextRequest) {
  const context = config(request);
  if (!context) return deny(404, "FIXTURE_DISABLED");
  if (request.headers.get("origin") !== context.origin) return deny(403, "ORIGIN_DENIED");
  if (request.nextUrl.search || request.headers.has("authorization")) return deny(422, "INVALID");
  const raw = await request.text();
  if (raw.length > 16_384) return deny(422, "INVALID");
  let input: {
    action?: string;
    learning_goal?: string;
    title?: string;
    steps?: unknown;
    draft_id?: string;
    expected_revision?: number;
    force_adapter_error?: boolean;
    force_fetch_timeout?: boolean;
    key?: string;
    digest?: unknown;
  };
  try { input = JSON.parse(raw); }
  catch { return deny(422, "INVALID"); }
  const action = input.action;
  const options = { cache: "no-store" as const, redirect: "error" as const, signal: AbortSignal.timeout(3000) };
  const headers = { Authorization: "Bearer " + context.coach, "Content-Type": "application/json",
    ...(input.key && uuid.test(input.key) ? { "Idempotency-Key": input.key } : {}) };
  try {
    if (input.force_fetch_timeout === true) {
      const error = new Error("timeout");
      error.name = "TimeoutError";
      throw error;
    }
    if (action === "review") {
      const allowed = new Set(["action", "draft_id", "expected_revision", "key", "force_fetch_timeout"]);
      if (Object.keys(input).some(field => !allowed.has(field)) || input.digest !== undefined)
        return deny(422, "INVALID");
      if (!input.draft_id || !uuid.test(input.draft_id) || !input.key || !uuid.test(input.key)
          || typeof input.expected_revision !== "number")
        return deny(422, "INVALID");
      const upstream = await fetch(context.service + "/journeys/drafts/" + input.draft_id + "/local-review", {
        ...options, method: "POST", headers,
        body: JSON.stringify({
          draft_id: input.draft_id,
          expected_revision: input.expected_revision,
        }),
      });
      const body = await upstream.json();
      if (!upstream.ok) return NextResponse.json({ error: body.error }, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
      return NextResponse.json({ data: sourcedDraft(body.data) }, { status: 201, headers: { "Cache-Control": "no-store" } });
    }
    if (action === "propose") {
      const upstream = await fetch(context.service + "/journeys/draft-proposals", {
        ...options, method: "POST", headers,
        body: JSON.stringify({
          learning_goal: input.learning_goal,
          candidate_ids: [CALM, FOCUS],
          force_adapter_error: input.force_adapter_error === true,
        }),
      });
      const body = await upstream.json();
      if (!upstream.ok) return NextResponse.json({ error: body.error }, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
      return NextResponse.json({ data: body.data }, { headers: { "Cache-Control": "no-store" } });
    }
    if (action === "save") {
      if (!input.key || !uuid.test(input.key)) return deny(422, "INVALID");
      const upstream = await fetch(context.service + "/journeys/draft-proposals/commit", {
        ...options, method: "POST", headers,
        body: JSON.stringify({
          learning_goal: input.learning_goal,
          title: input.title,
          steps: input.steps,
          ...(input.draft_id ? { draft_id: input.draft_id, expected_revision: input.expected_revision } : {}),
        }),
      });
      const body = await upstream.json();
      if (!upstream.ok) return NextResponse.json({ error: body.error }, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
      const response = NextResponse.json({ data: body.data }, { status: 201, headers: { "Cache-Control": "no-store" } });
      response.cookies.set(draftCookie, body.data.draft_id, { httpOnly: true, sameSite: "strict", path: "/" });
      return response;
    }
    if (action === "load") {
      const draftId = input.draft_id || request.cookies.get(draftCookie)?.value;
      if (!draftId || !uuid.test(draftId)) return deny(404, "NOT_FOUND");
      const upstream = await fetch(context.service + "/journeys/drafts/" + draftId, {
        ...options, headers: { Authorization: "Bearer " + context.coach },
      });
      const body = await upstream.json();
      if (!upstream.ok) return NextResponse.json({ error: body.error }, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
      return NextResponse.json({ data: sourcedDraft(body.data) }, { headers: { "Cache-Control": "no-store" } });
    }
    return deny(422, "INVALID");
  } catch {
    return deny(503, "FIXTURE_UNAVAILABLE", true);
  }
}
