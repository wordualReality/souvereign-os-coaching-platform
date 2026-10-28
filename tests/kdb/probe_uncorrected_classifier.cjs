'use strict';
// Prove the historical classifier accepts missing tenant_scope. Not live source.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const js = fs.readFileSync(
  path.join(__dirname, 'fixtures', 'uncorrected_fail_closed_classify_o1.js'),
  'utf8'
);
const fixture = JSON.parse(
  fs.readFileSync(
    path.join(
      __dirname,
      '..',
      '..',
      'n8n',
      'kdb-dev',
      'tenant-guard-candidate',
      'fixtures',
      'FX-01-positive-valid.json'
    ),
    'utf8'
  )
);
const body = JSON.parse(JSON.stringify(fixture.body));
delete body.tenant_scope;
const ctx = vm.createContext({ $input: { first: () => ({ json: body }) } });
const actual = vm.runInContext('(function(){\n' + js + '\n})()', ctx, { timeout: 250 })[0].json.route;
const report = {
  probe: 'uncorrected_missing_tenant_scope',
  expected_if_live: 'DENY',
  actual,
  historical_defect: actual !== 'DENY',
};
process.stdout.write(JSON.stringify(report) + '\n');
if (!report.historical_defect) process.exitCode = 1;
