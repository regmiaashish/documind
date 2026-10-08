import test from 'node:test';
import assert from 'node:assert/strict';
import { consumeEvents } from '../src/lib/sse.mjs';

function response(text, size = 1) {
  const bytes = new TextEncoder().encode(text);
  return new Response(new ReadableStream({ start(controller) {
    for (let index = 0; index < bytes.length; index += size) controller.enqueue(bytes.slice(index, index + size));
    controller.close();
  }}));
}

test('decodes fragmented UTF-8 and CRLF frames', async () => {
  const events = [];
  await consumeEvents(response('event: token\r\ndata: {"text":"नमस्ते"}\r\n\r\nevent: answer\r\ndata: {"answer":"done"}\r\n\r\nevent: done\r\ndata: {}\r\n\r\n'), (event, data) => events.push([event, data]));
  assert.deepEqual(events.map(item => item[0]), ['token', 'answer', 'done']);
  assert.equal(events[0][1].text, 'नमस्ते');
});

test('rejects a truncated stream even after a draft token', async () => {
  await assert.rejects(consumeEvents(response('event: token\ndata: {"text":"draft"}\n\n'), () => {}), /interrupted/);
});

test('requires the final answer and terminal event', async () => {
  await assert.rejects(consumeEvents(response('event: done\ndata: {}\n\n'), () => {}), /interrupted/);
});

test('surfaces a safe server error', async () => {
  await assert.rejects(consumeEvents(response('event: error\ndata: {"message":"Retry later"}\n\n'), () => {}), /Retry later/);
});
