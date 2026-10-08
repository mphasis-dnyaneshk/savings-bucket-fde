export type View = "overview" | "goals" | "bucket" | "activity" | "archived";

export interface Bucket {
  bucket_id: string;
  customer_id: string;
  name: string;
  target_amount: string;
  current_balance: string;
  remaining_amount: string;
  progress_percentage: string;
  target_date: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  reached_at: string | null;
  archived_at: string | null;
}

export interface Transaction {
  transaction_id: string;
  bucket_id: string;
  type: string;
  amount: string;
  status: string;
  external_reference: string | null;
  created_at: string;
}

export interface Contribution {
  contribution_id: string;
  bucket_id: string;
  customer_id: string;
  amount: string;
  status: string;
  idempotency_key: string;
  external_reference: string;
  created_at: string;
  goal_reached_now: boolean;
  bucket_current_balance: string | null;
  bucket_target_amount: string | null;
  bucket_remaining_amount: string | null;
  bucket_progress_percentage: string | null;
  bucket_status: string | null;
}

export interface Withdrawal {
  withdrawal_id: string;
  bucket_id: string;
  customer_id: string;
  amount: string;
  status: string;
  idempotency_key: string;
  external_reference: string;
  created_at: string;
}

export interface Schedule {
  schedule_id: string;
  bucket_id: string;
  customer_id: string;
  amount: string;
  frequency: string;
  start_date: string;
  next_execution_date: string;
  status: "ACTIVE" | "PAUSED" | "CANCELLED";
  created_at: string;
  updated_at: string;
}

export interface Notification {
  notification_id: string;
  customer_id: string;
  event_type: string;
  message: string;
  status: string;
  created_at: string;
}
