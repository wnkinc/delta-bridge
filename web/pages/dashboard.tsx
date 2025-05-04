// pages/dashboard.tsx

import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { auth } from "@/utils/firebase";
import { onAuthStateChanged } from "firebase/auth";
import { toUtf8Blob } from "@/utils/encoding";

interface Dataset {
  tableId: string;
  filename: string;
  status: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);

  // Auth listener
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (!user) {
        router.push("/login");
      } else {
        setUserEmail(user.email);
        setUserId(user.uid);
        setAuthReady(true);
      }
    });
    return unsubscribe;
  }, [router]);

  // Poll for datasets
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;

    async function fetchDatasets() {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/datasets?userId=${userId}`,
          { credentials: "include" }
        );
        const json = await res.json();
        if (!cancelled) {
          setDatasets(json.datasets || []);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    }

    fetchDatasets();
    const id = setInterval(fetchDatasets, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [userId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!userId || !selectedFile) {
      setStatus("Please select a file and ensure you’re signed in.");
      return;
    }

    setStatus("Requesting upload URL…");
    const presignRes = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/presign`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, filename: selectedFile.name }),
      }
    );
    const presignData = await presignRes.json();
    const url = presignData.url as string;
    if (!url) {
      setStatus("Failed to obtain upload URL.");
      return;
    }

    setStatus("Uploading file…");
    const safeBlob = await toUtf8Blob(selectedFile);
    const uploadRes = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "text/csv" },
      body: safeBlob,
    });

    if (uploadRes.ok) {
      setStatus("Upload complete! Processing will start shortly.");
      setSelectedFile(null);
      // Immediately poll again to pick up new entry
      setLoading(true);
    } else {
      setStatus("Upload failed. Please try again.");
    }
  };

  return (
    <main className="min-h-screen bg-gray-900 text-white px-6 py-10">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-extrabold">Your Datasets</h1>
        <p className="text-sm text-gray-300">
          {authReady ? `Signed in as ${userEmail}` : "Checking auth…"}
        </p>
      </div>

      {/* Upload Section */}
      <div className="mb-6 space-y-2">
        <label className="block text-gray-300">Select CSV File to Upload</label>
        <input
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          className="block w-full max-w-xs p-2 bg-white text-black rounded"
          disabled={!authReady}
        />
        <button
          disabled={!authReady || !selectedFile}
          onClick={handleUpload}
          className={`px-5 py-2 rounded transition text-white ${
            !authReady || !selectedFile
              ? "bg-gray-700 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          Upload New Dataset
        </button>
        {status && <p className="text-sm text-gray-400">{status}</p>}
      </div>

      {/* Dataset Cards or Loading */}
      {loading ? (
        <div className="text-center text-gray-400">Loading datasets…</div>
      ) : (
        <div className="grid gap-6">
          {datasets.map((ds) => (
            <div
              key={ds.tableId}
              className="bg-gray-800 p-4 rounded shadow flex justify-between items-center"
            >
              <div>
                <h2 className="text-lg font-semibold">{ds.filename}</h2>
                <p className="text-gray-400 text-sm">Status: {ds.status}</p>
              </div>
              {/* Share/Unshare buttons will go here */}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
