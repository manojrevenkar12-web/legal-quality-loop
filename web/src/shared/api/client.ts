import { net } from "../../theme/tokens";

export class LoadError extends Error {
  constructor(message: string, readonly retryable: boolean) {
    super(message);
    this.name = "LoadError";
  }
}

export async function fetchJSON<T>(url: string, signal?: AbortSignal, fetcher: typeof fetch = fetch): Promise<T> {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), net.timeoutMs);
  signal?.addEventListener("abort", () => timeout.abort());
  try {
    const res = await fetcher(url, { signal: timeout.signal });
    if (res.status === 404) throw new LoadError("No results yet. Run qloop develop, qloop heldout and qloop report.", false);
    if (!res.ok) throw new LoadError(`The server answered ${res.status}.`, true);
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof LoadError) throw e;
    if (signal?.aborted) throw e;
    throw new LoadError(timeout.signal.aborted ? "Loading took too long." : "Could not load the results.", true);
  } finally {
    clearTimeout(timer);
  }
}
