'use strict';
// Offline replay / retry / DLQ policy against fixture metadata.
// Does not execute n8n, HTTP, or SQL.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(process.argv[2] || path.join(__dirname, 'tenant-guard-candidate'));
const OUTPUT = path.resolve(process.argv[3] || path.join(__dirname, '..', 'replay-dlq-results.json'));

const NEVER_RETRY = new Set([
  'DENIED',
  'REVOKED',
  'RIGHTS_RESTRICTED',
  'CONFLICT',
  'INJECTION',
  'POISON',
  'UNKNOWN_COMMIT',
]);
const TRANSIENT = new Set(['UNAVAILABLE', 'RATE_LIMIT', 'TIMEOUT']);

function loadJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, rel), 'utf8'));
}

function digest(body) {
  const copy = JSON.parse(JSON.stringify(body));
  delete copy.synthetic_fault_class;
  return crypto.createHash('sha256').update(JSON.stringify(copy)).digest('hex');
}

function errorClass(fixture) {
  if (fixture.body && fixture.body.synthetic_fault_class) return fixture.body.synthetic_fault_class;
  if (fixture.expected_transport_class) return fixture.expected_transport_class;
  return null;
}

function terminalQueue(fixture) {
  if (fixture.expected_transport_route) return fixture.expected_transport_route;
  return fixture.expected_route;
}

function retryAllowed(error) {
  if (!error) return false;
  if (NEVER_RETRY.has(error)) return false;
  return TRANSIENT.has(error);
}

const fixtures = fs
  .readdirSync(path.join(ROOT, 'fixtures'))
  .filter((name) => name.endsWith('.json'))
  .sort()
  .map((name) => ({ name, data: loadJson('fixtures/' + name) }));

const cases = [];
for (const item of fixtures) {
  const error = errorClass(item.data);
  const queue = terminalQueue(item.data);
  const allowed = retryAllowed(error);
  if (NEVER_RETRY.has(error) && allowed) {
    cases.push({ fixture: item.name, pass: false, reason: 'never-retry class marked retryable' });
    continue;
  }
  if (TRANSIENT.has(error) && queue !== 'DLQ' && queue !== 'QUARANTINE') {
    cases.push({ fixture: item.name, pass: false, reason: 'transient class missing terminal queue' });
    continue;
  }
  cases.push({
    fixture: item.name,
    error_class: error,
    terminal_queue: queue,
    retry_allowed: allowed,
    bounded_retry: allowed ? 'TRANSIENT_ONLY_UNTIL_OWNER_BUDGET' : 'NONE',
    pass: true,
  });
}

const receipts = new Map();
function record(key, bodyDigest) {
  if (receipts.has(key)) {
    return receipts.get(key) === bodyDigest ? 'REPLAY' : 'CONFLICT';
  }
  receipts.set(key, bodyDigest);
  return 'ACCEPT';
}

const fx04 = fixtures.find((item) => item.name === 'FX-04-duplicate-same-body.json').data;
const first = record(fx04.body.idempotency_key, digest(fx04.body));
const replay = record(fx04.body.idempotency_key, digest(fx04.body));
const conflictBody = JSON.parse(JSON.stringify(fx04.body));
conflictBody.payload.content_fingerprint = 'b'.repeat(64);
const conflict = record(fx04.body.idempotency_key, digest(conflictBody));

const receiptCases = [
  { name: 'first_accept', actual: first, expected: 'ACCEPT', pass: first === 'ACCEPT' },
  { name: 'same_body_replay', actual: replay, expected: 'REPLAY', pass: replay === 'REPLAY' },
  { name: 'different_body_conflict', actual: conflict, expected: 'CONFLICT', pass: conflict === 'CONFLICT' },
];

const report = {
  root: path.basename(ROOT),
  policy_cases: cases,
  receipt_cases: receiptCases,
  counts: {
    policy: cases.length,
    policy_pass: cases.filter((row) => row.pass).length,
    receipt_pass: receiptCases.filter((row) => row.pass).length,
  },
  acceptance: {
    offline_replay_dlq_policy: cases.every((row) => row.pass) && receiptCases.every((row) => row.pass) ? 'PASS' : 'FAIL',
    n8n_runtime: 'NOT_RUN',
    numeric_retry_budget: 'NOT_INVENTED',
  },
};

fs.writeFileSync(OUTPUT, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ counts: report.counts, acceptance: report.acceptance }, null, 2));
if (report.acceptance.offline_replay_dlq_policy !== 'PASS') process.exitCode = 1;
