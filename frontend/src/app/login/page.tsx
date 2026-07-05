"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("admin@bankalbilad.com");
  const [password, setPassword] = useState("Admin@12345");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(email, password);
      router.push("/dashboard");
    } catch {
      setError("Login failed. Please check your email and password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 flex items-center justify-center px-6">
      <section className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl">
        <div className="mb-8">
          <p className="text-sm font-semibold text-emerald-700">Bank Albilad</p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">
            Executive Social Media Intelligence
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Sign in to access the Milestone 1 dashboard.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Email
            </label>
            <input
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-emerald-600"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              required
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Password
            </label>
            <input
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-emerald-600"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              required
            />
          </div>

          {error ? (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-emerald-700 px-4 py-3 font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
