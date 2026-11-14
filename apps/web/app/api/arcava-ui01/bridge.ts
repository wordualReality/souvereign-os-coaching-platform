import { createHmac, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const assignmentCookie = "arcava_ui01_assignment";

function deny(status: number, code: string) {
  return NextResponse.json({ error: { code } }, { status, headers: { "Cache-Control": "no-store" } });
}

function config(request: NextRequest) {
  const { ARCAVA_UI01_MODE, ARCAVA_UI01_SERVICE_PORT, ARCAVA_UI01_VERSION,
    ARCAVA_UI01_COACH_BEARER, ARCAVA_UI01_CLIENT_BEARER, __NEXT_PRIVATE_ORIGIN } = process.env;
  const host = request.headers.get("host");
  if (process.env.NODE_ENV !== "production" || ARCAVA_UI01_MODE !== "TEST_LOOPBACK_ONLY"
      || !host || !/^127\.0\.0\.1:[1-9]\d{0,4}$/.test(host)
      || __NEXT_PRIVATE_ORIGIN !== "http://" + host
      || !ARCAVA_UI01_SERVICE_PORT || !/^[1-9]\d{0,4}$/.test(ARCAVA_UI01_SERVICE_PORT)
      || Number(ARCAVA_UI01_SERVICE_PORT) > 65535 || ARCAVA_UI01_SERVICE_PORT === host.split(":")[1]
      || !ARCAVA_UI01_VERSION || !uuid.test(ARCAVA_UI01_VERSION)
      || !ARCAVA_UI01_COACH_BEARER || !ARCAVA_UI01_CLIENT_BEARER
      || ARCAVA_UI01_COACH_BEARER === ARCAVA_UI01_CLIENT_BEARER) return null;
  return {
    origin: "http://" + host,
    service: "http://127.0.0.1:" + ARCAVA_UI01_SERVICE_PORT + "/project-b/v1",
    version: ARCAVA_UI01_VERSION,
    coach: ARCAVA_UI01_COACH_BEARER,
    client: ARCAVA_UI01_CLIENT_BEARER,
  };
}

const tenant = "11111111-1111-4111-8111-111111111111";
const client = "33333333-3333-4333-8333-333333333333";
const step = "66666666-6666-4666-8666-666666666666";
const assignments = "/tenants/" + tenant + "/clients/" + client + "/assignments";

export async function GET(request: NextRequest) {
  const context = config(request);
  if (!context) return deny(404, "FIXTURE_DISABLED");
  return NextResponse.json({ journey_version_id: context.version, client_id: client },
    { headers: { "Cache-Control": "no-store" } });
}

function signedAssignment(assignment: string, version: string, secret: string) {
  const signature = createHmac("sha256", secret).update(version + ":" + assignment).digest("hex");
  return assignment + "." + signature;
}

function sessionAssignment(cookie: string | undefined, version: string, secret: string) {
  if (!cookie) return null;
  const assignment = cookie.split(".")[0];
  if (!uuid.test(assignment)) return null;
  const expected = Buffer.from(signedAssignment(assignment, version, secret));
  const provided = Buffer.from(cookie);
  return expected.length === provided.length && timingSafeEqual(expected, provided) ? assignment : null;
}

export async function fixturePost(request: NextRequest, messageRole?: "coach" | "client") {
  const context = config(request);
  if (!context) return deny(404, "FIXTURE_DISABLED");
  if (request.headers.get("origin") !== context.origin) return deny(403, "ORIGIN_DENIED");
  if (request.nextUrl.search || request.headers.has("authorization")) return deny(422, "INVALID");
  const raw = await request.text();
  if (raw.length > 4096) return deny(422, "INVALID");
  let message: { body: string; key: string } | undefined;
  if (messageRole && raw !== "list") {
    try {
      const input = JSON.parse(raw);
      if (!input || Object.keys(input).sort().join(",") !== "body,key"
          || typeof input.body !== "string" || typeof input.key !== "string"
          || !uuid.test(input.key)) return deny(422, "INVALID");
      message = input;
    } catch {
      return deny(422, "INVALID");
    }
  } else if (!messageRole && raw !== "assign" && raw !== "open") {
    return deny(422, "INVALID");
  }
  const assignment = sessionAssignment(request.cookies.get(assignmentCookie)?.value, context.version, context.coach);
  if ((messageRole || raw === "open") && !assignment) return deny(404, "NOT_FOUND");

  const options = { cache: "no-store", redirect: "error", signal: AbortSignal.timeout(3000) } as const;
  try {
    const health = await fetch(context.service + "/health", options);
    const profile = health.ok && (await health.json()).data;
    if (profile?.profile !== "TEST_LOOPBACK_ONLY" || profile.bind !== "127.0.0.1"
        || profile.runtime !== "loopback_fixture" || profile.status !== "ready") return deny(503, "FIXTURE_UNAVAILABLE");

    const assigned = !messageRole && raw === "assign";
    const messagePath = assignments + "/" + assignment + "/versions/" + context.version + "/steps/" + step + "/messages";
    const upstream = messageRole
      ? await fetch(context.service + messagePath, { ...options, method: message ? "POST" : "GET",
        headers: { Authorization: "Bearer " + context[messageRole],
          ...(message ? { "Content-Type": "application/json", "Idempotency-Key": message.key } : {}) },
        body: message ? JSON.stringify({ body: message.body }) : undefined })
      : assigned
      ? await fetch(context.service + assignments, { ...options, method: "POST",
        headers: { Authorization: "Bearer " + context.coach, "Content-Type": "application/json",
          "Idempotency-Key": "arcava-ui01-" + context.version },
        body: JSON.stringify({ journey_version_id: context.version }) })
      : await fetch(context.service + assignments + "/" + assignment + "/version/steps/" + step,
        { ...options, headers: { Authorization: "Bearer " + context.client } });
    const body = await upstream.json();
    if (!upstream.ok) return deny(upstream.status, body.error?.code ?? "UPSTREAM_DENIED");
    const data = body.data;
    if (data?.journey_version_id !== context.version
        || (assigned && (upstream.status !== 201 || data.client_id !== client || !uuid.test(data.assignment_id ?? "")))
        || (!assigned && (upstream.status !== (message ? 201 : 200) || data.profile !== "TEST_LOOPBACK_ONLY"
          || data.step_id !== step || (messageRole && data.assignment_id !== assignment)))) {
      return deny(502, "FIXTURE_RESPONSE_MISMATCH");
    }
    const response = NextResponse.json({ data }, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
    if (assigned) response.cookies.set(assignmentCookie, signedAssignment(data.assignment_id, context.version, context.coach), { httpOnly: true, sameSite: "strict", path: "/" });
    return response;
  } catch {
    return deny(503, "FIXTURE_UNAVAILABLE");
  }
}
