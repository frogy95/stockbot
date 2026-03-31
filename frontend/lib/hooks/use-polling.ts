"use client";

import useSWR from "swr";
import { apiGet } from "@/lib/api";

export function usePolling<T>(path: string, intervalMs = 5000) {
  const { data, error, isLoading, mutate } = useSWR<T>(path, apiGet, {
    refreshInterval: intervalMs,
    revalidateOnFocus: false,
    refreshWhenHidden: false,
  });

  return { data, error, isLoading, mutate };
}
