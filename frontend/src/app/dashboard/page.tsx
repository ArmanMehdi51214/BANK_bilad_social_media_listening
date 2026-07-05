"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import {
  getAiResults,
  getAiSummary,
  getCollectionJobs,
  getSchedulerStatus,
  runSchedulerNow,
} from "@/lib/api";
import type {
  AiResultItem,
  AiSummary,
  CollectionJob,
  SchedulerStatus,
} from "@/types/api";

export default function DashboardPage() {
  const router = useRouter();

  const [summary, setSummary] = useState<AiSummary | null>(null);
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [posts, setPosts] = useState<AiResultItem[]>([]);
  const [complaints, setComplaints] = useState<AiResultItem[]>([]);
  const [jobs, setJobs] = useState<CollectionJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningNow, setRunningNow] = useState(false);

  async function loadDashboard() {
    const [summaryData, schedulerData, postsData, complaintsData, jobsData] =
      await Promise.all([
        getAiSummary(),
        getSchedulerStatus(),
        getAiResults("brand_related=true&limit=20"),
        getAiResults("is_complaint=true&brand_related=true&limit=5"),
        getCollectionJobs("limit=5"),
      ]);

    setSummary(summaryData);
    setScheduler(schedulerData);
    setPosts(postsData.items);
    setComplaints(complaintsData.items);
    setJobs(jobsData.items);
  }

  useEffect(() => {
    if (!getAccessToken()) {
      router.push("/login");
      return;
    }

    loadDashboard()
      .catch(() => {
        clearAccessToken();
        router.push("/login");
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleRunNow() {
    setRunningNow(true);

    try {
      await runSchedulerNow();
      await loadDashboard();
    } finally {
      setRunningNow(false);
    }
  }

  function logout() {
    clearAccessToken();
    router.push("/login");
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-white">
        Loading dashboard...
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="border-b bg-white px-8 py-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-emerald-700">Bank Albilad</p>
            <h1 className="text-2xl font-bold text-slate-900">
              Executive Social Media Intelligence
            </h1>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => loadDashboard()}
              className="rounded-lg border px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Refresh
            </button>

            <button
              onClick={logout}
              className="rounded-lg border px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <section className="space-y-8 p-8">
        <div className="grid gap-5 md:grid-cols-4">
          <Kpi title="Total Posts" value={summary?.total_posts ?? 0} />
          <Kpi title="Analyzed Posts" value={summary?.analyzed_posts ?? 0} />
          <Kpi title="Complaints" value={summary?.complaint_count ?? 0} />
          <Kpi title="Scheduler" value={scheduler?.running ? "Running" : "Stopped"} />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Panel title="Sentiment">
            {summary?.sentiment_distribution.map((item) => (
              <Row key={item.sentiment_label} label={item.sentiment_label} value={item.count} />
            ))}
          </Panel>

          <Panel title="Top Topics">
            {summary?.topic_distribution.slice(0, 8).map((item) => (
              <Row key={item.slug} label={item.name} value={item.count} />
            ))}
          </Panel>

          <Panel title="Entities">
            {summary?.entity_distribution.map((item) => (
              <Row key={item.entity_type} label={item.entity_type} value={item.count} />
            ))}
          </Panel>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <Panel title="Latest Bank Albilad Mentions">
            <div className="space-y-4">
              {posts
                .filter(isClientRelevantPost)
                .slice(0, 5)
                .map((item) => (
                  <PostCard key={item.post.id} item={item} />
                ))}
            </div>
          </Panel>

          <Panel title="Latest Complaints">
            <div className="space-y-4">
              {complaints.map((item) => (
                <PostCard key={item.post.id} item={item} />
              ))}
            </div>
          </Panel>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <Panel title="Collection Jobs">
            <div className="space-y-3">
              {jobs.map((job) => (
                <div key={job.id} className="rounded-xl border p-4">
                  <div className="flex items-center justify-between gap-4">
                    <p className="font-semibold text-slate-900">{job.status}</p>
                    <p className="text-sm text-slate-500">{job.platform}</p>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">
                    Fetched: {job.total_fetched} | Inserted: {job.total_inserted} | Errors:{" "}
                    {job.total_errors}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{job.finished_at}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Scheduler Control">
            <p className="text-sm text-slate-600">
              Automatic X collection is configured as a background job.
            </p>

            <div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
              <p>Status: {scheduler?.running ? "Running" : "Stopped"}</p>
              <p>Jobs: {scheduler?.job_count ?? 0}</p>
              <p>Timezone: {scheduler?.timezone}</p>
            </div>

            <button
              onClick={handleRunNow}
              disabled={runningNow}
              className="mt-5 rounded-lg bg-emerald-700 px-4 py-3 font-semibold text-white hover:bg-emerald-800 disabled:opacity-60"
            >
              {runningNow ? "Collecting..." : "Run Collection Now"}
            </button>
          </Panel>
        </div>
      </section>
    </main>
  );
}

function isClientRelevantPost(item: AiResultItem): boolean {
  const text = `${item.post.clean_text || ""} ${item.post.raw_text || ""}`.trim();

  if (text.length < 15) {
    return false;
  }

  const isComplaint = item.analysis?.is_complaint === true;
  if (isComplaint) {
    return true;
  }

  const topics = item.topics.map((topic) => topic.slug);
  const isCompetitorOnly =
    topics.includes("competitor-discussions") &&
    !topics.includes("complaints") &&
    !topics.includes("customer-support") &&
    !topics.includes("accounts") &&
    !topics.includes("mobile-app") &&
    !topics.includes("payments") &&
    !topics.includes("cards") &&
    !topics.includes("financing") &&
    !topics.includes("loans");

  if (isCompetitorOnly) {
    return false;
  }

  const usefulBankingTopics = [
    "customer-support",
    "complaints",
    "accounts",
    "mobile-app",
    "payments",
    "cards",
    "branches",
    "atms",
    "financing",
    "loans",
    "transfers",
    "service-quality",
    "security",
  ];

  return topics.some((topic) => usefulBankingTopics.includes(topic));
}

function Kpi({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-3 text-3xl font-bold text-slate-900">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-bold text-slate-900">{title}</h2>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between border-b pb-2 text-sm">
      <span className="capitalize text-slate-600">{label.replaceAll("_", " ")}</span>
      <span className="font-semibold text-slate-900">{value}</span>
    </div>
  );
}

function PostCard({ item }: { item: AiResultItem }) {
  const sentiment = item.analysis?.sentiment_label ?? "unknown";

  return (
    <div className="rounded-xl border p-4">
      <div className="flex items-center justify-between gap-4">
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold capitalize text-slate-700">
          {sentiment}
        </span>
        {item.analysis?.is_complaint ? (
          <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">
            Complaint
          </span>
        ) : null}
      </div>

      <p className="mt-3 line-clamp-3 text-sm text-slate-700">
        {item.post.clean_text || item.post.raw_text || "No text"}
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {item.topics.slice(0, 3).map((topic) => (
          <span
            key={topic.slug}
            className="rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-700"
          >
            {topic.name}
          </span>
        ))}
      </div>

      {item.analysis?.is_complaint && item.post.source_url ? (
        <a
          href={item.post.source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-block text-sm font-semibold text-emerald-700 hover:underline"
        >
          Open original X post
        </a>
      ) : null}
    </div>
  );
}
