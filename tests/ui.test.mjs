// Run: node --test tests/ui.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { kindLabel, magnitude, prevNetText } from '../src/ui.js';

test('magnitude reads Korean and US amount strings', () => {
  assert.equal(magnitude('+353억'), 353);
  assert.equal(magnitude('−1.2조'), 12000);
  assert.equal(magnitude('+5,116만'), 0.5116);
  assert.equal(magnitude('+$103.9B'), 103900);
  assert.equal(magnitude('−$4.2M'), 4.2);
  assert.equal(magnitude('$14K'), 0.014);
  assert.equal(magnitude('—'), 0);
});

test('prevNetText recovers the earlier period total', () => {
  assert.equal(prevNetText('kr', { net: -260.8, diffTxt: '285억', diffUp: true }), '−546억');
  assert.equal(prevNetText('kr', { net: 120, diffTxt: '30억', diffUp: false }), '+150억');
  assert.equal(prevNetText('us', { net: 12.5, diffTxt: '$2.5M', diffUp: true }), '+$10.0M');
});

test('kindLabel names the report type and its colour', () => {
  assert.deepEqual(kindLabel({ kind: 'buy', dk: 'buy' }), ['장내매수', 'buy']);
  assert.deepEqual(kindLabel({ kind: 'sell', dk: 'sell' }), ['장내매도', 'sell']);
  assert.deepEqual(kindLabel({ kind: 'mixed', dk: 'sell' }), ['매수와 매도', 'sell']);
  assert.deepEqual(kindLabel({ kind: 'major', dk: 'muted' }), ['5% 보고', '']);
  assert.deepEqual(kindLabel({ kind: 'other', dk: 'muted' }), ['소유 변동', '']);
});
