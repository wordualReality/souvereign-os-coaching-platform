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
    ...["domain/JourneyKernel", "domain/JourneyJournal", "domain/GoalProposalAdapter", "json/JsonMini",
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
  let sequence = 0;
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    const command = commands.get(message.id);
    if (command) {
      commands.delete(message.id);
      if (message.error) command.reject(new Error(message.error.message));
      else command.resolve(message.result);
    } else if (message.method === "Network.responseReceived") events.push(message.params);
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
  assert.equal(still.data.revision, revision);
  assert.equal(still.data.steps.length, 2);
  assert.equal(still.data.title, "Edited calm draft");
  assert.equal(await evaluate("document.querySelector('[data-c19-title]').value"), "Edited calm draft");
  console.log(JSON.stringify({
    result: "PASS",
    draft_id: draftId,
    revision,
    title: still.data.title,
    steps: still.data.steps.length,
    a1_preview: true, a2_edit_save: true, a3_restart: true, a3_title_restored: true,
    a7_adapter_error: true, a7_fetch_timeout: true,
    test_only: true, no_live_kdb: true,
  }));
} finally {
  socket?.close();
  await Promise.all([...children].map(child => stop(child)));
  await rm(work, { recursive: true, force: true });
}
