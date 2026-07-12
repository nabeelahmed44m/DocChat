/**
 * Typed HTTP client for the Doc Chat backend.
 *
 * A thin, dependency-light wrapper: it owns URL construction, JSON handling,
 * multipart uploads, timeouts, auth headers, and turning non-2xx responses into
 * a typed `ApiError` the UI can branch on. Connection details (base URL + API
 * key) are injected as an `ApiCtx` rather than hard-coded.
 *
 * File uploads use expo-file-system's uploadAsync instead of fetch+FormData
 * because React Native's fetch multipart implementation is unreliable on iOS.
 */

import * as FileSystem from 'expo-file-system/legacy';
import { fetch as streamingFetch } from 'expo/fetch';

import type {
  AskResponse,
  BillingStatus,
  CheckoutResponse,
  DocumentList,
  DocumentRecord,
  HealthResponse,
  KeyPointsResponse,
  PickedFile,
  SearchResponse,
  StatusResponse,
  SummaryResponse,
  TablesResponse,
} from './types';

const DEFAULT_TIMEOUT_MS = 20000;

export interface ApiCtx {
  baseUrl: string;
  apiKey?: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, '')}${path}`;
}

function authHeaders(ctx: ApiCtx): Record<string, string> {
  return ctx.apiKey ? { Authorization: `Bearer ${ctx.apiKey}` } : {};
}

async function parseError(res: Response): Promise<never> {
  let detail = `Request failed (${res.status})`;
  let code: string | undefined;
  try {
    const body = await res.json();
    if (body?.detail) detail = body.detail;
    if (body?.code) code = body.code;
  } catch {
    // non-JSON body; keep the default message
  }
  throw new ApiError(detail, res.status, code);
}

async function request<T>(
  ctx: ApiCtx,
  path: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(joinUrl(ctx.baseUrl, path), {
      ...init,
      headers: { ...authHeaders(ctx), ...(init.headers ?? {}) },
      signal: controller.signal,
    });
    if (!res.ok) await parseError(res);
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiError('The request timed out. Check the server address.', 0);
    }
    throw new ApiError(
      `Could not reach the server (${ctx.baseUrl}). Check the address in Settings.`,
      0,
    );
  } finally {
    clearTimeout(timer);
  }
}

/**
 * POST/GET a plain-text streaming endpoint and report progress.
 *
 * Uses expo/fetch (WinterCG-compliant) because React Native's built-in fetch
 * cannot read response bodies incrementally. `onChunk` receives the full text
 * accumulated so far — simpler for callers that re-render on every chunk.
 */
async function streamText(
  ctx: ApiCtx,
  path: string,
  init: { method?: string; body?: string } = {},
  onChunk: (textSoFar: string) => void,
  timeoutMs = 90000,
): Promise<string> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await streamingFetch(joinUrl(ctx.baseUrl, path), {
      method: init.method ?? 'GET',
      headers: {
        ...authHeaders(ctx),
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: init.body,
      signal: controller.signal,
    });
    if (!res.ok) {
      let detail = `Request failed (${res.status})`;
      let code: string | undefined;
      try {
        const body = await res.json();
        if (body?.detail) detail = body.detail;
        if (body?.code) code = body.code;
      } catch { /* non-JSON body */ }
      throw new ApiError(detail, res.status, code);
    }
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let full = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      full += decoder.decode(value, { stream: true });
      onChunk(full);
    }
    full += decoder.decode();
    return full;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiError('The request timed out. Check the server address.', 0);
    }
    throw new ApiError(
      `Could not reach the server (${ctx.baseUrl}). Check the address in Settings.`,
      0,
    );
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: (ctx: ApiCtx) => request<HealthResponse>(ctx, '/health', {}, 8000),

  listDocuments: (ctx: ApiCtx) => request<DocumentList>(ctx, '/documents'),

  getDocument: (ctx: ApiCtx, id: string) =>
    request<DocumentRecord>(ctx, `/documents/${id}`),

  getStatus: (ctx: ApiCtx, id: string) =>
    request<StatusResponse>(ctx, `/documents/${id}/status`, {}, 8000),

  uploadDocument: async (ctx: ApiCtx, file: PickedFile, persist: boolean): Promise<DocumentRecord> => {
    const url = joinUrl(ctx.baseUrl, '/documents');
    try {
      const result = await FileSystem.uploadAsync(url, file.uri, {
        httpMethod: 'POST',
        uploadType: FileSystem.FileSystemUploadType.MULTIPART as number,
        fieldName: 'file',
        mimeType: file.mimeType,
        parameters: { persist: String(persist), display_name: file.name },
        headers: authHeaders(ctx),
      });
      if (result.status < 200 || result.status >= 300) {
        let detail = `Request failed (${result.status})`;
        let code: string | undefined;
        try {
          const body = JSON.parse(result.body);
          if (body?.detail) detail = body.detail;
          if (body?.code) code = body.code;
        } catch { /* keep default */ }
        throw new ApiError(detail, result.status, code);
      }
      return JSON.parse(result.body) as DocumentRecord;
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(
        `Upload failed (${ctx.baseUrl}). Check the address in Settings.`,
        0,
      );
    }
  },

  ask: (
    ctx: ApiCtx,
    id: string,
    question: string,
    history: Array<{ role: 'user' | 'model'; content: string }> = [],
    topK = 6,
  ) =>
    request<AskResponse>(ctx, `/documents/${id}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, top_k: topK, history }),
    }, 30000),

  askStream: (
    ctx: ApiCtx,
    id: string,
    question: string,
    history: Array<{ role: 'user' | 'model'; content: string }>,
    onChunk: (textSoFar: string) => void,
    topK = 6,
  ) =>
    streamText(
      ctx,
      `/documents/${id}/ask/stream`,
      { method: 'POST', body: JSON.stringify({ question, top_k: topK, history }) },
      onChunk,
    ),

  summaryStream: (ctx: ApiCtx, id: string, onChunk: (textSoFar: string) => void) =>
    streamText(ctx, `/documents/${id}/summary/stream`, {}, onChunk),

  keypointsStream: (ctx: ApiCtx, id: string, onChunk: (textSoFar: string) => void) =>
    streamText(ctx, `/documents/${id}/keypoints/stream`, {}, onChunk),

  summary: (ctx: ApiCtx, id: string) =>
    request<SummaryResponse>(ctx, `/documents/${id}/summary`, {}, 30000),

  keypoints: (ctx: ApiCtx, id: string) =>
    request<KeyPointsResponse>(ctx, `/documents/${id}/keypoints`),

  tables: (ctx: ApiCtx, id: string) =>
    request<TablesResponse>(ctx, `/documents/${id}/tables`, {}, 60000),

  search: (ctx: ApiCtx, question: string, topK = 8) =>
    request<SearchResponse>(ctx, '/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, top_k: topK, per_document: 1 }),
    }),

  deleteDocument: (ctx: ApiCtx, id: string) =>
    request<void>(ctx, `/documents/${id}`, { method: 'DELETE' }),

  getBillingStatus: (ctx: ApiCtx) =>
    request<BillingStatus>(ctx, '/billing/status'),

  createCheckout: (ctx: ApiCtx) =>
    request<CheckoutResponse>(ctx, '/billing/checkout', { method: 'POST' }),

  createPortal: (ctx: ApiCtx) =>
    request<CheckoutResponse>(ctx, '/billing/portal', { method: 'POST' }),
};
