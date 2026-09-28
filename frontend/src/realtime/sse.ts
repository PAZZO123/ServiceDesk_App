
export interface SseMessage {
  event: string;
  data: string;
}
export function createSseParser(): (chunk: string) => SseMessage[] {
  // Text we already received, but which is not a finished event yet.
  let buffer = "";
  let heldBack = "";

  return function push(chunk: string): SseMessage[] {
    let text = heldBack + chunk;
    heldBack = "";

    if (text.endsWith("\r")) {
      heldBack = "\r";
      text = text.slice(0, -1); // remove the last character
    }

    buffer += text.replace(/\r\n?/g, "\n");
    const messages: SseMessage[] = [];
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {

      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2); // +2 skips the two "\n"
      let event = "message";

      const dataLines: string[] = [];

      for (const line of block.split("\n")) {
        if (line === "" || line.startsWith(":")) continue;

        const colon = line.indexOf(":");
        const field = colon === -1 ? line : line.slice(0, colon);
        let value = colon === -1 ? "" : line.slice(colon + 1);

        if (value.startsWith(" ")) value = value.slice(1);

        if (field === "event") event = value;
        else if (field === "data") dataLines.push(value);
      }
      if (dataLines.length > 0) {
        messages.push({ event, data: dataLines.join("\n") });
      }

      boundary = buffer.indexOf("\n\n");
    }

    return messages;
  };
}

// ── HOW useUnreadCount.ts WILL USE THIS (next file) ──
//   const decoder = new TextDecoder();      // bytes -> text
//   const parse = createSseParser();
//   for each chunk `value` read from response.body:
//     const text = decoder.decode(value, { stream: true });
//     for (const msg of parse(text)) { ...use msg.data... }
//
// { stream: true } matters. A character like "é" is 2 bytes. If a chunk
// ends after the first byte, the decoder waits for the second byte
// instead of producing a broken character.