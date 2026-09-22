import type {
  Bucket,
  Contribution,
  Notification,
  Schedule,
  Transaction,
  Withdrawal,
} from "./types";

const customerId = import.meta.env.VITE_CUSTOMER_ID || "customer-001";
const bucketApi = import.meta.env.VITE_BUCKET_API_URL || "http://localhost:8001";
const contributionApi = import.meta.env.VITE_CONTRIBUTION_API_URL || "http://localhost:8002";
const withdrawalApi = import.meta.env.VITE_WITHDRAWAL_API_URL || "http://localhost:8003";
const recurringApi = import.meta.env.VITE_RECURRING_API_URL || "http://localhost:8004";
const notificationApi = import.meta.env.VITE_NOTIFICATION_API_URL || "http://localhost:8005";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Customer-ID": customerId,
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string; message?: string } | null;
    throw new Error(body?.detail || body?.message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  customerId,
  listBuckets: () => request<Bucket[]>(`${bucketApi}/v1/buckets`),
  createBucket: (payload: { name: string; target_amount: string; target_date: string | null }) =>
    request<Bucket>(`${bucketApi}/v1/buckets`, { method: "POST", body: JSON.stringify(payload) }),
  getTransactions: (bucketId: string) =>
    request<Transaction[]>(`${bucketApi}/v1/buckets/${bucketId}/transactions`),
  contribute: (bucketId: string, amount: string) =>
    request<Contribution>(`${contributionApi}/v1/buckets/${bucketId}/contributions`, {
      method: "POST",
      headers: { "Idempotency-Key": `contribution-${crypto.randomUUID()}` },
      body: JSON.stringify({ amount }),
    }),
  withdraw: (bucketId: string, amount: string) =>
    request<Withdrawal>(`${withdrawalApi}/v1/buckets/${bucketId}/withdrawals`, {
      method: "POST",
      headers: { "Idempotency-Key": `withdrawal-${crypto.randomUUID()}` },
      body: JSON.stringify({ amount }),
    }),
  listSchedules: (bucketId: string) =>
    request<Schedule[]>(`${recurringApi}/v1/buckets/${bucketId}/recurring-contributions`),
  createSchedule: (bucketId: string, payload: { amount: string; frequency: string; start_date: string }) =>
    request<Schedule>(`${recurringApi}/v1/buckets/${bucketId}/recurring-contributions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateSchedule: (bucketId: string, scheduleId: string, payload: Partial<Pick<Schedule, "amount" | "frequency" | "status">>) =>
    request<Schedule>(`${recurringApi}/v1/buckets/${bucketId}/recurring-contributions/${scheduleId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createNotification: (payload: { event_type: string; message: string }) =>
    request<Notification>(`${notificationApi}/internal/notifications`, {
      method: "POST",
      headers: {},
      body: JSON.stringify({ ...payload, customer_id: customerId }),
    }),
};
