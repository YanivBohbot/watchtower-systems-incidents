import { useQuery } from "@tanstack/react-query";
import { request } from "./client";

/** A list endpoint (`/videos`, `/jobs`, ...) polled every 2.5 seconds while signed in. */
export function useList<T>(name: string, token: string, enabled: boolean) {
  return useQuery({
    queryKey: [name, token],
    queryFn: () => request<T[]>(`/${name}`, token),
    enabled,
    refetchInterval: 2500,
  });
}
