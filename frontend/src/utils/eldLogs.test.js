import assert from 'node:assert/strict'
import test from 'node:test'
import { createEldLogs } from './eldLogs.js'

const chicagoTimeline = [
  { type: 'DRIVING', start_hour: 0, end_hour: 3.613, duration_hours: 3.613 },
  { type: 'PICKUP', start_hour: 3.613, end_hour: 4.613, duration_hours: 1 },
  { type: 'DRIVING', start_hour: 4.613, end_hour: 12, duration_hours: 7.387 },
  { type: 'SLEEPER', start_hour: 12, end_hour: 22, duration_hours: 10 },
  { type: 'DRIVING', start_hour: 22, end_hour: 24.450694, duration_hours: 2.450694 },
  { type: 'DROPOFF', start_hour: 24.450694, end_hour: 25.450694, duration_hours: 1 },
]

const chicagoLocations = {
  pickup: { name: 'Indianapolis, IN' },
  dropoff: { name: 'Atlanta, GA' },
}

test('creates one complete 24-hour sheet for a trip no longer than one day', () => {
  const logs = createEldLogs([{ type: 'DRIVING', start_hour: 0, end_hour: 8 }], 8)
  assert.equal(logs.length, 1)
  assert.equal(logs[0].total_hours, 24)
  assert.equal(logs[0].totals.DRIVING, 8)
  assert.equal(logs[0].totals.OFF_DUTY, 16)
})

test('splits the Chicago example into two days with the expected totals and remarks', () => {
  const logs = createEldLogs(chicagoTimeline, 25.450694, chicagoLocations)
  assert.equal(logs.length, 2)
  assert.deepEqual(logs.map((day) => day.total_hours), [24, 24])
  assert.ok(Math.abs(logs[0].totals.DRIVING - 13) < 1e-8)
  assert.ok(Math.abs(logs[0].totals.ON_DUTY - 1) < 1e-9)
  assert.equal(logs[0].totals.SLEEPER_BERTH, 10)
  assert.ok(Math.abs(logs[0].totals.OFF_DUTY) < 1e-8)
  assert.ok(Math.abs(logs[1].totals.DRIVING - 0.450694) < 1e-8)
  assert.ok(Math.abs(logs[1].totals.ON_DUTY - 1) < 1e-9)
  assert.ok(Math.abs(logs[1].totals.OFF_DUTY - 22.549306) < 1e-8)
  assert.equal(logs[1].totals.SLEEPER_BERTH, 0)
  assert.ok(logs[0].remarks.some((item) => item.label === 'Pickup' && item.location === 'Indianapolis, IN'))
  assert.ok(logs[1].remarks.some((item) => item.label === 'Dropoff' && item.location === 'Atlanta, GA'))
})

test('splits a midnight-crossing driving event without losing or duplicating time', () => {
  const logs = createEldLogs([
    { type: 'SLEEPER', start_hour: 0, end_hour: 22 },
    { type: 'DRIVING', start_hour: 22, end_hour: 24.450694 },
    { type: 'DROPOFF', start_hour: 24.450694, end_hour: 25.450694 },
  ], 25.450694)
  const driving = logs.map((day) => day.segments.filter((segment) => segment.status === 'DRIVING')
    .reduce((sum, segment) => sum + segment.end_hour - segment.start_hour, 0))
  assert.deepEqual(driving.map((hours) => Number(hours.toFixed(6))), [2, 0.450694])
  assert.ok(Math.abs(driving.reduce((sum, hours) => sum + hours, 0) - 2.450694) < 1e-9)
  assert.equal(logs[0].segments.at(-1).end_hour, 24)
  assert.equal(logs[1].segments[0].start_hour, 0)
})

test('maps the HOS event kinds to the four standard duty rows', () => {
  const events = [
    ['BREAK', 'OFF_DUTY'],
    ['SLEEPER', 'SLEEPER_BERTH'],
    ['DRIVING', 'DRIVING'],
    ['PICKUP', 'ON_DUTY'],
    ['DROPOFF', 'ON_DUTY'],
    ['FUEL', 'ON_DUTY'],
  ].map(([type], index) => ({ type, start_hour: index * 0.5, end_hour: (index + 1) * 0.5 }))
  const log = createEldLogs(events, 3)[0]
  for (const [type, status] of [
    ['BREAK', 'OFF_DUTY'], ['SLEEPER', 'SLEEPER_BERTH'], ['DRIVING', 'DRIVING'],
    ['PICKUP', 'ON_DUTY'], ['DROPOFF', 'ON_DUTY'], ['FUEL', 'ON_DUTY'],
  ]) {
    const matching = log.segments.find((segment) => segment.events.some(({ event }) => event.type === type))
    assert.equal(matching.status, status, `${type} maps to ${status}`)
  }
  assert.equal(log.total_hours, 24)
})

test('fills the post-trip portion of the last sheet as off duty', () => {
  const [log] = createEldLogs([
    { type: 'DRIVING', start_hour: 0, end_hour: 0.45 },
    { type: 'DROPOFF', start_hour: 0.45, end_hour: 1.45 },
  ], 1.45)
  const remainder = log.segments.find((segment) => segment.status === 'OFF_DUTY')
  assert.equal(remainder.start_hour, 1.45)
  assert.equal(remainder.end_hour, 24)
  assert.ok(Math.abs(log.totals.OFF_DUTY - 22.55) < 1e-9)
  assert.equal(log.total_hours, 24)
})
