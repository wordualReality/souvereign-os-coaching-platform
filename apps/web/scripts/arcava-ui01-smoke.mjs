import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { appendFile, mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, execFileSync } from "node:child_process";
import { once } from "node:events";

const root = new URL("../../../", import.meta.url);
process.chdir(fileURLToPath(root));
const work = await mkdtemp(join(tmpdir(), "arcava-ui01-smoke-"));
const journal = join(work, "journal.ndjson");
const classes = join(work, "classes");
const coach = randomUUID();
const client = randomUUID();
const otherCoach = randomUUID();
const otherClient = randomUUID();
const env = {
  ...process.env, NEXT_TELEMETRY_DISABLED: "1",
  ARCAVA_UI01_COACH_BEARER: coach, ARCAVA_UI01_CLIENT_BEARER: client,
  ARCAVA_UI02_OTHER_COACH: otherCoach, ARCAVA_UI02_OTHER_CLIENT: otherClient,
};
for (const key of ["DATABASE_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"]) delete env[key];

const children = new Set();
function launch(file, args, options = {}) {
  const child = spawn(file, args, { env, ...options });
  children.add(child);
  child.once("exit", () => children.delete(child));
  child.on("error", error => console.error(error.message));
  return child;
}

async function stop(child, signal = "SIGTERM") {
  if (child?.pid && child.exitCode === null && child.signalCode === null) {
    const exited = once(child, "exit");
    child.kill(signal);
    await exited;
  }
}

