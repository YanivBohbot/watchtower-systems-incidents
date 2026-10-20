import { useEffect, useState } from "react";
import { mediaUrl } from "./client";

/**
 * Fetch an authenticated image or video as an object URL, revoked when the path
 * changes or the component unmounts. A null path clears the media.
 */
export function useMedia(path: string | null, token: string) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    setUrl("");
    setError("");
    if (!path) return;
    const abort = new AbortController();
    let current = "";
    mediaUrl(path, token, abort.signal)
      .then((value) => {
        current = value;
        if (abort.signal.aborted) URL.revokeObjectURL(value);
        else setUrl(value);
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(String(e));
      });
    return () => {
      abort.abort();
      if (current) URL.revokeObjectURL(current);
    };
  }, [path, token]);
  return { url, error };
}
