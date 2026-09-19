// Validates the contracts: proto lint + rule-pack JSON Schema vs all samples.
// Usage: node scripts/check-contracts.js
const Ajv2020 = require('ajv/dist/2020'); // rulepack schema is draft 2020-12
const addFormats = require('ajv-formats');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const CONTRACTS = path.join(ROOT, 'contracts');

// 1. proto lint via buf
console.log('== buf lint ==');
execFileSync('npx', ['buf', 'lint', 'proto', '--config', 'buf.yaml'], {
  cwd: CONTRACTS, stdio: 'inherit',
});
console.log('proto: OK');

// 2. JSON Schema vs samples
console.log('== rulepack schema ==');
const schema = JSON.parse(
  fs.readFileSync(path.join(CONTRACTS, 'rulepack', 'v1', 'rulepack.schema.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile(schema);
const samples = fs.readdirSync(path.join(CONTRACTS, 'samples'))
  .filter(f => f.endsWith('.json'))
  .map(f => path.join(CONTRACTS, 'samples', f));
let failed = false;
for (const s of samples) {
  const pack = JSON.parse(fs.readFileSync(s, 'utf8'));
  if (!validate(pack)) {
    failed = true;
    console.error('FAIL', path.basename(s), JSON.stringify(validate.errors, null, 2));
  } else {
    console.log('ok  ', path.basename(s));
  }
}
if (failed) process.exit(1);
console.log('contracts: ALL OK');
