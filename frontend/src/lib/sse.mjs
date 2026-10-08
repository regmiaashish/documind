// Decode complete SSE frames; network chunks may split lines or UTF-8 characters.
export async function consumeEvents(response, onEvent) {
  if (!response.body) throw new Error('Your browser cannot read this response.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let doneEvent = false;
  let answerEvent = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      // CRLF is legal SSE. Preserve an incomplete CRLF until the next read.
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || '';
      for (const frame of frames) {
        let event = 'message';
        const lines = [];
        for (const line of frame.split(/\r?\n/)) {
          if (line.startsWith('event:')) event = line.slice(6).trim();
          if (line.startsWith('data:')) lines.push(line.slice(5).trimStart());
        }
        if (!lines.length) continue;
        const data = JSON.parse(lines.join('\n'));
        if (event === 'error') throw new Error(data.message || 'The answer failed. Please retry.');
        if (event === 'answer') answerEvent = true;
        if (event === 'done') doneEvent = true;
        onEvent(event, data);
      }
      if (done) break;
    }
    if (!doneEvent || !answerEvent) throw new Error('The answer was interrupted. Please retry.');
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
