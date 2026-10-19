import type { LiveEvent } from "./types";

export async function request<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : `Invalid request (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

export async function mediaUrl(
  path: string,
  token: string,
  signal: AbortSignal,
): Promise<string> {
  const response = await fetch(`/api${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  if (!response.ok) throw new Error("Unable to load media");
  return URL.createObjectURL(await response.blob());
}

/** Reads the Server-Sent Events stream with fetch so the token stays in a header; reconnects with backoff. */
export function streamEvents(
  token: string,
  onEvent: (event: LiveEvent) => void,
  onOpen: () => void,
): () => void {
  const abort = new AbortController();
  let delay = 1000;
  void (async () => {
    while (!abort.signal.aborted) {
      try {
        const response = await fetch("/api/live/events", {
          headers: { Authorization: `Bearer ${token}` },
          signal: abort.signal,
        });
        if (!response.ok || !response.body)
          throw new Error(`Live events unavailable (${response.status})`);
        onOpen();
        delay = 1000;
        const reader = response.body
          .pipeThrough(new TextDecoderStream())
          .getReader();
        let buffer = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += value;
          let end = buffer.indexOf("\n\n");
          while (end >= 0) {
            const data = buffer
              .slice(0, end)
              .split("\n")
              .filter((line) => line.startsWith("data: "))
              .map((line) => line.slice(6))
              .join("\n");
            buffer = buffer.slice(end + 2);
            if (data) onEvent(JSON.parse(data) as LiveEvent);
            end = buffer.indexOf("\n\n");
          }
        }
      } catch {
        if (abort.signal.aborted) return;
      }
      await new Promise((resolve) => setTimeout(resolve, delay));
      delay = Math.min(delay * 2, 15000);
    }
  })();
  return () => abort.abort();
}
