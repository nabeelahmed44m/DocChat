/**
 * React Query hooks over the API client.
 *
 * These own caching, background refetch, and — crucially — the polling that
 * drives the "queued → processing → ready" UI while the backend ingests a
 * document. Every hook builds an `ApiCtx` (base URL + API key) from settings, so
 * auth and server address flow through transparently.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useSettings } from '@/lib/settings';
import { createSmoothStream } from '@/lib/smoothStream';
import { api, type ApiCtx } from './client';
import type { DocumentRecord, PickedFile } from './types';

const IN_FLIGHT: readonly string[] = ['queued', 'processing'];

/** Build the API context (base URL + key) and a stable cache-scope string. */
function useApiCtx(): { ctx: ApiCtx; scope: string } {
  const { baseUrl, apiKey } = useSettings();
  return useMemo(
    () => ({ ctx: { baseUrl, apiKey }, scope: `${baseUrl}#${apiKey}` }),
    [baseUrl, apiKey],
  );
}

export const queryKeys = {
  health: (scope: string) => ['health', scope] as const,
  documents: (scope: string) => ['documents', scope] as const,
  status: (scope: string, id: string) => ['status', scope, id] as const,
  summary: (scope: string, id: string) => ['summary', scope, id] as const,
  keypoints: (scope: string, id: string) => ['keypoints', scope, id] as const,
  tables: (scope: string, id: string) => ['tables', scope, id] as const,
};

export function useHealth() {
  const { ctx, scope } = useApiCtx();
  return useQuery({
    queryKey: queryKeys.health(scope),
    queryFn: () => api.health(ctx),
    retry: 1,
    staleTime: 15000,
  });
}

export function useDocuments() {
  const { ctx, scope } = useApiCtx();
  return useQuery({
    queryKey: queryKeys.documents(scope),
    queryFn: () => api.listDocuments(ctx),
    refetchInterval: (query) => {
      const anyInFlight = query.state.data?.documents.some((d) =>
        IN_FLIGHT.includes(d.status),
      );
      return anyInFlight ? 1500 : false;
    },
  });
}

export function useDocumentStatus(id: string, enabled = true) {
  const { ctx, scope } = useApiCtx();
  return useQuery({
    queryKey: queryKeys.status(scope, id),
    queryFn: () => api.getStatus(ctx, id),
    enabled: enabled && !!id,
    refetchInterval: (query) =>
      IN_FLIGHT.includes(query.state.data?.status ?? 'ready') ? 1200 : false,
  });
}

export function useUploadDocument() {
  const { ctx, scope } = useApiCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, persist }: { file: PickedFile; persist: boolean }) =>
      api.uploadDocument(ctx, file, persist),
    onSuccess: (record: DocumentRecord) => {
      qc.invalidateQueries({ queryKey: queryKeys.documents(scope) });
      qc.setQueryData(queryKeys.status(scope, record.id), {
        id: record.id,
        status: record.status,
        error: record.error,
        stats: record.stats,
      });
    },
  });
}

export type ChatMessage = { role: 'user' | 'model'; content: string };

export function useAsk(id: string) {
  const { ctx } = useApiCtx();
  return useMutation({
    mutationFn: ({
      question,
      history = [],
      topK,
    }: {
      question: string;
      history?: ChatMessage[];
      topK?: number;
    }) => api.ask(ctx, id, question, history, topK),
  });
}

/**
 * Streaming Q&A: returns a function that POSTs to /ask/stream and invokes
 * `onChunk` with the accumulated answer as chunks arrive. Resolves with the
 * final full answer.
 */
export function useAskStream(id: string) {
  const { ctx } = useApiCtx();
  return useCallback(
    (
      question: string,
      history: ChatMessage[],
      onChunk: (textSoFar: string) => void,
    ) => api.askStream(ctx, id, question, history, onChunk),
    [ctx, id],
  );
}

export type StreamState = {
  /** Raw accumulated text so far (SUMMARY:/KEY POINTS: format). */
  text: string;
  /** True while chunks are still arriving. */
  streaming: boolean;
  /** True once the stream finished successfully. */
  done: boolean;
  error: string | null;
  retry: () => void;
};

/**
 * Stream an analysis endpoint (summary or keypoints) once when `active`
 * becomes true. The raw text grows as chunks arrive; callers parse it
 * progressively. The backend caches the parsed result, so re-streams after
 * the first are a single instant chunk.
 */
export function useAnalysisStream(
  id: string,
  kind: 'summary' | 'keypoints',
  active: boolean,
): StreamState {
  const { ctx, scope } = useApiCtx();
  const [text, setText] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const startedFor = useRef<string | null>(null);

  const retry = useCallback(() => {
    startedFor.current = null;
    setText('');
    setDone(false);
    setError(null);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    const key = `${scope}#${id}#${kind}#${attempt}`;
    if (!active || !id || startedFor.current === key) return;
    startedFor.current = key;

    let cancelled = false;
    setStreaming(true);
    setError(null);

    // Pace the reveal so fast generations (and instant cached replays)
    // still visibly stream in instead of appearing all at once.
    const smooth = createSmoothStream((soFar) => {
      if (!cancelled) setText(soFar);
    });

    const call = kind === 'summary' ? api.summaryStream : api.keypointsStream;
    call(ctx, id, (soFar) => smooth.push(soFar))
      .then((raw) => smooth.finish(raw))
      .then((full) => {
        if (cancelled) return;
        setText(full);
        setDone(true);
      })
      .catch((err) => {
        smooth.cancel();
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Something went wrong.');
      })
      .finally(() => {
        if (!cancelled) setStreaming(false);
      });

    return () => {
      cancelled = true;
      smooth.cancel();
    };
  }, [active, id, kind, ctx, scope, attempt]);

  return { text, streaming, done, error, retry };
}

export function useSearch() {
  const { ctx } = useApiCtx();
  return useMutation({
    mutationFn: (question: string) => api.search(ctx, question),
  });
}

export function useSummary(id: string, enabled: boolean) {
  const { ctx, scope } = useApiCtx();
  return useQuery({
    queryKey: queryKeys.summary(scope, id),
    queryFn: () => api.summary(ctx, id),
    enabled: enabled && !!id,
    staleTime: Infinity,
  });
}

export function useKeypoints(id: string, enabled: boolean) {
  const { ctx, scope } = useApiCtx();
  return useQuery({
    queryKey: queryKeys.keypoints(scope, id),
    queryFn: () => api.keypoints(ctx, id),
    enabled: enabled && !!id,
    staleTime: Infinity,
  });
}

export function useTables(id: string, enabled: boolean) {
  const { ctx, scope } = useApiCtx();
  return useQuery({
    queryKey: queryKeys.tables(scope, id),
    queryFn: () => api.tables(ctx, id),
    enabled: enabled && !!id,
    staleTime: Infinity,
  });
}

export function useDeleteDocument() {
  const { ctx, scope } = useApiCtx();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteDocument(ctx, id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.documents(scope) }),
  });
}
