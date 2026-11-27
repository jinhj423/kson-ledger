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

import { eventsFor, heroSentence } from '../src/ui.js';

const SERIES = [
  { d: '11.05 (목)', v: -10, txt: '−10억' },
  { d: '11.06 (금)', v: 78.3, txt: '+78.3억' },
  { d: '11.09 (월)', v: 5, txt: '+5억' },
];

test('eventsFor places events of this market on chart days and skips the rest', () => {
  const evs = [
    { kr: '2026-11-06', us: '2026-11-05', cat: '시장', imp: 3, t: 'A', x: 'a', src: [] },
    { kr: '2026-11-08', cat: '금리', imp: 3, t: 'weekend', x: 'b', src: [] },
    { us: '2026-11-09', cat: '금리', imp: 2, t: 'us only', x: 'c', src: [] },
  ];
  const kr = eventsFor('kr', SERIES, evs);
  assert.equal(kr.length, 1);
  assert.equal(kr[0].i, 1);
  assert.equal(kr[0].t, 'A');
  const us = eventsFor('us', SERIES, evs);
  assert.deepEqual(us.map((e) => e.i), [0, 2]);
});

test('heroSentence says which way insiders leaned', () => {
  assert.equal(heroSentence('kr', -260.8), '내부자들이 산 것보다 261억 원 더 팔았어요.');
  assert.equal(heroSentence('kr', 45.2), '내부자들이 판 것보다 45.2억 원 더 샀어요.');
  assert.equal(heroSentence('us', 12.5), '내부자들이 판 것보다 $12.5M 더 샀어요.');
  assert.equal(heroSentence('kr', 0), '산 금액과 판 금액이 같아요.');
});

import { fullMoney } from '../src/ui.js';

test('fullMoney writes the whole amount with commas', () => {
  assert.deepEqual(fullMoney('kr', { netAmt: -26083412345 }, -260.8), { txt: '−26,083,412,345', unit: '원' });
  assert.deepEqual(fullMoney('kr', { netAmt: 0 }, 0), { txt: '0', unit: '원' });
  assert.deepEqual(fullMoney('us', { netAmt: 71612345678 }, 71612.3), { txt: '+$71,612,345,678', unit: '' });
  // older data without the exact field: rebuilt from the rounded total
  assert.deepEqual(fullMoney('kr', {}, -260.8), { txt: '−26,080,000,000', unit: '원' });
  assert.deepEqual(fullMoney('us', {}, 12.5), { txt: '+$12,500,000', unit: '' });
});