async function until(check, label) {
  for (let i = 0; i < 120; i++) {
    const value = await check();
    if (value) return value;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error("Timed out: " + label);
}

async function service(mode) {
  const child = launch("java", ["-cp", classes, "com.projectb.api.http.JourneyUiFixture", journal, mode]);
  let log = "";
  child.stdout.on("data", chunk => { log += chunk; });
  child.stderr.pipe(process.stderr);
  const port = await until(() => log.match(/^PORT (\d+)$/m)?.[1], "Java listener");
  return { child, port, version: log.match(/^VERSION (\S+)$/m)?.[1] };
}

const listener = createServer();
listener.listen(0, "127.0.0.1");
await once(listener, "listening");
const port = listener.address().port;
await new Promise(resolve => listener.close(resolve));
const origin = "http://127.0.0.1:" + port;
const endpoint = origin + "/api/arcava-ui01";
const tenant = "11111111-1111-4111-8111-111111111111";
const clientId = "33333333-3333-4333-8333-333333333333";
const stepId = "66666666-6666-4666-8666-666666666666";
const source = {
  schema_version: 1, variant: "KDB_PROTOCOL_VERSION",
  protocol_id: "05000000-0000-4000-8000-000000000009",
  protocol_version_id: "05000000-0000-4000-8000-000000000010",
  owning_module_id: "05000000-0000-4000-8000-000000000013",
  taxonomy_version_id: "05000000-0000-4000-8000-000000000014",
  relation_ids: [],
};

async function web(servicePort, version, mode = "TEST_LOOPBACK_ONLY") {
  const child = launch(process.execPath, ["node_modules/next/dist/bin/next", "start",
    "apps/web", "--hostname", "127.0.0.1", "--port", String(port)], {
    env: { ...env, ARCAVA_UI01_MODE: mode, ARCAVA_UI01_SERVICE_PORT: servicePort, ARCAVA_UI01_VERSION: version },
  });
  child.stdout.pipe(process.stdout);
  child.stderr.pipe(process.stderr);
  await until(async () => fetch(origin).then(response => response.ok).catch(() => false), "Next listener");
  return child;
}

let socket;
try {
  await mkdir(classes);
  const src = "services/api/src/";
  const pkg = "/java/com/projectb/api/";
  execFileSync("javac", ["-Xlint:all", "-Werror", "-d", classes,
    ...["domain/JourneyKernel", "domain/JourneyJournal", "domain/GoalProposalAdapter", "json/JsonMini", "http/JourneyHttpServer",
      "http/JourneyProducer", "http/TrustedKdbVerifier", "http/TrustedPiacVerifier"]
      .map(name => src + "main" + pkg + name + ".java"),
    ...["JourneyPathTest", "JourneyUiFixture"].map(name => src + "test" + pkg + "http/" + name + ".java"),
  ], { stdio: "inherit" });

  let backend = await service("seed");
  const version = backend.version;
  assert.ok(version);
  let next = await web(backend.port, version, "disabled");
  assert.equal((await fetch(endpoint)).status, 404);
  await stop(next);
  next = await web(backend.port, version);
  assert.equal(execFileSync("curl", ["-sS", "-o", "/dev/null", "-w", "%{http_code}",
    "-H", "Host: example.invalid", endpoint], { encoding: "utf8" }), "404");
  const post = (body, headers = {}, url = endpoint) => fetch(url, { method: "POST", body, headers: { origin, ...headers } });
  assert.equal((await post("assign", { origin: "http://example.invalid" })).status, 403);
  assert.equal((await post("assign", {}, endpoint + "?tenant=other")).status, 422);
  assert.equal((await post("assign", { authorization: "Bearer external" })).status, 422);
  assert.equal((await post("open")).status, 404);

  const profile = join(work, "browser");
  const chrome = launch(process.env.ARCAVA_UI01_CHROME ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ["--headless", "--disable-background-networking", "--disable-sync", "--no-first-run", "--remote-debugging-port=0",
      "--user-data-dir=" + profile, "about:blank"]);
  chrome.stderr.resume();
  const debugPort = await until(async () => {
    try { return (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; }
    catch { return null; }
  }, "Chrome debugging port");
  const pages = await (await fetch("http://127.0.0.1:" + debugPort + "/json/list")).json();
  socket = new WebSocket(pages.find(target => target.type === "page").webSocketDebuggerUrl);
  await once(socket, "open");
  const commands = new Map();
  const events = [];
  let sequence = 0;
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    const command = commands.get(message.id);
    if (command) {
      commands.delete(message.id);
      if (message.error) command.reject(new Error(message.error.message));
      else command.resolve(message.result);
    } else if (message.method === "Network.responseReceived") {
      events.push(message.params);
    }
  });
  function cdp(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      commands.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async function evaluate(expression) {
    const reply = await cdp("Runtime.evaluate", { expression, returnByValue: true });
    assert.equal(reply.exceptionDetails, undefined);
    return reply.result.value;
  }
  await cdp("Network.enable");
  await cdp("Page.enable");
  async function navigate(path) {
    await cdp("Page.navigate", { url: origin + path });
    await until(() => evaluate("location.pathname === " + JSON.stringify(path)
      + " && document.querySelector(\"section[aria-label='Synthetic local journey fixture'] button\") !== null"), path);
  }
  async function click(label, status, route = endpoint) {
    const start = events.length;
    const selector = "section[aria-label='Synthetic local journey fixture'] button";
    const index = await evaluate(`Array.from(document.querySelectorAll(${JSON.stringify(selector)}))
      .findIndex(button => button.textContent.trim() === ${JSON.stringify(label)} && !button.disabled)`);
    assert.ok(index >= 0, "enabled control: " + label);
    await evaluate(`document.querySelectorAll(${JSON.stringify(selector)})[${index}].scrollIntoView({block:"center"})`);
    const button = await cdp("DOM.getDocument");
    const { nodeIds } = await cdp("DOM.querySelectorAll", { nodeId: button.root.nodeId, selector });
    const nodeId = nodeIds[index];
    const { model } = await cdp("DOM.getBoxModel", { nodeId });
    const [x1,y1,x2,, ,y3] = model.content;
    const x = (x1 + x2) / 2;
    const y = (y1 + y3) / 2;
    for (const type of ["mousePressed", "mouseReleased"])
      await cdp("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1 });
    const wire = await until(() => events.slice(start).find(event => event.response.url === route), "UI service response");
    assert.equal(wire.response.status, status);
    await until(() => evaluate("document.querySelector('[role=status]')?.textContent?.startsWith('HTTP " + status + "')"), "visible HTTP status");
    const raw = await cdp("Network.getResponseBody", { requestId: wire.requestId });
    assert.equal(raw.base64Encoded, false);
    const body = JSON.parse(raw.body);
    const visible = await evaluate("document.querySelector('pre')?.textContent ?? null");
    if (status >= 400) assert.equal(visible, null);
    else assert.deepEqual(JSON.parse(visible), body.data);
    return body;
  }
  const stepTitle = () => evaluate("document.querySelector('[data-step-title]')?.getAttribute('data-step-title') ?? null");
  const mediaNav = () => evaluate("document.querySelector('a[data-external-media]')?.getAttribute('href') ?? null");
  const mediaRel = () => evaluate("document.querySelector('a[data-external-media]')?.getAttribute('rel') ?? null");
  const mediaTarget = () => evaluate("document.querySelector('a[data-external-media]')?.getAttribute('target') ?? null");
  await navigate("/coach/journeys");
  const assigned = (await click("Assign published test Journey", 201)).data;
  assert.equal(assigned.journey_version_id, version);
  assert.equal(assigned.client_id, clientId);
  const durable = await readFile(journal);
  assert.deepEqual((await click("Assign published test Journey", 201)).data, assigned);
  assert.deepEqual(await readFile(journal), durable);
  await navigate("/client/member-home");
  const checkOpen = async () => {
    const opened = (await click("Open assigned step", 200)).data;
    assert.equal(opened.journey_version_id, version);
    assert.equal(opened.step_id, stepId);
    assert.equal(opened.title, "Breathing");
    assert.deepEqual(opened.source_ref, source);
    assert.equal(await stepTitle(), "Breathing");
    assert.equal(await mediaNav(), null);
    assert.deepEqual(await readFile(journal), durable);
  };
  await checkOpen();
  await checkOpen();
  await cdp("Page.reload");
  await until(() => evaluate("document.querySelector(\"section[aria-label='Synthetic local journey fixture'] button\") !== null && document.querySelector('pre') === null"), "browser refresh");
  await checkOpen();

  async function restart(mode = "replay", partialTail = false) {
    await stop(next);
    await stop(backend.child);
    if (partialTail) await appendFile(journal, '{"op":"step_progress"');
    backend = await service(mode);
    next = await web(backend.port, version);
    await navigate("/client/member-home");
  }
  await restart();
  await checkOpen();
  const coachRoute = endpoint + "/coach";
  const clientRoute = endpoint + "/client";
  const list = (role, status = 200) => click("View step messages", status, role === "coach" ? coachRoute : clientRoute);
  const send = role => click("Send step message", 201, role === "coach" ? coachRoute : clientRoute);
  async function type(body) {
    await evaluate(`(() => {
      const input = document.querySelector("section[aria-label='Synthetic local journey fixture'] input");
      input.focus();
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      setter.call(input, ${JSON.stringify(body)});
      input.dispatchEvent(new Event("input", { bubbles: true }));
    })()`);
    assert.equal(await evaluate("document.querySelector(\"section[aria-label='Synthetic local journey fixture'] input\").value"), body);
  }
  function checkBinding(data) {
    assert.equal(data.assignment_id, assigned.assignment_id);
    assert.equal(data.journey_version_id, version);
    assert.equal(data.step_id, stepId);
    assert.deepEqual(data.source_ref, source);
  }

  await navigate("/coach/journeys");
  await type("Synthetic coach message");
  const coachSent = (await send("coach")).data;
  checkBinding(coachSent);
  assert.equal(coachSent.message.sender_role, "COACH");
  assert.equal(coachSent.message.body, "Synthetic coach message");
  const coachBytes = await readFile(journal);
  assert.deepEqual((await send("coach")).data, coachSent);
  assert.deepEqual(await readFile(journal), coachBytes);

  await navigate("/client/member-home");
  const clientRead = (await list("client")).data;
  checkBinding(clientRead);
  assert.deepEqual(clientRead.messages, [coachSent.message]);
  await type("Synthetic client reply");
  const clientSent = (await send("client")).data;
  checkBinding(clientSent);
  assert.equal(clientSent.message.sender_role, "CLIENT");
  assert.equal(clientSent.message.sender_id, clientId);
  assert.equal(clientSent.message.body, "Synthetic client reply");
  assert.equal(await stepTitle(), "Breathing");
  await navigate("/coach/journeys");
  const thread = (await list("coach")).data;
  checkBinding(thread);
  assert.deepEqual(thread.messages, [coachSent.message, clientSent.message]);
  const messageBytes = await readFile(journal);
  await cdp("Page.reload");
  await until(() => evaluate("document.querySelector(\"section[aria-label='Synthetic local journey fixture'] button\") !== null && document.querySelector('pre') === null"), "message refresh");
  assert.deepEqual((await list("coach")).data, thread);
  await restart();
  assert.deepEqual((await list("client")).data, thread);
  await navigate("/coach/journeys");
  assert.deepEqual((await list("coach")).data, thread);

  const messagePath = "/project-b/v1/tenants/" + tenant + "/clients/" + clientId + "/assignments/"
    + assigned.assignment_id + "/versions/" + version + "/steps/" + stepId + "/messages";
  async function backendRequest(path, token, payload, key = randomUUID()) {
    const headers = token ? { authorization: "Bearer " + token } : {};
    if (payload !== undefined) {
      headers["idempotency-key"] = key;
      headers["content-type"] = "application/json";
    }
    return fetch("http://127.0.0.1:" + backend.port + path, { headers,
      method: payload === undefined ? "GET" : "POST", body: payload === undefined ? undefined : JSON.stringify(payload) });
  }
  const denied = async (status, path, token, payload, key) => {
    const response = await backendRequest(path, token, payload, key);
    assert.equal(response.status, status, path);
    assert.equal((await response.json()).data, undefined);
  };
  await denied(401, messagePath);
  await denied(403, messagePath.replace(tenant, randomUUID()), coach);
  await denied(403, messagePath, otherCoach, { body: "denied" });
  await denied(403, messagePath, otherClient);
  for (const id of [assigned.assignment_id, version, stepId]) await denied(404, messagePath.replace(id, randomUUID()), coach);
  await denied(422, messagePath + "?role=coach", client);
  for (const payload of [{ body: "" }, { body: "x".repeat(501) }, { body: "forged", sender_role: "COACH" }])
    await denied(422, messagePath, client, payload);
  assert.equal((await post("list", { cookie: "arcava_ui01_assignment=" + assigned.assignment_id }, coachRoute)).status, 404);
  assert.equal((await post(JSON.stringify({ body: "forged", key: randomUUID(), role: "coach" }), {}, clientRoute)).status, 422);
  assert.deepEqual(await readFile(journal), messageBytes);

  const persisted = (await readFile(journal, "utf8")).trim().split("\n").map(JSON.parse);
  const coachKey = persisted.find(entry => entry.message_id === coachSent.message.message_id).key;
  await denied(409, messagePath, coach, { body: "different intent" }, coachKey);
  const retried = await backendRequest(messagePath, coach, { body: coachSent.message.body }, coachKey);
  assert.equal(retried.status, 201);
  assert.deepEqual((await retried.json()).data, coachSent);
  assert.deepEqual(await readFile(journal), messageBytes);

  async function createAssignment(pin, key) {
    const drafts = "/project-b/v1/tenants/" + tenant + "/journeys/drafts";
    async function write(path, method, payload, idempotency) {
      const response = await fetch("http://127.0.0.1:" + backend.port + path, {
        method, body: JSON.stringify(payload), headers: { authorization: "Bearer " + coach,
          "content-type": "application/json", "idempotency-key": idempotency ?? randomUUID() },
      });
      assert.equal(response.status, method === "PATCH" ? 200 : 201);
      return (await response.json()).data;
    }
    const draft = await write(drafts, "POST", { title: "Synthetic negative fixture" });
    const path = drafts + "/" + draft.draft_id;
    await write(path, "PATCH", {
      title: "Synthetic negative fixture", expected_revision: 1,
      phases: [{ steps: [{ step_id: stepId, title: "Test step",
        canonical_refs: [{ ref_id: "kdb:protocol:test", version: "a".repeat(64) }],
        acceptance: { receipt_sha256: "a".repeat(64), approved: true, rights_granted: true } }] }],
      producer_phases: [{ steps: [{ step_id: stepId, source_ref: pin }] }],
    });
    const published = await write(path + "/publish", "POST", { expected_draft_version: 2 });
    const target = messagePath.split("/" + assigned.assignment_id)[0];
    const assignment = await write(target, "POST", { journey_version_id: published.journey_version_id }, key);
    return messagePath.replace(assigned.assignment_id, assignment.assignment_id)
      .replace(version, published.journey_version_id);
  }
  const otherTarget = await createAssignment(source);
  const beforeConflict = await readFile(journal);
  await denied(409, otherTarget, coach, { body: coachSent.message.body }, coachKey);
  assert.deepEqual(await readFile(journal), beforeConflict);
  const invalidPinTargets = [];
  for (const pin of [undefined, { ...source, relation_ids: [randomUUID()] }, ...["protocol_id", "protocol_version_id", "owning_module_id", "taxonomy_version_id"]
    .map(field => ({ ...source, [field]: randomUUID() }))]) {
    const path = await createAssignment(pin);
    invalidPinTargets.push(path);
    const beforeDeny = await readFile(journal);
    await denied(422, path, coach, { body: "denied" });
    await denied(422, path, client);
    assert.deepEqual(await readFile(journal), beforeDeny);
  }
  const beforeConsent = await readFile(journal);

  await restart("no-consent");
  assert.equal((await list("client", 422)).error.code, "CONSENT_REQUIRED");
  await denied(422, messagePath, coach, { body: "denied" });
  assert.deepEqual(await readFile(journal), beforeConsent);
  await restart();
  const clientProgress = endpoint + "/client/progress";
  const coachProgress = endpoint + "/coach/progress";
  const progress = messagePath.replace(/messages$/, "progress/");
  const own = () => click("View my step progress", 200, clientProgress);
  const coachView = status => click("View released step progress", status, coachProgress);
  const complete = () => click("Complete step", 201, clientProgress);
  const share = () => click("Share completed status with assigned coach", 201, clientProgress);
  const revoke = () => click("Withdraw progress sharing", 201, clientProgress);
  await navigate("/coach/journeys");
  await coachView(404);
  await navigate("/client/member-home");
  const completed = (await complete()).data;
  checkBinding(completed);
  assert.equal(completed.step_completed, true);
  assert.equal(completed.visibility, "PRIVATE");
  assert.equal(completed.event_id, completed.completion_id);
  assert.equal(completed.release_id, undefined);
  assert.equal(await stepTitle(), "Breathing");
  const privateBytes = await readFile(journal);
  assert.deepEqual((await complete()).data, completed);
  await navigate("/coach/journeys");
  await coachView(404);
  assert.deepEqual(await readFile(journal), privateBytes);

  await navigate("/client/member-home");
  const released = (await share()).data;
  checkBinding(released);
  assert.equal(released.completion_id, completed.completion_id);
  assert.equal(released.event_id, released.release_id);
  assert.notEqual(released.release_id, completed.completion_id);
  assert.equal(released.visibility, "RELEASED");
  const releasedBytes = await readFile(journal);
  assert.deepEqual((await share()).data, released);
  await navigate("/coach/journeys");
  const coachProjection = { assignment_id: assigned.assignment_id, journey_version_id: version,
    step_id: stepId, step_completed: true };
  assert.deepEqual((await coachView(200)).data, coachProjection);
  await cdp("Page.reload");
  await until(() => evaluate("document.querySelector(\"section[aria-label='Synthetic local journey fixture'] button\") !== null && document.querySelector('pre') === null"), "progress refresh");
  assert.deepEqual((await coachView(200)).data, coachProjection);
  await restart("replay", true);
  const restored = (await own()).data;
  assert.deepEqual(restored, Object.fromEntries(Object.entries(released).filter(([key]) => key !== "event_id")));
  await navigate("/coach/journeys");
  assert.deepEqual((await coachView(200)).data, coachProjection);

  const progressRecords = releasedBytes.toString().trim().split("\n").map(JSON.parse)
    .filter(entry => entry.op === "step_progress");
  assert.deepEqual(progressRecords.map(entry => entry.action), ["COMPLETE", "SHARE"]);
  for (const entry of progressRecords) assert.deepEqual(entry.source_ref, source);
  const [completeRecord, shareRecord] = progressRecords;
  await denied(401, progress + "released");
  await denied(401, progress + "released", randomUUID());
  await denied(403, progress.replace(tenant, randomUUID()) + "released", coach);
  await denied(403, progress + "released", otherCoach);
  await denied(403, progress + "complete", otherClient, {});
  await denied(403, progress + "complete", coach, {});
  for (const id of [assigned.assignment_id, version, stepId])
    await denied(404, progress.replace(id, randomUUID()) + "released", coach);
  await denied(422, progress + "released?actor=coach", coach);
  await denied(422, progress + "share", client, { scope: "profile" });
  await denied(422, progress + "complete", client, "malformed");
  await denied(409, progress + "share", client, { coach_id: "other" }, shareRecord.key);
  await denied(409, otherTarget.replace(/messages$/, "progress/complete"), client, {}, completeRecord.key);
  for (const path of invalidPinTargets)
    await denied(422, path.replace(/messages$/, "progress/complete"), client, {});
  assert.equal((await post("released", { origin: "http://example.invalid" }, coachProgress)).status, 403);
  assert.equal((await post("released", { authorization: "Bearer external" }, coachProgress)).status, 422);
  assert.equal((await post("released", { cookie: "arcava_ui01_assignment=" + assigned.assignment_id }, coachProgress)).status, 404);
  assert.equal((await post(JSON.stringify({ operation: "share", key: randomUUID(), role: "coach" }), {}, clientProgress)).status, 422);
  assert.deepEqual(await readFile(journal), releasedBytes);

  await restart("no-consent");
  await denied(422, progress + "complete", client, {}, completeRecord.key);
  await navigate("/coach/journeys");
  assert.equal((await coachView(422)).error.code, "CONSENT_REQUIRED");
  assert.deepEqual(await readFile(journal), releasedBytes);
  await restart();
  const revoked = (await revoke()).data;
  assert.equal(revoked.completion_id, completed.completion_id);
  assert.equal(revoked.visibility, "PRIVATE");
  assert.equal(revoked.release_id, undefined);
  const revokedBytes = await readFile(journal);
  assert.deepEqual((await revoke()).data, revoked);
  assert.ok(revokedBytes.subarray(0, releasedBytes.length).equals(releasedBytes));
  const revokedRecords = revokedBytes.toString().trim().split("\n").map(JSON.parse)
    .filter(entry => entry.op === "step_progress");
  assert.deepEqual(revokedRecords.map(entry => entry.event_id), [completed.completion_id, released.release_id, revoked.event_id]);
  assert.equal(revokedRecords[2].action, "REVOKE");
  await navigate("/coach/journeys");
  await coachView(404);
  await restart();
  assert.equal((await own()).data.completion_id, completed.completion_id);
  await navigate("/coach/journeys");
  await coachView(404);
  const shareReplay = await backendRequest(progress + "share", client, {}, shareRecord.key);
  assert.equal(shareReplay.status, 201);
  const replayed = (await shareReplay.json()).data;
  assert.equal(replayed.event_id, released.release_id);
  assert.equal(replayed.visibility, "PRIVATE");
  await coachView(404);
  assert.deepEqual(await readFile(journal), revokedBytes);

  const mediaUrl = "https://www.youtube.com/watch?v=arcavaLocal";
  const mediaTitle = "Synthetic test media";
  const coachMedia = endpoint + "/coach/media";
  const clientMedia = endpoint + "/client/media";
  const mediaPath = messagePath.replace(/messages$/, "media-links");
  async function typeMedia(url) {
    await evaluate("document.querySelector('[data-media-url]').focus()");
    await cdp("Input.insertText", { text: url });
    assert.equal(await evaluate("document.querySelector('[data-media-url]').value"), url);
  }
  await navigate("/coach/journeys");
  await typeMedia(mediaUrl);
  const attachedMedia = (await click("Attach step media link", 201, coachMedia)).data;
  checkBinding(attachedMedia);
  assert.equal(attachedMedia.media_link.url, mediaUrl);
  assert.equal(attachedMedia.media_link.title, mediaTitle);
  assert.equal(attachedMedia.media_link.owner_id, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
  assert.equal(attachedMedia.media_link.link_version, 1);
  assert.equal(attachedMedia.media_link.visibility, "ACTIVE");
  assert.equal(attachedMedia.media_link.rights_state, "SYNTHETIC_TEST_ONLY");
  assert.equal(attachedMedia.media_link.use, "EXTERNAL_NAVIGATION_ONLY");
  assert.equal(await evaluate("document.querySelector('iframe,embed,video')"), null);
  const attachedMediaBytes = await readFile(journal);
  assert.deepEqual((await click("Attach step media link", 201, coachMedia)).data, attachedMedia);
  assert.deepEqual(await readFile(journal), attachedMediaBytes);
  await navigate("/client/member-home");
  const clientMediaView = (await click("View step media link", 200, clientMedia)).data;
  assert.equal(clientMediaView.media_link.media_link_id, attachedMedia.media_link.media_link_id);
  assert.equal(clientMediaView.media_link.url, mediaUrl);
  assert.deepEqual(clientMediaView.source_ref, source);
  assert.equal(await evaluate("document.querySelector('iframe,embed,video')"), null);
  assert.equal(await stepTitle(), "Breathing");
  assert.equal(await mediaNav(), mediaUrl);
  assert.equal(await mediaTarget(), "_blank");
  assert.equal(await mediaRel(), "noopener noreferrer");
  await restart();
  const restoredMedia = (await click("View step media link", 200, clientMedia)).data;
  assert.equal(restoredMedia.media_link.media_link_id, attachedMedia.media_link.media_link_id);
  assert.equal(restoredMedia.media_link.url, mediaUrl);
  assert.equal(restoredMedia.journey_version_id, version);
  assert.equal(await mediaNav(), mediaUrl);
  assert.equal(await evaluate("document.querySelector('iframe,embed,video')"), null);
  await navigate("/coach/journeys");
  assert.equal((await click("View step media link", 200, coachMedia)).data.media_link.media_link_id,
    attachedMedia.media_link.media_link_id);
  assert.deepEqual(await readFile(journal), attachedMediaBytes);
  const youtubeFetches = events.filter(event => /youtube\.com|youtu\.be|skool\.com|googlevideo/i.test(event.response.url));
  assert.equal(youtubeFetches.length, 0);
  await denied(401, mediaPath);
  await denied(403, mediaPath.replace(tenant, randomUUID()), coach);
  await denied(403, mediaPath, otherCoach, { url: mediaUrl, title: mediaTitle });
  await denied(403, mediaPath, otherClient);
  await denied(403, mediaPath, client, { url: mediaUrl, title: mediaTitle });
  for (const id of [assigned.assignment_id, version, stepId])
    await denied(404, mediaPath.replace(id, randomUUID()), coach);
  await denied(422, mediaPath + "?provider=youtube", client);
  for (const payload of [
    { url: "http://www.youtube.com/watch?v=arcavaLocal", title: mediaTitle },
    { url: "javascript:alert(1)", title: mediaTitle },
    { url: "https://user:pass@www.youtube.com/watch?v=arcavaLocal", title: mediaTitle },
    { url: "https://www.youtube.com.evil.com/watch?v=arcavaLocal", title: mediaTitle },
    { url: "https://vimeo.com/123", title: mediaTitle },
    { url: "https://127.0.0.1/watch", title: mediaTitle },
    { url: mediaUrl, title: "x".repeat(121) },
  ]) await denied(422, mediaPath, coach, payload);
  const mediaRecords = attachedMediaBytes.toString().trim().split("\n").map(JSON.parse)
    .filter(entry => entry.op === "coach_media_link_attach");
  assert.equal(mediaRecords.length, 1);
  await denied(409, mediaPath, coach, { url: "https://www.skool.com/arcava-synthetic", title: mediaTitle },
    mediaRecords[0].key);
  assert.equal((await post("list", { origin: "http://example.invalid" }, coachMedia)).status, 403);
  assert.equal((await post("list", { authorization: "Bearer external" }, coachMedia)).status, 422);
  assert.equal((await post(JSON.stringify({ url: mediaUrl, title: mediaTitle, key: randomUUID() }), {}, clientMedia)).status, 422);
  assert.deepEqual(await readFile(journal), attachedMediaBytes);

  const withdrawnMedia = (await click("Withdraw step media link", 201, coachMedia)).data;
  assert.equal(withdrawnMedia.media_link.media_link_id, attachedMedia.media_link.media_link_id);
  assert.equal(withdrawnMedia.media_link.visibility, "WITHDRAWN");
  const withdrawnMediaBytes = await readFile(journal);
  assert.deepEqual((await click("Withdraw step media link", 201, coachMedia)).data, withdrawnMedia);
  assert.deepEqual(await readFile(journal), withdrawnMediaBytes);
  await navigate("/client/member-home");
  assert.equal((await click("View step media link", 404, clientMedia)).error.code, "NOT_FOUND");
  assert.equal(await mediaNav(), null);
  await restart();
  assert.equal((await click("View step media link", 404, clientMedia)).error.code, "NOT_FOUND");
  assert.equal(await mediaNav(), null);
  await navigate("/coach/journeys");
  assert.equal((await click("View step media link", 404, coachMedia)).error.code, "NOT_FOUND");
  const mediaHistory = withdrawnMediaBytes.toString().trim().split("\n").map(JSON.parse)
    .filter(entry => entry.op === "coach_media_link_attach" || entry.op === "coach_media_link_withdraw");
  assert.deepEqual(mediaHistory.map(entry => entry.op),
    ["coach_media_link_attach", "coach_media_link_withdraw"]);
  assert.equal(mediaHistory[0].media_link_id, attachedMedia.media_link.media_link_id);
  assert.deepEqual(mediaHistory[0].source_ref, source);

  const withdrawal = await fetch("http://127.0.0.1:" + backend.port + "/project-b/v1/tenants/" + tenant
    + "/journeys/versions/" + version + "/withdraw",
    { method: "POST", body: "{}", headers: { authorization: "Bearer " + coach, "content-type": "application/json" } });
  assert.equal(withdrawal.status, 200);
  await denied(422, progress + "released", coach);
  await denied(422, progress + "share", client, {});
  await navigate("/client/member-home");
  const withdrawn = await readFile(journal);
  assert.equal((await click("Open assigned step", 422)).error.code, "WITHDRAWN");
  assert.equal(await stepTitle(), null);
  assert.equal(await mediaNav(), null);
  assert.deepEqual(await readFile(journal), withdrawn);
  assert.equal((await list("client", 422)).error.code, "WITHDRAWN");
  await denied(422, messagePath, coach, { body: "denied" });
  await denied(422, mediaPath, client);
  await denied(422, mediaPath, coach, { url: mediaUrl, title: mediaTitle });
  await restart();
  assert.equal((await click("Open assigned step", 422)).error.code, "WITHDRAWN");
  assert.equal(await stepTitle(), null);
  assert.equal(await mediaNav(), null);
  assert.deepEqual(await readFile(journal), withdrawn);
  assert.equal((await list("client", 422)).error.code, "WITHDRAWN");
  await denied(422, messagePath, client, { body: "denied" });
  assert.deepEqual(await readFile(journal), withdrawn);
  await denied(422, progress + "released", coach);
  await denied(422, progress + "share", client, {});
  assert.deepEqual(await readFile(journal), withdrawn);
  console.log(JSON.stringify({ progress: {
    completion_id: completed.completion_id, release_id: released.release_id, revoke_id: revoked.event_id,
    private_before_share: true, coach_projection: coachProjection, historical_events: ["COMPLETE", "SHARE", "REVOKE"],
    consent_denied: true, withdrawal_denied_before_after_replay: true, partial_tail_discarded: true,
    old_share_retry_stayed_revoked: true, same_key_changed_target_or_audience: 409,
  }, messaging: { coachSent: coachSent.message, clientSent: clientSent.message,
    ordered_replay: true, current_consent_denied: true, message_retry_conflict: true, changed_target_conflict: true, missing_or_swapped_pin_denied: true, negative_binding_cases: true },
    media: {
      media_link_id: attachedMedia.media_link.media_link_id, link_version: 1, url: mediaUrl,
      client_saw_active: true, restart_preserved: true, withdrawn_hidden: true,
      history_retained: true, no_external_fetch: true, invalid_url_denied: true,
      clickable_https_only_when_active: true, no_link_after_withdraw_or_restart_404: true,
    },
    assigned_step: {
      visible_title: "Breathing", stable_through_messages_progress_media: true,
      test_only: true, no_live_kdb: true, source_pin: "PA-05",
    },
    result: "PASS", browser: await evaluate("navigator.userAgent"),
    assignment_id: assigned.assignment_id, journey_version_id: version, step_id: stepId, source_ref: source,
    assign_http: 201, open_http: 200, withdrawn_http: 422, refresh: true, service_process_restart: true,
    stable_idempotency: true, journal_bytes_preserved: true, cross_origin_denied: true, foreign_host_denied: true }));
} finally {
  socket?.close();
  await Promise.all([...children].map(child => stop(child)));
  await rm(work, { recursive: true, force: true });
}
