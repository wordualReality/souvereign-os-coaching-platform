import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, execFileSync } from "node:child_process";
import { once } from "node:events";

const root = new URL("../../../", import.meta.url);
process.chdir(fileURLToPath(root));
const work = await mkdtemp(join(tmpdir(), "arcava-c19-smoke-"));
const journal = join(work, "journal.ndjson");
const classes = join(work, "classes");
const coach = randomUUID();
const client = randomUUID();
const env = {
  ...process.env, NEXT_TELEMETRY_DISABLED: "1",
  ARCAVA_UI01_COACH_BEARER: coach, ARCAVA_UI01_CLIENT_BEARER: client,
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
const endpoint = origin + "/api/arcava-c19";

async function web(servicePort, version) {
  const child = launch(process.execPath, ["node_modules/next/dist/bin/next", "start",
    "apps/web", "--hostname", "127.0.0.1", "--port", String(port)], {
    env: { ...env, ARCAVA_UI01_MODE: "TEST_LOOPBACK_ONLY", ARCAVA_UI01_SERVICE_PORT: servicePort,
      ARCAVA_UI01_VERSION: version },
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
    ...["domain/JourneyKernel", "domain/JourneyJournal", "domain/C19LocalReview", "domain/GoalProposalAdapter", "json/JsonMini",
      "http/JourneyHttpServer", "http/JourneyProducer", "http/TrustedKdbVerifier", "http/TrustedPiacVerifier"]
      .map(name => src + "main" + pkg + name + ".java"),
    ...["JourneyPathTest", "JourneyUiFixture"].map(name => src + "test" + pkg + "http/" + name + ".java"),
  ], { stdio: "inherit" });

  let backend = await service("seed");
  const version = backend.version;
  let next = await web(backend.port, version);
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
  const failures = [];
  let sequence = 0;
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    const command = commands.get(message.id);
    if (command) {
      commands.delete(message.id);
      if (message.error) command.reject(new Error(message.error.message));
      else command.resolve(message.result);
    } else if (message.method === "Network.responseReceived") events.push(message.params);
    else if (message.method === "Network.loadingFailed") failures.push(message.params);
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
  async function navigate() {
    await cdp("Page.navigate", { url: origin + "/coach/journeys" });
    await until(() => evaluate("location.pathname === '/coach/journeys' && document.querySelector('[data-c19-goal]') !== null"),
      "/coach/journeys");
  }
  const c19 = "[aria-label='C19 local goal draft fixture']";
  async function click(label, status) {
    const start = events.length;
    const done = await evaluate(`(() => {
      const button = Array.from(document.querySelectorAll(${JSON.stringify(c19 + " button")}))
        .find(candidate => candidate.textContent.trim() === ${JSON.stringify(label)} && !candidate.disabled);
      if (!button) return false;
      button.scrollIntoView({block:"center"});
      button.click();
      return true;
    })()`);
    assert.equal(done, true, "enabled control: " + label);
    const wire = await until(() => events.slice(start).find(event => event.response.url === endpoint), "C19 response");
    assert.equal(wire.response.status, status);
    await until(() => evaluate("document.querySelector('[data-c19-status]')?.textContent?.startsWith('HTTP " + status + "')"),
      "visible C19 status");
    const raw = await cdp("Network.getResponseBody", { requestId: wire.requestId });
    return JSON.parse(raw.body);
  }

  async function press(label) {
    const done = await evaluate(`(() => {
      const button = Array.from(document.querySelectorAll(${JSON.stringify(c19 + " button")}))
        .find(candidate => candidate.textContent.trim() === ${JSON.stringify(label)} && !candidate.disabled);
      if (!button) return false;
      button.click();
      return true;
    })()`);
    assert.equal(done, true, "local control: " + label);
  }

  await navigate();
  const proposed = await click("Propose sourced outline", 200);
  assert.equal(proposed.data.steps.length, 3);
  assert.equal(proposed.data.publication_state, "UNSAVED_PREVIEW");
  assert.equal(await evaluate("document.querySelector('[data-c19-steps]').getAttribute('data-c19-steps')"), "3");
  await evaluate(`(() => {
    const input = document.querySelector(${JSON.stringify(c19 + " li input")});
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    setter.call(input, "Settle slowly");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  })()`);
  assert.equal(await evaluate("document.querySelector('[data-c19-step] input').value"), "Settle slowly");
  await evaluate(`(() => {
    const input = document.querySelector("[data-c19-title]");
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    setter.call(input, "Edited calm draft");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  })()`);
  assert.equal(await evaluate("document.querySelector('[data-c19-title]').value"), "Edited calm draft");
  await press("Move down");
  await press("Remove step");
  await until(() => evaluate("document.querySelector('[data-c19-steps]').getAttribute('data-c19-steps') === '2'"), "removed step");
  const saved = await click("Save draft", 201);
  assert.equal(saved.data.status, "draft");
  assert.equal(saved.data.title, "Edited calm draft");
  assert.equal(saved.data.steps.length, 2);
  assert.equal(saved.data.publication_state, "DRAFT");
  const draftId = saved.data.draft_id;
  const revision = saved.data.revision;
  const bytes = await readFile(journal);
  assert.equal(bytes.toString().includes('"op":"publish"') && bytes.toString().split('"op":"publish"').length === 2, true);

  await stop(next);
  await stop(backend.child);
  backend = await service("replay");
  next = await web(backend.port, version);
  await navigate();
  const restored = await click("Reload saved draft", 200);
  assert.equal(restored.data.draft_id, draftId);
  assert.equal(restored.data.revision, revision);
  assert.equal(restored.data.steps.length, 2);
  assert.equal(restored.data.publication_state, "DRAFT");
  assert.equal(await evaluate("document.querySelector('[data-c19-steps]').getAttribute('data-c19-steps')"), "2");
  assert.equal(await evaluate("document.querySelectorAll('[data-c19-hash]').length"), 2);
  assert.equal(await evaluate("document.querySelector('[data-c19-title]').value"), "Edited calm draft");
  assert.equal(restored.data.title, "Edited calm draft");
  assert.equal(restored.data.origin, "C19_GOAL_DRAFT");
  assert.match(String(restored.data.digest ?? ""), /^[0-9a-f]{64}$/);
  assert.equal(restored.data.review_state, "NONE");
  assert.equal(await evaluate("document.querySelector('[data-c19-review-label]')?.textContent"),
    "LOCAL TEST REVIEW, NOT PUBLISHING");
  assert.equal(await evaluate("document.querySelector('[data-c19-dirty]').getAttribute('data-c19-dirty')"), "false");
  const reviewed = await click("Confirm local review", 201);
  assert.equal(reviewed.data.review_state, "ACCEPTED");
  assert.equal(reviewed.data.digest, restored.data.digest);
  assert.equal(reviewed.data.publication_state, "DRAFT");
  assert.ok(reviewed.data.review_receipt?.reviewer_id);
  assert.equal(await evaluate("document.querySelector('[data-c19-review-state]').getAttribute('data-c19-review-state')"),
    "ACCEPTED");
  const journalAfterReview = await readFile(journal);
  assert.equal(journalAfterReview.toString().includes('"op":"c19_local_review"'), true);
  assert.equal(journalAfterReview.toString().includes('"op":"publish"')
    && journalAfterReview.toString().split('"op":"publish"').length === 2, true);

  await stop(next);
  await stop(backend.child);
  backend = await service("replay");
  next = await web(backend.port, version);
  await navigate();
  const reviewRestored = await click("Reload saved draft", 200);
  assert.equal(reviewRestored.data.draft_id, draftId);
  assert.equal(reviewRestored.data.revision, revision);
  assert.equal(reviewRestored.data.review_state, "ACCEPTED");
  assert.equal(reviewRestored.data.digest, restored.data.digest);
  assert.equal(reviewRestored.data.title, "Edited calm draft");
  assert.equal(await evaluate("document.querySelector('[data-c19-title]').value"), "Edited calm draft");

  await evaluate(`(() => {
    const input = document.querySelector("[data-c19-title]");
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    setter.call(input, "Unsaved review edit");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  })()`);
  assert.equal(await evaluate("document.querySelector('[data-c19-dirty]').getAttribute('data-c19-dirty')"), "true");
  await press("Confirm local review");
  await until(() => evaluate("document.querySelector('[data-c19-status]')?.textContent === 'HTTP 422 UNSAVED_CHANGES'"),
    "unsaved review refused");
  assert.equal(await evaluate("document.querySelector('[data-c19-review-state]').getAttribute('data-c19-review-state')"),
    "ACCEPTED");
  const reloadedClean = await click("Reload saved draft", 200);
  assert.equal(reloadedClean.data.review_state, "ACCEPTED");
  assert.equal(reloadedClean.data.title, "Edited calm draft");

  const resaved = await click("Save draft", 201);
  assert.equal(resaved.data.draft_id, draftId);
  assert.equal(resaved.data.title, "Edited calm draft");
  assert.ok(resaved.data.revision >= revision);
  assert.equal(resaved.data.review_state, "INEFFECTIVE");
  const liveRevision = resaved.data.revision;
  const acceptedAgain = await click("Confirm local review", 201);
  assert.equal(acceptedAgain.data.review_state, "ACCEPTED");
  assert.equal(acceptedAgain.data.revision, liveRevision);
  assert.notEqual(acceptedAgain.data.digest, restored.data.digest);
  const journalAfterSave = await readFile(journal);
  const failed = await click("Simulate adapter failure", 503);
  assert.equal(failed.error.code, "ADAPTER_UNAVAILABLE");
  assert.equal(failed.error.retryable, true);
  assert.equal(await evaluate("document.querySelector('[data-c19-notice]')?.textContent?.includes('temporarily unavailable')"), true);
  const timedOut = await click("Simulate fetch timeout", 503);
  assert.equal(timedOut.error.code, "FIXTURE_UNAVAILABLE");
  assert.equal(timedOut.error.retryable, true);
  assert.equal(await evaluate("document.querySelector('[data-c19-notice]')?.textContent?.includes('temporarily unavailable')"), true);
  assert.equal(await evaluate("document.querySelector('[data-c19-title]').value"), "Edited calm draft");
  const still = await click("Reload saved draft", 200);
  assert.equal(still.data.draft_id, draftId);
  assert.equal(still.data.revision, liveRevision);
  assert.equal(still.data.steps.length, 2);
  assert.equal(still.data.title, "Edited calm draft");
  assert.equal(still.data.review_state, "ACCEPTED");
  assert.equal(await evaluate("document.querySelector('[data-c19-title]').value"), "Edited calm draft");
  const reviewFailStart = failures.length;
  await cdp("Network.setBlockedURLs", { urls: [endpoint, "*/api/arcava-c19*"] });
  await press("Confirm local review");
  await until(() => evaluate("document.querySelector('[data-c19-status]')?.textContent === 'HTTP 0 FETCH_REJECTED'"),
    "rejected review fetch");
  assert.equal(await evaluate("document.querySelector('[data-c19-notice]')?.textContent?.includes('temporarily unavailable')"), true);
  assert.equal(await evaluate("document.querySelector('[data-c19-review-state]').getAttribute('data-c19-review-state')"),
    "ACCEPTED");
  assert.equal(await evaluate("document.querySelector('[data-c19-title]').value"), "Edited calm draft");
  assert.ok(failures.slice(reviewFailStart).find(event => (event.errorText || event.blockedReason || "").length > 0));
  await cdp("Network.setBlockedURLs", { urls: [] });
  const failStart = failures.length;
  const responseStart = events.length;
  await cdp("Network.setBlockedURLs", { urls: [endpoint, "*/api/arcava-c19*"] });
  await press("Propose sourced outline");
  await until(() => evaluate("document.querySelector('[data-c19-status]')?.textContent === 'HTTP 0 FETCH_REJECTED'"),
    "rejected fetch status");
  assert.equal(await evaluate("document.querySelector('[data-c19-notice]')?.textContent?.includes('temporarily unavailable')"), true);
  assert.equal(await evaluate("document.querySelector('[data-c19-title]').value"), "Edited calm draft");
  assert.equal(await evaluate("document.querySelector('[data-c19-steps]').getAttribute('data-c19-steps')"), "2");
  assert.equal(await evaluate("document.querySelectorAll('[data-c19-hash]').length"), 2);
  assert.equal(await evaluate(`Array.from(document.querySelectorAll(${JSON.stringify(c19 + " button")}))
    .some(button => button.textContent.trim() === "Reload saved draft" && !button.disabled)`), true);
  assert.equal(events.slice(responseStart).some(event => event.response.url === endpoint && event.response.status === 503), false);
  const rejected = failures.slice(failStart).find(event =>
    (event.errorText || event.blockedReason || "").length > 0);
  assert.ok(rejected, "CDP Network.loadingFailed for blocked C19 fetch");
  assert.deepEqual(await readFile(journal), journalAfterSave);
  await cdp("Network.setBlockedURLs", { urls: [] });
  const recovered = await click("Reload saved draft", 200);
  assert.equal(recovered.data.draft_id, draftId);
  assert.equal(recovered.data.revision, liveRevision);
  assert.equal(recovered.data.title, "Edited calm draft");
  assert.equal(await evaluate("document.querySelector('[data-c19-title]').value"), "Edited calm draft");
  console.log(JSON.stringify({
    result: "PASS",
    draft_id: draftId,
    revision: liveRevision,
    title: recovered.data.title,
    steps: recovered.data.steps.length,
    a1_preview: true, a2_edit_save: true, a3_restart: true, a3_title_restored: true,
    a3_save_after_restart: true,
    a7_adapter_error: true, a7_fetch_timeout: true,
    a7_browser_fetch_rejected: true,
    r01_review: true, r02_restart: true, r03_unsaved_and_invalidate: true, r07_review_fetch_rejected: true,
    loading_failed: rejected.errorText || rejected.blockedReason,
    test_only: true, no_live_kdb: true,
  }));
} finally {
  socket?.close();
  await Promise.all([...children].map(child => stop(child)));
  await rm(work, { recursive: true, force: true });
}
