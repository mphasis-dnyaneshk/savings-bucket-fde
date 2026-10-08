import { FormEvent, useEffect, useState } from "react";
import {
  ArrowUpRight,
  Archive,
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
import type { Bucket, Contribution, Notification, Schedule, Transaction, View, Withdrawal } from "./types";

const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
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
  const [archivedBuckets, setArchivedBuckets] = useState<Bucket[]>([]);
  const [selectedBucket, setSelectedBucket] = useState<Bucket | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [clearingNotifications, setClearingNotifications] = useState(false);
  const [view, setView] = useState<View>("overview");
  const [modal, setModal] = useState<"create" | "contribute" | "withdraw" | "recurring" | "target" | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [overTargetChoice, setOverTargetChoice] = useState<{ amount: string; remaining: string } | null>(null);

  async function loadBuckets() {
    setLoading(true);
    setError("");
    try {
      const [activeResult, archivedResult] = await Promise.allSettled([
        api.listBuckets(),
        api.listArchivedBuckets(),
      ]);
      if (activeResult.status === "rejected") throw activeResult.reason;
      const nextBuckets = activeResult.value;
      const nextArchivedBuckets = archivedResult.status === "fulfilled"
        ? archivedResult.value
        : [];
      setBuckets(nextBuckets);
      setArchivedBuckets(nextArchivedBuckets);
      if (selectedBucket) {
        setSelectedBucket(
          nextBuckets.find((bucket) => bucket.bucket_id === selectedBucket.bucket_id)
          || nextArchivedBuckets.find((bucket) => bucket.bucket_id === selectedBucket.bucket_id)
          || null,
        );
      }
      if (archivedResult.status === "rejected") {
        setError("Active goals loaded, but the Archived list is unavailable. Restart bucket-service to enable it.");
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

  async function clearAllNotifications() {
    if (!notifications.length || clearingNotifications) return;
    setClearingNotifications(true);
    try {
      await api.clearNotifications();
      setNotifications([]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not clear notifications.");
    } finally {
      setClearingNotifications(false);
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
      if (bucket.status === "REACHED") {
        const pauseResult = await pauseActiveSchedules(bucket.bucket_id, nextSchedules);
        setSchedules(pauseResult.schedules);
        if (pauseResult.failed) setError("This goal is reached, but some recurring contributions could not be paused.");
      } else {
        setSchedules(nextSchedules);
      }
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

  async function createNotification(payload: { event_type: string; message: string }) {
    try {
      const notification = await api.createNotification(payload);
      setNotifications((current) => [notification, ...current]);
      return true;
    } catch {
      return false;
    }
  }

  async function pauseActiveSchedules(bucketId: string, scheduleList: Schedule[]) {
    const activeSchedules = scheduleList.filter((schedule) => schedule.status === "ACTIVE");
    const pauseResults = await Promise.allSettled(activeSchedules.map((schedule) =>
      api.updateSchedule(bucketId, schedule.schedule_id, { status: "PAUSED" }),
    ));
    const pausedById = new Map(pauseResults.flatMap((pause) => pause.status === "fulfilled" ? [[pause.value.schedule_id, pause.value] as const] : []));
    return {
      schedules: scheduleList.map((schedule) => pausedById.get(schedule.schedule_id) || schedule),
      failed: pauseResults.some((pause) => pause.status === "rejected"),
    };
  }

  async function handleMoneyAction(event: FormEvent<HTMLFormElement>, kind: "contribute" | "withdraw") {
    event.preventDefault();
    if (!selectedBucket) return;
    const form = new FormData(event.currentTarget);
    const amount = String(form.get("amount"));
    if (kind === "contribute") {
      setWorking(true);
      try {
        const latestBucket = await api.getBucket(selectedBucket.bucket_id);
        setSelectedBucket(latestBucket);
        setBuckets((current) => current.map((bucket) => bucket.bucket_id === latestBucket.bucket_id ? latestBucket : bucket));
        if (Number(amount) > Number(latestBucket.remaining_amount)) {
          setOverTargetChoice({ amount, remaining: latestBucket.remaining_amount });
          return;
        }
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Could not check the remaining goal amount.");
        return;
      } finally {
        setWorking(false);
      }
    }
    await processMoneyAction(kind, amount);
  }

  async function processMoneyAction(kind: "contribute" | "withdraw", amount: string, allowOverTarget = false) {
    if (!selectedBucket) return;
    setWorking(true);
    setError("");
    try {
      const result: Contribution | Withdrawal = kind === "contribute"
        ? await api.contribute(selectedBucket.bucket_id, amount, allowOverTarget)
        : await api.withdraw(selectedBucket.bucket_id, amount);
      const contribution = "goal_reached_now" in result ? result : null;
      let updatedBucket = selectedBucket;
      let refreshFailed = false;
      if (contribution?.bucket_current_balance && contribution.bucket_target_amount && contribution.bucket_remaining_amount && contribution.bucket_progress_percentage && contribution.bucket_status) {
        updatedBucket = {
          ...selectedBucket,
          current_balance: contribution.bucket_current_balance,
          target_amount: contribution.bucket_target_amount,
          remaining_amount: contribution.bucket_remaining_amount,
          progress_percentage: contribution.bucket_progress_percentage,
          status: contribution.bucket_status,
          updated_at: new Date().toISOString(),
        };
      } else {
        const bucketRefresh = await Promise.allSettled([api.getBucket(selectedBucket.bucket_id)]);
        if (bucketRefresh[0].status === "fulfilled") updatedBucket = bucketRefresh[0].value;
        else refreshFailed = true;
      }
      setBuckets((current) => current.map((bucket) => bucket.bucket_id === updatedBucket.bucket_id ? updatedBucket : bucket));
      setSelectedBucket(updatedBucket);

      const [transactionsResult, schedulesResult] = await Promise.allSettled([
        api.getTransactions(updatedBucket.bucket_id),
        api.listSchedules(updatedBucket.bucket_id),
      ]);
      if (transactionsResult.status === "fulfilled") setTransactions(transactionsResult.value);
      else refreshFailed = true;

      let recurringPauseFailed = false;
      if (contribution?.goal_reached_now) {
        if (schedulesResult.status === "rejected") {
          recurringPauseFailed = true;
        } else {
          const pauseResult = await pauseActiveSchedules(updatedBucket.bucket_id, schedulesResult.value);
          recurringPauseFailed = pauseResult.failed;
          setSchedules(pauseResult.schedules);
        }
      } else if (schedulesResult.status === "fulfilled") {
        setSchedules(schedulesResult.value);
      } else {
        refreshFailed = true;
      }

      setModal(null);
      setOverTargetChoice(null);
      const contributionNotificationSent = await createNotification({
        event_type: kind === "contribute" ? "ContributionCompleted" : "WithdrawalCompleted",
        message: `${kind === "contribute" ? "Contribution" : "Withdrawal"} of ${formatMoney(amount)} completed in mock mode.`,
      });
      let successMessage = `${kind === "contribute" ? "Contribution" : "Withdrawal"} ${result.status.toLowerCase()}.`;
      if (contribution?.goal_reached_now) {
        const target = Number(updatedBucket.target_amount);
        const balance = Number(updatedBucket.current_balance);
        const excess = Math.max(balance - target, 0);
        const goalReachedMessage = excess > 0
          ? `Congratulations, you reached ${updatedBucket.name} and saved ${formatMoney(excess)} above your ${formatMoney(target)} target. Your full balance is ${formatMoney(balance)}.`
          : `Congratulations, you reached your ${updatedBucket.name} goal of ${formatMoney(target)}.`;
        const scheduleMessage = recurringPauseFailed
          ? " Some recurring contributions could not be paused; please review them."
          : " Active recurring contributions have been paused.";
        const goalNotificationSent = await createNotification({
          event_type: "GoalReached",
          message: `${goalReachedMessage}${scheduleMessage}`,
        });
        successMessage = `${goalReachedMessage}${scheduleMessage}`;
        if (!goalNotificationSent) successMessage += " The in-app congratulations notification could not be saved.";
      }
      if (!contributionNotificationSent) successMessage += " The activity notification could not be saved.";
      if (refreshFailed) successMessage += " The contribution succeeded, but some goal details could not be refreshed.";
      setError(successMessage);
    } catch (requestError) {
      if (
        kind === "contribute"
        && requestError instanceof Error
        && requestError.message.includes("exceeds the remaining target")
      ) {
        const remainingFromServer = requestError.message.match(/remaining target of ([\d.]+)/)?.[1];
        setOverTargetChoice({ amount, remaining: remainingFromServer || selectedBucket.remaining_amount });
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "The request completed, but the latest goal details could not be loaded.");
    } finally {
      setWorking(false);
    }
  }

  async function handleUpdateTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBucket) return;
    const form = new FormData(event.currentTarget);
    setWorking(true);
    setError("");
    try {
      const previousStatus = selectedBucket.status;
      const updatedBucket = await api.updateBucketTarget(
        selectedBucket.bucket_id,
        String(form.get("target_amount")),
      );
      setSelectedBucket(updatedBucket);
      setBuckets((current) => current.map((bucket) => bucket.bucket_id === updatedBucket.bucket_id ? updatedBucket : bucket));
      setModal(null);
      if (previousStatus !== "REACHED" && updatedBucket.status === "REACHED") {
        let pauseFailed = false;
        const schedulesResult = await Promise.allSettled([api.listSchedules(updatedBucket.bucket_id)]);
        if (schedulesResult[0].status === "fulfilled") {
          const pauseResult = await pauseActiveSchedules(updatedBucket.bucket_id, schedulesResult[0].value);
          pauseFailed = pauseResult.failed;
          setSchedules(pauseResult.schedules);
        } else {
          pauseFailed = true;
        }
        const excess = Math.max(Number(updatedBucket.current_balance) - Number(updatedBucket.target_amount), 0);
        const balanceMessage = excess > 0
          ? ` Its balance is ${formatMoney(updatedBucket.current_balance)}, including ${formatMoney(excess)} above target.`
          : ` Its balance is ${formatMoney(updatedBucket.current_balance)}.`;
        const targetMessage = pauseFailed
          ? `Your updated ${updatedBucket.name} target is already met.${balanceMessage} Some recurring contributions could not be paused. Please review them.`
          : `Your updated ${updatedBucket.name} target is already met.${balanceMessage} Active recurring contributions have been paused.`;
        const notificationSent = await createNotification({ event_type: "GoalReached", message: targetMessage });
        setError(notificationSent ? targetMessage : `${targetMessage} The in-app notification could not be saved.`);
      } else {
        setError("Savings goal target updated.");
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update the savings goal target.");
    } finally {
      setWorking(false);
    }
  }

  async function archiveSelectedBucket() {
    if (!selectedBucket) return;
    setWorking(true);
    setError("");
    try {
      const currentSchedules = await api.listSchedules(selectedBucket.bucket_id);
      if (currentSchedules.some((schedule) => schedule.status === "ACTIVE")) {
        setError("Pause all recurring contributions before archiving this goal.");
        return;
      }
      const archivedBucket = await api.archiveBucket(selectedBucket.bucket_id);
      setBuckets((current) => current.filter((bucket) => bucket.bucket_id !== archivedBucket.bucket_id));
      setArchivedBuckets((current) => [archivedBucket, ...current.filter((bucket) => bucket.bucket_id !== archivedBucket.bucket_id)]);
      setSelectedBucket(archivedBucket);
      setError("Goal archived. You can find it in the Archived tab.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not archive this goal.");
    } finally {
      setWorking(false);
    }
  }

  async function restoreBucket(bucket: Bucket) {
    setWorking(true);
    setError("");
    try {
      const restoredBucket = await api.restoreBucket(bucket.bucket_id);
      setArchivedBuckets((current) => current.filter((item) => item.bucket_id !== bucket.bucket_id));
      setBuckets((current) => [restoredBucket, ...current]);
      setSelectedBucket(restoredBucket);
      setView("bucket");
      setTransactions(await api.getTransactions(restoredBucket.bucket_id));
      setSchedules(await api.listSchedules(restoredBucket.bucket_id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not restore this goal.");
    } finally {
      setWorking(false);
    }
  }

  async function handleRecurring(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBucket) return;
    if (selectedBucket.status === "REACHED") {
      setError("This goal is reached. Change its target before starting recurring contributions again.");
      return;
    }
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
    if (status === "ACTIVE" && selectedBucket.status === "REACHED") {
      setError("This goal is reached. Change its target before resuming recurring contributions.");
      return;
    }
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
          <button className={view === "goals" || view === "bucket" ? "nav-item active" : "nav-item"} onClick={() => navigate("goals")}><Target size={18} /> Goals</button>
          <button className={view === "activity" ? "nav-item active" : "nav-item"} onClick={() => navigate("activity")}><Clock3 size={18} /> Activity</button>
          <button className={view === "archived" ? "nav-item active" : "nav-item"} onClick={() => navigate("archived")}><Archive size={18} /> Archived</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="mode-note"><span className="status-dot" /> Local mock mode</div>
          <button className="nav-item"><Settings2 size={18} /> Settings</button>
          <div className="profile"><span className="avatar">C</span><span><strong>Customer 001</strong><small>Demo profile</small></span></div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div><span className="breadcrumb">Savings / {view === "overview" ? "Overview" : view === "activity" ? "Activity" : view === "goals" ? "Goals" : view === "archived" ? "Archived" : selectedBucket?.name || "Goal"}</span><h1>{view === "overview" ? "Your savings, in view." : view === "activity" ? "Activity" : view === "goals" ? "Your savings goals" : view === "archived" ? "Archived goals" : selectedBucket?.name || "Goal detail"}</h1></div>
          <div className="top-actions"><button className="icon-button" title="Refresh data" onClick={() => { void loadBuckets(); void loadNotifications(); }}><RefreshCw size={18} /></button><div className="notification-wrap"><button className="notification-button" title="Notifications" aria-label="Notifications" aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((open) => !open)}><Bell size={18} />{notifications.length > 0 && <span>{notifications.length}</span>}</button>{notificationsOpen && <NotificationPopover notifications={notifications} onDismiss={(notificationId) => void dismissNotification(notificationId)} onClearAll={() => void clearAllNotifications()} clearing={clearingNotifications} />}</div><button className="primary-button" onClick={() => setModal("create")}><Plus size={18} /> New goal</button></div>
        </header>

        {error && <div className="notice" role="status"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss message"><X size={16} /></button></div>}

        {loading ? <div className="loading-state"><LoaderCircle className="spin" size={28} /><span>Loading your goals...</span></div> : view === "overview" ? (
          <Overview buckets={buckets} totalSaved={totalSaved} totalTarget={totalTarget} totalProgress={totalProgress} onSelect={selectBucket} onCreate={() => setModal("create")} />
        ) : view === "goals" ? (
          <Goals buckets={buckets} onSelect={selectBucket} onCreate={() => setModal("create")} />
        ) : view === "activity" ? (
          <Activity buckets={buckets} onSelect={selectBucket} />
        ) : view === "archived" ? (
          <ArchivedGoals buckets={archivedBuckets} onSelect={selectBucket} />
        ) : selectedBucket ? (
          <BucketDetail bucket={selectedBucket} transactions={transactions} schedules={schedules} onBack={() => navigate(selectedBucket.status === "ARCHIVED" ? "archived" : "goals")} onContribute={() => { setOverTargetChoice(null); setModal("contribute"); }} onWithdraw={() => setModal("withdraw")} onRecurring={() => setModal("recurring")} onChangeTarget={() => setModal("target")} onArchive={() => void archiveSelectedBucket()} onRestore={() => void restoreBucket(selectedBucket)} working={working} onToggleSchedule={toggleSchedule} />
        ) : <EmptyState onCreate={() => setModal("create")} />}
      </main>

      {modal === "create" && <Modal title="Create a savings goal" subtitle="Give your next milestone a clear place to grow." onClose={() => setModal(null)}><form className="form-stack" onSubmit={handleCreate}><label>Goal name<input name="name" placeholder="Emergency Fund" required autoFocus /></label><label>Target amount<input name="target_amount" type="number" min="1" step="0.01" placeholder="100000" required /></label><label>Target date <span className="optional">optional</span><input name="target_date" type="date" /></label>{buckets.length >= 10 && <div className="safe-copy warning" role="alert">You can create a maximum of 10 savings buckets per account.</div>}{error && <div className="safe-copy warning" role="alert">{error}</div>}<button className="primary-button full-width" disabled={working || buckets.length >= 10}>{working ? "Creating..." : buckets.length >= 10 ? "Maximum reached" : "Create goal"} <ArrowUpRight size={17} /></button></form></Modal>}
      {modal === "contribute" && <Modal title="Add money" subtitle={`Assign savings to ${selectedBucket?.name}.`} onClose={() => { setModal(null); setOverTargetChoice(null); }}><form className="form-stack" onSubmit={(event) => void handleMoneyAction(event, "contribute")}><div className="context-row"><WalletCards size={18} /><span>Mock funding account</span><strong>Available</strong></div><label>Contribution amount<input name="amount" type="number" min="0.01" step="0.01" placeholder="1000" required autoFocus /></label>{overTargetChoice && <div className="over-target-choice" role="alert"><strong>This contribution is above the remaining target.</strong><p>{formatMoney(overTargetChoice.remaining)} remains. Choose whether to stop at the target or contribute the full {formatMoney(overTargetChoice.amount)}.</p>{Number(overTargetChoice.remaining) > 0 && <button className="secondary-button full-width" type="button" disabled={working} onClick={() => void processMoneyAction("contribute", overTargetChoice.remaining)}>Add only {formatMoney(overTargetChoice.remaining)}</button>}<button className="primary-button full-width" type="button" disabled={working} onClick={() => void processMoneyAction("contribute", overTargetChoice.amount, true)}>Contribute full amount</button><button className="text-button" type="button" onClick={() => setOverTargetChoice(null)}>Change amount</button></div>}<div className="safe-copy"><Check size={16} /> This demo uses mock financial processing.</div><button className="primary-button full-width" disabled={working || Boolean(overTargetChoice)}>{working ? "Checking..." : "Review contribution"} <ArrowUpRight size={17} /></button></form></Modal>}
      {modal === "withdraw" && <Modal title="Withdraw savings" subtitle={`Return assigned savings from ${selectedBucket?.name}.`} onClose={() => setModal(null)}><form className="form-stack" onSubmit={(event) => void handleMoneyAction(event, "withdraw")}><div className="balance-callout"><span>Current allocated balance</span><strong>{formatMoney(selectedBucket?.current_balance || 0)}</strong></div><label>Withdrawal amount<input name="amount" type="number" min="0.01" step="0.01" placeholder="500" required autoFocus /></label><div className="safe-copy warning"><Check size={16} /> Mock mode will return a successful result.</div><button className="primary-button dark full-width" disabled={working}>{working ? "Processing..." : "Review withdrawal"} <ArrowUpRight size={17} /></button></form></Modal>}
      {modal === "recurring" && <Modal title="Set a recurring contribution" subtitle="Turn a small habit into steady progress." onClose={() => setModal(null)}><form className="form-stack" onSubmit={(event) => void handleRecurring(event)}><label>Amount<input name="amount" type="number" min="0.01" step="0.01" placeholder="1000" required autoFocus /></label><label>Frequency<select name="frequency" defaultValue="MONTHLY"><option value="WEEKLY">Weekly</option><option value="MONTHLY">Monthly</option><option value="QUARTERLY">Quarterly</option></select></label><label>Start date<input name="start_date" type="date" defaultValue={new Date().toISOString().slice(0, 10)} required /></label><button className="primary-button full-width" disabled={working}>{working ? "Saving..." : "Schedule contribution"} <ArrowUpRight size={17} /></button></form></Modal>}
      {modal === "target" && selectedBucket && <Modal title="Change goal target" subtitle={`Set a new target for ${selectedBucket.name}.`} onClose={() => setModal(null)}><form className="form-stack" onSubmit={(event) => void handleUpdateTarget(event)}><label>New target amount<input name="target_amount" type="number" min="1" step="0.01" defaultValue={selectedBucket.target_amount} required autoFocus /></label><button className="primary-button full-width" disabled={working}>{working ? "Saving..." : "Save new target"} <ArrowUpRight size={17} /></button></form></Modal>}
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
  return <button className="bucket-card" onClick={onClick}><div className="card-top"><span className="goal-icon"><Target size={19} /></span><span className="card-arrow"><ArrowUpRight size={17} /></span></div><div className="card-title"><h3>{bucket.name}</h3><span>{bucket.status === "ARCHIVED" ? "Archived" : formatDate(bucket.target_date)}</span></div><div className="progress-line"><span style={{ width: `${progress}%` }} /></div><div className="card-numbers"><strong>{formatMoney(bucket.current_balance)}</strong><span>of {formatMoney(bucket.target_amount)}</span><b>{progress.toFixed(0)}%</b></div></button>;
}

function Goals({ buckets, onSelect, onCreate }: { buckets: Bucket[]; onSelect: (bucket: Bucket) => void; onCreate: () => void }) {
  return <section className="activity-page"><div className="section-heading"><div><span className="eyebrow">Goals</span><h2>Your savings goals</h2></div><button className="primary-button" onClick={onCreate}><Plus size={17} /> New goal</button></div>{buckets.length ? <div className="bucket-grid">{buckets.map((bucket) => <BucketCard key={bucket.bucket_id} bucket={bucket} onClick={() => onSelect(bucket)} />)}</div> : <EmptyState onCreate={onCreate} />}</section>;
}

function ArchivedGoals({ buckets, onSelect }: { buckets: Bucket[]; onSelect: (bucket: Bucket) => void }) {
  return <section className="activity-page"><div className="section-heading"><div><span className="eyebrow">History</span><h2>Archived goals</h2></div><span className="activity-count">{buckets.length} goals</span></div>{buckets.length ? <div className="bucket-grid">{buckets.map((bucket) => <BucketCard key={bucket.bucket_id} bucket={bucket} onClick={() => onSelect(bucket)} />)}</div> : <div className="empty-state"><div className="empty-icon"><Archive size={24} /></div><span className="eyebrow">Your history stays here</span><h3>No archived goals</h3><p>Goals you archive after reaching and emptying them will appear here.</p></div>}</section>;
}

function ArchiveReadyGoalDetail({ bucket, transactions, onBack, onArchive, onContribute, working }: { bucket: Bucket; transactions: Transaction[]; onBack: () => void; onArchive: () => void; onContribute: () => void; working: boolean }) {
  return <div className="detail-layout"><button className="back-button" onClick={onBack}>← All goals</button><div className="detail-header"><div><span className="eyebrow">Goal reached</span><h2>{bucket.name}</h2><p>Reached {bucket.reached_at ? formatDateTime(bucket.reached_at) : "previously"}</p></div><span className="pill success">Ready to archive</span></div><section className="goal-reached-banner"><div><strong>This goal has been reached and its balance is zero.</strong><p>Archiving keeps the goal and its transaction history in the Archived tab.</p></div><button className="secondary-button" onClick={onContribute}><Plus size={17} /> Continue saving</button><button className="primary-button" disabled={working} onClick={onArchive}><Archive size={17} /> {working ? "Archiving..." : "Archive goal"}</button></section><section className="activity-panel"><div className="panel-heading"><div><span className="eyebrow">History</span><h3>Money movement</h3></div><span className="activity-count">{transactions.length} records</span></div>{transactions.length ? transactions.slice(0, 5).map((transaction) => <div className="transaction-row" key={transaction.transaction_id}><span className={`transaction-icon ${transaction.type.toLowerCase()}`}>{transaction.type === "CONTRIBUTION" ? "+" : "−"}</span><div><strong>{transaction.type}</strong><span>{formatDateTime(transaction.created_at)} · {transaction.status}</span></div><b>{formatMoney(transaction.amount)}</b></div>) : <div className="empty-inline"><p>No activity yet.</p></div>}</section></div>;
}

function ArchivedBucketDetail({ bucket, transactions, onBack, onRestore, working }: { bucket: Bucket; transactions: Transaction[]; onBack: () => void; onRestore: () => void; working: boolean }) {
  return <div className="detail-layout"><button className="back-button" onClick={onBack}>← Archived goals</button><div className="detail-header"><div><span className="eyebrow">Archived goal</span><h2>{bucket.name}</h2><p>Archived {bucket.archived_at ? formatDateTime(bucket.archived_at) : "previously"}</p></div><span className="pill success">Archived</span></div><section className="goal-reached-banner"><div><strong>Goal history is preserved.</strong><p>Reached {bucket.reached_at ? formatDateTime(bucket.reached_at) : "previously"}. Final balance: {formatMoney(bucket.current_balance)}.</p></div><button className="secondary-button" disabled={working} onClick={onRestore}>{working ? "Restoring..." : "Restore goal"}</button></section><section className="activity-panel"><div className="panel-heading"><div><span className="eyebrow">History</span><h3>Money movement</h3></div><span className="activity-count">{transactions.length} records</span></div>{transactions.length ? transactions.map((transaction) => <div className="transaction-row" key={transaction.transaction_id}><span className={`transaction-icon ${transaction.type.toLowerCase()}`}>{transaction.type === "CONTRIBUTION" ? "+" : "−"}</span><div><strong>{transaction.type}</strong><span>{formatDateTime(transaction.created_at)} · {transaction.status}</span></div><b>{formatMoney(transaction.amount)}</b></div>) : <div className="empty-inline"><p>No activity recorded for this goal.</p></div>}</section></div>;
}

function BucketDetail({ bucket, transactions, schedules, onBack, onContribute, onWithdraw, onRecurring, onChangeTarget, onArchive, onRestore, working, onToggleSchedule }: { bucket: Bucket; transactions: Transaction[]; schedules: Schedule[]; onBack: () => void; onContribute: () => void; onWithdraw: () => void; onRecurring: () => void; onChangeTarget: () => void; onArchive: () => void; onRestore: () => void; working: boolean; onToggleSchedule: (schedule: Schedule) => void }) {
  const progress = Number(bucket.progress_percentage);
  if (bucket.status === "ARCHIVED") {
    return <ArchivedBucketDetail bucket={bucket} transactions={transactions} onBack={onBack} onRestore={onRestore} working={working} />;
  }
  if (bucket.reached_at && Number(bucket.current_balance) === 0) {
    return <ArchiveReadyGoalDetail bucket={bucket} transactions={transactions} onBack={onBack} onArchive={onArchive} onContribute={onContribute} working={working} />;
  }
    if (bucket.status === "REACHED") {
      return <ReachedGoalDetail bucket={bucket} transactions={transactions} schedules={schedules} onBack={onBack} onContribute={onContribute} onWithdraw={onWithdraw} onChangeTarget={onChangeTarget} onToggleSchedule={onToggleSchedule} />;
    }
    return <div className="detail-layout"><button className="back-button" onClick={onBack}>← All goals</button><div className="detail-header"><div><span className="eyebrow">Goal detail</span><h2>{bucket.name}</h2><p>Target date {formatDate(bucket.target_date)}</p></div><span className="pill success">{bucket.status}</span></div><div className="detail-grid"><section className="balance-panel"><div className="balance-label"><span>Saved toward goal</span><span>{progress.toFixed(0)}%</span></div><strong>{formatMoney(bucket.current_balance)}</strong><div className="large-progress"><span style={{ width: `${progress}%` }} /></div><div className="balance-meta"><span>{formatMoney(bucket.remaining_amount)} remaining</span><span>Target {formatMoney(bucket.target_amount)}</span></div><div className="action-row"><button className="primary-button" onClick={onContribute}><Plus size={17} /> Add money</button><button className="secondary-button" onClick={onWithdraw}>Withdraw</button></div></section><section className="side-panel"><div className="panel-heading"><div><span className="eyebrow">Automate</span><h3>Recurring contribution</h3></div><CalendarDays size={20} /></div>{schedules.length ? schedules.map((schedule) => <div className="schedule-row" key={schedule.schedule_id}><div><strong>{formatMoney(schedule.amount)} · {schedule.frequency}</strong><span>Next on {formatDate(schedule.next_execution_date)}</span></div><button className={`status-toggle ${schedule.status.toLowerCase()}`} onClick={() => onToggleSchedule(schedule)}>{schedule.status === "ACTIVE" ? "Pause" : "Resume"}</button></div>) : <div className="empty-inline"><p>No recurring contribution yet.</p><button className="text-button" onClick={onRecurring}>Set one up <ChevronRight size={16} /></button></div>}</section></div><section className="activity-panel"><div className="panel-heading"><div><span className="eyebrow">Recent activity</span><h3>Money movement</h3></div><span className="activity-count">{transactions.length} records</span></div>{transactions.length ? transactions.map((transaction) => <div className="transaction-row" key={transaction.transaction_id}><span className={`transaction-icon ${transaction.type.toLowerCase()}`}>{transaction.type === "CONTRIBUTION" ? "+" : "−"}</span><div><strong>{transaction.type}</strong><span>{formatDate(transaction.created_at)} · {transaction.status}</span></div><b>{formatMoney(transaction.amount)}</b></div>) : <div className="empty-inline"><p>Your confirmed activity will appear here.</p><span className="muted">Mock contributions and withdrawals are tracked by their own services.</span></div>}</section></div>;
    }

function ReachedGoalDetail({ bucket, transactions, schedules, onBack, onContribute, onWithdraw, onChangeTarget, onToggleSchedule }: { bucket: Bucket; transactions: Transaction[]; schedules: Schedule[]; onBack: () => void; onContribute: () => void; onWithdraw: () => void; onChangeTarget: () => void; onToggleSchedule: (schedule: Schedule) => void }) {
  const excess = Math.max(Number(bucket.current_balance) - Number(bucket.target_amount), 0);
  return <div className="detail-layout"><button className="back-button" onClick={onBack}>← All goals</button><div className="detail-header"><div><span className="eyebrow">Goal detail</span><h2>{bucket.name}</h2><p>Target date {formatDate(bucket.target_date)}</p></div><span className="pill success">Goal reached</span></div><section className="goal-reached-banner" role="status"><div><strong>Congratulations, you reached your goal.</strong><p>Your target is {formatMoney(bucket.target_amount)} and your full balance is {formatMoney(bucket.current_balance)}{excess > 0 ? `, including ${formatMoney(excess)} above target.` : "."} Active recurring contributions are paused.</p></div><button className="secondary-button" onClick={onChangeTarget}>Change target</button></section><div className="detail-grid"><section className="balance-panel"><div className="balance-label"><span>Saved toward goal</span><span>100%</span></div><strong>{formatMoney(bucket.current_balance)}</strong><div className="large-progress"><span style={{ width: "100%" }} /></div><div className="balance-meta"><span>{formatMoney(excess)} above target</span><span>Target {formatMoney(bucket.target_amount)}</span></div><div className="action-row"><button className="primary-button" onClick={onContribute}><Plus size={17} /> Continue saving</button><button className="secondary-button" onClick={onWithdraw}>Withdraw</button></div></section><section className="side-panel"><div className="panel-heading"><div><span className="eyebrow">Automate</span><h3>Recurring contribution</h3></div><CalendarDays size={20} /></div>{schedules.length ? schedules.map((schedule) => <div className="schedule-row" key={schedule.schedule_id}><div><strong>{formatMoney(schedule.amount)} · {schedule.frequency}</strong><span>{schedule.status === "PAUSED" ? "Paused at goal completion" : `Next on ${formatDate(schedule.next_execution_date)}`}</span></div><button className={`status-toggle ${schedule.status.toLowerCase()}`} disabled={schedule.status !== "ACTIVE"} onClick={() => onToggleSchedule(schedule)}>{schedule.status === "ACTIVE" ? "Pause" : "Paused"}</button></div>) : <div className="empty-inline"><p>Recurring contributions are paused while this goal is reached.</p></div>}<button className="text-button" onClick={onChangeTarget}>Change target to resume recurring contributions <ChevronRight size={16} /></button></section></div><section className="activity-panel"><div className="panel-heading"><div><span className="eyebrow">Recent activity</span><h3>Money movement</h3></div><span className="activity-count">{transactions.length} records</span></div>{transactions.length ? transactions.slice(0, 5).map((transaction) => <div className="transaction-row" key={transaction.transaction_id}><span className={`transaction-icon ${transaction.type.toLowerCase()}`}>{transaction.type === "CONTRIBUTION" ? "+" : "−"}</span><div><strong>{transaction.type}</strong><span>{formatDateTime(transaction.created_at)} · {transaction.status}</span></div><b>{formatMoney(transaction.amount)}</b></div>) : <div className="empty-inline"><p>No activity yet.</p></div>}</section></div>;
}

function Activity({ buckets, onSelect }: { buckets: Bucket[]; onSelect: (bucket: Bucket) => void }) {
  return <section className="activity-page"><div className="section-heading"><div><span className="eyebrow">Activity</span><h2>All your goals, one glance</h2></div></div>{buckets.length ? buckets.map((bucket) => <button className="activity-bucket" key={bucket.bucket_id} onClick={() => onSelect(bucket)}><span className="goal-icon"><Target size={18} /></span><span><strong>{bucket.name}</strong><small>{formatMoney(bucket.current_balance)} saved · {Number(bucket.progress_percentage).toFixed(0)}% complete</small></span><ChevronRight size={18} /></button>) : <EmptyState onCreate={() => undefined} />}</section>;
}

function NotificationPopover({ notifications, onDismiss, onClearAll, clearing }: { notifications: Notification[]; onDismiss: (notificationId: string) => void; onClearAll: () => void; clearing: boolean }) {
  return <section className="notification-popover" aria-label="Notifications">
    <div className="notification-popover-header"><div><span className="eyebrow">Updates</span><h3>Notifications</h3></div><div className="notification-actions"><span className="activity-count">{notifications.length}</span>{notifications.length > 0 && <button className="text-button" disabled={clearing} onClick={onClearAll}>{clearing ? "Clearing..." : "Clear all"}</button>}</div></div>
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
