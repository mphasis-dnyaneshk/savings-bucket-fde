import { FormEvent, useEffect, useState } from "react";
import {
  ArrowUpRight,
  Bell,
  CalendarDays,
  Check,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  LayoutDashboard,
  LoaderCircle,
  Plus,
  RefreshCw,
  Settings2,
  Target,
  WalletCards,
  X,
} from "lucide-react";
import { api } from "./api";
import type { Bucket, Notification, Schedule, Transaction, View } from "./types";

const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

function formatMoney(value: string | number) {
  return money.format(Number(value));
}

function formatDate(value: string | null) {
  if (!value) return "No target date";
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(
    new Date(value),
  );
}

function App() {
  const [buckets, setBuckets] = useState<Bucket[]>([]);
  const [selectedBucket, setSelectedBucket] = useState<Bucket | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [view, setView] = useState<View>("overview");
  const [modal, setModal] = useState<"create" | "contribute" | "withdraw" | "recurring" | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  async function loadBuckets() {
    setLoading(true);
    setError("");
    try {
      const nextBuckets = await api.listBuckets();
      setBuckets(nextBuckets);
      if (selectedBucket) {
        setSelectedBucket(nextBuckets.find((bucket) => bucket.bucket_id === selectedBucket.bucket_id) || null);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load buckets.");
    } finally {
      setLoading(false);
    }
  }

  async function loadNotifications() {
    try {
      setNotifications(await api.listNotifications());
    } catch {
      // Notifications are optional local feedback and should not block the dashboard.
    }
  }

  async function dismissNotification(notificationId: string) {
    try {
      await api.dismissNotification(notificationId);
      setNotifications((current) => current.filter((item) => item.notification_id !== notificationId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not dismiss notification.");
    }
  }

  async function selectBucket(bucket: Bucket) {
    setSelectedBucket(bucket);
    setView("bucket");
    setError("");
    try {
      const [nextTransactions, nextSchedules] = await Promise.all([
        api.getTransactions(bucket.bucket_id),
        api.listSchedules(bucket.bucket_id),
      ]);
      setTransactions(nextTransactions);
      setSchedules(nextSchedules);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load bucket details.");
    }
  }

  useEffect(() => {
    void loadBuckets();
    void loadNotifications();
  }, []);

  const totalSaved = buckets.reduce((sum, bucket) => sum + Number(bucket.current_balance), 0);
  const totalTarget = buckets.reduce((sum, bucket) => sum + Number(bucket.target_amount), 0);
  const totalProgress = totalTarget ? Math.min((totalSaved / totalTarget) * 100, 100) : 0;

  function navigate(nextView: View) {
    setView(nextView);
    if (nextView !== "bucket") setSelectedBucket(null);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setWorking(true);
    setError("");
    try {
      const bucket = await api.createBucket({
        name: String(form.get("name")),
        target_amount: String(form.get("target_amount")),
        target_date: String(form.get("target_date") || "") || null,
      });
      setBuckets((current) => [bucket, ...current]);
      setModal(null);
      await selectBucket(bucket);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create bucket.");
    } finally {
      setWorking(false);
    }
  }

  async function handleMoneyAction(event: FormEvent<HTMLFormElement>, kind: "contribute" | "withdraw") {
    event.preventDefault();
    if (!selectedBucket) return;
    const form = new FormData(event.currentTarget);
    setWorking(true);
    setError("");
    try {
      const amount = String(form.get("amount"));
      const result = kind === "contribute"
        ? await api.contribute(selectedBucket.bucket_id, amount)
        : await api.withdraw(selectedBucket.bucket_id, amount);
      const notification = await api.createNotification({
        event_type: kind === "contribute" ? "ContributionCompleted" : "WithdrawalCompleted",
        message: `${kind === "contribute" ? "Contribution" : "Withdrawal"} of ${formatMoney(amount)} completed in mock mode.`,
      });
      setNotifications((current) => [notification, ...current]);
      await loadBuckets();
      if (selectedBucket) await selectBucket(selectedBucket);
      setModal(null);
      setError(`${kind === "contribute" ? "Contribution" : "Withdrawal"} ${result.status.toLowerCase()}. Mock financial state is recorded separately from bucket allocation.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not complete the request.");
    } finally {
      setWorking(false);
    }
  }

  async function handleRecurring(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBucket) return;
    const form = new FormData(event.currentTarget);
    setWorking(true);
    setError("");
    try {
      const schedule = await api.createSchedule(selectedBucket.bucket_id, {
        amount: String(form.get("amount")),
        frequency: String(form.get("frequency")),
        start_date: String(form.get("start_date")),
      });
      setSchedules((current) => [schedule, ...current]);
      setModal(null);
      setError("Recurring contribution scheduled in mock mode.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create schedule.");
    } finally {
      setWorking(false);
    }
  }

  async function toggleSchedule(schedule: Schedule) {
    if (!selectedBucket) return;
    const status = schedule.status === "ACTIVE" ? "PAUSED" : "ACTIVE";
    try {
      const updated = await api.updateSchedule(selectedBucket.bucket_id, schedule.schedule_id, { status });
      setSchedules((current) => current.map((item) => item.schedule_id === updated.schedule_id ? updated : item));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update schedule.");
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark"><CircleDollarSign size={22} strokeWidth={2.5} /></div>
        <div className="brand-copy">
          <span className="eyebrow">Personal finance</span>
          <strong>Savings<br />Bucket</strong>
        </div>
        <nav className="primary-nav" aria-label="Primary navigation">
          <button className={view === "overview" ? "nav-item active" : "nav-item"} onClick={() => navigate("overview")}><LayoutDashboard size={18} /> Overview</button>
          <button className={view === "bucket" ? "nav-item active" : "nav-item"} onClick={() => selectedBucket ? setView("bucket") : navigate("overview")}><Target size={18} /> Goals</button>
          <button className={view === "activity" ? "nav-item active" : "nav-item"} onClick={() => navigate("activity")}><Clock3 size={18} /> Activity</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="mode-note"><span className="status-dot" /> Local mock mode</div>
          <button className="nav-item"><Settings2 size={18} /> Settings</button>
          <div className="profile"><span className="avatar">C</span><span><strong>Customer 001</strong><small>Demo profile</small></span></div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div><span className="breadcrumb">Savings / {view === "overview" ? "Overview" : view === "activity" ? "Activity" : selectedBucket?.name || "Goal"}</span><h1>{view === "overview" ? "Your savings, in view." : view === "activity" ? "Activity" : selectedBucket?.name || "Goal detail"}</h1></div>
          <div className="top-actions"><button className="icon-button" title="Refresh data" onClick={() => { void loadBuckets(); void loadNotifications(); }}><RefreshCw size={18} /></button><div className="notification-wrap"><button className="notification-button" title="Notifications" aria-label="Notifications" aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((open) => !open)}><Bell size={18} />{notifications.length > 0 && <span>{notifications.length}</span>}</button>{notificationsOpen && <NotificationPopover notifications={notifications} onDismiss={(notificationId) => void dismissNotification(notificationId)} />}</div><button className="primary-button" onClick={() => setModal("create")}><Plus size={18} /> New goal</button></div>
        </header>

        {error && <div className="notice" role="status"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss message"><X size={16} /></button></div>}

        {loading ? <div className="loading-state"><LoaderCircle className="spin" size={28} /><span>Loading your goals...</span></div> : view === "overview" ? (
          <Overview buckets={buckets} totalSaved={totalSaved} totalTarget={totalTarget} totalProgress={totalProgress} onSelect={selectBucket} onCreate={() => setModal("create")} />
        ) : view === "activity" ? (
          <Activity buckets={buckets} onSelect={selectBucket} />
        ) : selectedBucket ? (
          <BucketDetail bucket={selectedBucket} transactions={transactions} schedules={schedules} onBack={() => navigate("overview")} onContribute={() => setModal("contribute")} onWithdraw={() => setModal("withdraw")} onRecurring={() => setModal("recurring")} onToggleSchedule={toggleSchedule} />
        ) : <EmptyState onCreate={() => setModal("create")} />}
      </main>

      {modal === "create" && <Modal title="Create a savings goal" subtitle="Give your next milestone a clear place to grow." onClose={() => setModal(null)}><form className="form-stack" onSubmit={handleCreate}><label>Goal name<input name="name" placeholder="Emergency Fund" required autoFocus /></label><label>Target amount<input name="target_amount" type="number" min="1" step="0.01" placeholder="100000" required /></label><label>Target date <span className="optional">optional</span><input name="target_date" type="date" /></label><button className="primary-button full-width" disabled={working}>{working ? "Creating..." : "Create goal"} <ArrowUpRight size={17} /></button></form></Modal>}
      {modal === "contribute" && <Modal title="Add money" subtitle={`Assign savings to ${selectedBucket?.name}.`} onClose={() => setModal(null)}><form className="form-stack" onSubmit={(event) => void handleMoneyAction(event, "contribute")}><div className="context-row"><WalletCards size={18} /><span>Mock funding account</span><strong>Available</strong></div><label>Contribution amount<input name="amount" type="number" min="0.01" step="0.01" placeholder="1000" required autoFocus /></label><div className="safe-copy"><Check size={16} /> This demo uses mock financial processing.</div><button className="primary-button full-width" disabled={working}>{working ? "Processing..." : "Review contribution"} <ArrowUpRight size={17} /></button></form></Modal>}
      {modal === "withdraw" && <Modal title="Withdraw savings" subtitle={`Return assigned savings from ${selectedBucket?.name}.`} onClose={() => setModal(null)}><form className="form-stack" onSubmit={(event) => void handleMoneyAction(event, "withdraw")}><div className="balance-callout"><span>Current allocated balance</span><strong>{formatMoney(selectedBucket?.current_balance || 0)}</strong></div><label>Withdrawal amount<input name="amount" type="number" min="0.01" step="0.01" placeholder="500" required autoFocus /></label><div className="safe-copy warning"><Check size={16} /> Mock mode will return a successful result.</div><button className="primary-button dark full-width" disabled={working}>{working ? "Processing..." : "Review withdrawal"} <ArrowUpRight size={17} /></button></form></Modal>}
      {modal === "recurring" && <Modal title="Set a recurring contribution" subtitle="Turn a small habit into steady progress." onClose={() => setModal(null)}><form className="form-stack" onSubmit={(event) => void handleRecurring(event)}><label>Amount<input name="amount" type="number" min="0.01" step="0.01" placeholder="1000" required autoFocus /></label><label>Frequency<select name="frequency" defaultValue="MONTHLY"><option value="WEEKLY">Weekly</option><option value="MONTHLY">Monthly</option><option value="QUARTERLY">Quarterly</option></select></label><label>Start date<input name="start_date" type="date" defaultValue={new Date().toISOString().slice(0, 10)} required /></label><button className="primary-button full-width" disabled={working}>{working ? "Saving..." : "Schedule contribution"} <ArrowUpRight size={17} /></button></form></Modal>}
    </div>
  );
}

function Overview({ buckets, totalSaved, totalTarget, totalProgress, onSelect, onCreate }: { buckets: Bucket[]; totalSaved: number; totalTarget: number; totalProgress: number; onSelect: (bucket: Bucket) => void; onCreate: () => void }) {
  return <>
    <section className="hero-panel"><div className="hero-copy"><span className="eyebrow light">Your financial north star</span><h2>Small, intentional moves.<br /><em>Big future energy.</em></h2><p>Keep every goal visible, every milestone tangible, and your next move close at hand.</p><button className="light-button" onClick={onCreate}><Plus size={17} /> Create a goal</button></div><div className="hero-orbit"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="orbit-core"><span>Total saved</span><strong>{formatMoney(totalSaved)}</strong><small>across {buckets.length} {buckets.length === 1 ? "goal" : "goals"}</small></div></div></section>
    <section className="stat-grid"><div className="stat-card"><span>Allocated savings</span><strong>{formatMoney(totalSaved)}</strong><small>Across all goals</small></div><div className="stat-card"><span>Total target</span><strong>{formatMoney(totalTarget)}</strong><small>{totalTarget ? `${Math.round(totalProgress)}% overall progress` : "Start your first goal"}</small></div><div className="stat-card accent-card"><span>Next best action</span><strong>{buckets.length ? "Keep going" : "Set a target"}</strong><small>{buckets.length ? "Consistency compounds" : "A clear goal changes everything"}</small></div></section>
    <div className="section-heading"><div><span className="eyebrow">Your goals</span><h2>Where your money is headed</h2></div><button className="text-button" onClick={onCreate}>Add another <ChevronRight size={16} /></button></div>
    {buckets.length ? <div className="bucket-grid">{buckets.map((bucket) => <BucketCard key={bucket.bucket_id} bucket={bucket} onClick={() => onSelect(bucket)} />)}</div> : <EmptyState onCreate={onCreate} />}
  </>;
}

function BucketCard({ bucket, onClick }: { bucket: Bucket; onClick: () => void }) {
  const progress = Number(bucket.progress_percentage);
  return <button className="bucket-card" onClick={onClick}><div className="card-top"><span className="goal-icon"><Target size={19} /></span><span className="card-arrow"><ArrowUpRight size={17} /></span></div><div className="card-title"><h3>{bucket.name}</h3><span>{formatDate(bucket.target_date)}</span></div><div className="progress-line"><span style={{ width: `${progress}%` }} /></div><div className="card-numbers"><strong>{formatMoney(bucket.current_balance)}</strong><span>of {formatMoney(bucket.target_amount)}</span><b>{progress.toFixed(0)}%</b></div></button>;
}

function BucketDetail({ bucket, transactions, schedules, onBack, onContribute, onWithdraw, onRecurring, onToggleSchedule }: { bucket: Bucket; transactions: Transaction[]; schedules: Schedule[]; onBack: () => void; onContribute: () => void; onWithdraw: () => void; onRecurring: () => void; onToggleSchedule: (schedule: Schedule) => void }) {
  const progress = Number(bucket.progress_percentage);
  return <div className="detail-layout"><button className="back-button" onClick={onBack}>← All goals</button><div className="detail-header"><div><span className="eyebrow">Goal detail</span><h2>{bucket.name}</h2><p>Target date {formatDate(bucket.target_date)}</p></div><span className="pill success">{bucket.status}</span></div><div className="detail-grid"><section className="balance-panel"><div className="balance-label"><span>Saved toward goal</span><span>{progress.toFixed(0)}%</span></div><strong>{formatMoney(bucket.current_balance)}</strong><div className="large-progress"><span style={{ width: `${progress}%` }} /></div><div className="balance-meta"><span>{formatMoney(bucket.remaining_amount)} remaining</span><span>Target {formatMoney(bucket.target_amount)}</span></div><div className="action-row"><button className="primary-button" onClick={onContribute}><Plus size={17} /> Add money</button><button className="secondary-button" onClick={onWithdraw}>Withdraw</button></div></section><section className="side-panel"><div className="panel-heading"><div><span className="eyebrow">Automate</span><h3>Recurring contribution</h3></div><CalendarDays size={20} /></div>{schedules.length ? schedules.map((schedule) => <div className="schedule-row" key={schedule.schedule_id}><div><strong>{formatMoney(schedule.amount)} · {schedule.frequency}</strong><span>Next on {formatDate(schedule.next_execution_date)}</span></div><button className={`status-toggle ${schedule.status.toLowerCase()}`} onClick={() => onToggleSchedule(schedule)}>{schedule.status === "ACTIVE" ? "Pause" : "Resume"}</button></div>) : <div className="empty-inline"><p>No recurring contribution yet.</p><button className="text-button" onClick={onRecurring}>Set one up <ChevronRight size={16} /></button></div>}</section></div><section className="activity-panel"><div className="panel-heading"><div><span className="eyebrow">Recent activity</span><h3>Money movement</h3></div><span className="activity-count">{transactions.length} records</span></div>{transactions.length ? transactions.map((transaction) => <div className="transaction-row" key={transaction.transaction_id}><span className={`transaction-icon ${transaction.type.toLowerCase()}`}>{transaction.type === "CONTRIBUTION" ? "+" : "−"}</span><div><strong>{transaction.type}</strong><span>{formatDate(transaction.created_at)} · {transaction.status}</span></div><b>{formatMoney(transaction.amount)}</b></div>) : <div className="empty-inline"><p>Your confirmed activity will appear here.</p><span className="muted">Mock contributions and withdrawals are tracked by their own services.</span></div>}</section></div>;
}

function Activity({ buckets, onSelect }: { buckets: Bucket[]; onSelect: (bucket: Bucket) => void }) {
  return <section className="activity-page"><div className="section-heading"><div><span className="eyebrow">Activity</span><h2>All your goals, one glance</h2></div></div>{buckets.length ? buckets.map((bucket) => <button className="activity-bucket" key={bucket.bucket_id} onClick={() => onSelect(bucket)}><span className="goal-icon"><Target size={18} /></span><span><strong>{bucket.name}</strong><small>{formatMoney(bucket.current_balance)} saved · {Number(bucket.progress_percentage).toFixed(0)}% complete</small></span><ChevronRight size={18} /></button>) : <EmptyState onCreate={() => undefined} />}</section>;
}

function NotificationPopover({ notifications, onDismiss }: { notifications: Notification[]; onDismiss: (notificationId: string) => void }) {
  return <section className="notification-popover" aria-label="Notifications">
    <div className="notification-popover-header"><div><span className="eyebrow">Updates</span><h3>Notifications</h3></div><span className="activity-count">{notifications.length}</span></div>
    {notifications.length ? <div className="notification-list">{notifications.map((notification) => <article className="notification-item" key={notification.notification_id}><span className="notification-dot"><Check size={13} /></span><div className="notification-content"><strong>{notification.event_type.replace(/([A-Z])/g, " $1").trim()}</strong><p>{notification.message}</p><small>{notification.status} · {formatDateTime(notification.created_at)}</small></div><button className="notification-item-close" title="Dismiss notification" aria-label={`Dismiss ${notification.event_type} notification`} onClick={() => onDismiss(notification.notification_id)}><X size={14} /></button></article>)}</div> : <p className="notification-empty">No notifications yet.</p>}
  </section>;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return <div className="empty-state"><div className="empty-icon"><Target size={24} /></div><span className="eyebrow">A blank page is a beginning</span><h3>Give your first goal a name.</h3><p>Emergency fund, next adventure, a little more breathing room. Start wherever feels right.</p><button className="primary-button" onClick={onCreate}><Plus size={17} /> Create first goal</button></div>;
}

function Modal({ title, subtitle, onClose, children }: { title: string; subtitle: string; onClose: () => void; children: React.ReactNode }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="modal" role="dialog" aria-modal="true" aria-label={title}><button className="modal-close" onClick={onClose} aria-label="Close"><X size={18} /></button><span className="eyebrow">Savings Bucket</span><h2>{title}</h2><p>{subtitle}</p>{children}</section></div>;
}

export default App;
