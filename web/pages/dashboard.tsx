// pages/dashboard.tsx

import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { auth } from "@/utils/firebase";
import { onAuthStateChanged } from "firebase/auth";
import { toUtf8Blob } from "@/utils/encoding";
import ShareActions from "@/components/ShareActions";

interface Dataset {
  tableId: string;
  filename: string;
  status: "pending" | "converted" | "shared";
}

export default function DashboardPage() {
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");

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

  // Poll for datasets every minute
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
    const interval = setInterval(fetchDatasets, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [userId]);

  // File picker handler
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
  };

  // Upload CSV to S3 via presigned URL
  const handleUpload = async () => {
    if (!userId || !selectedFile) {
      setStatusMessage("Please select a file and ensure you’re signed in.");
      return;
    }

    setStatusMessage("Requesting upload URL…");
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
      setStatusMessage("Failed to obtain upload URL.");
      return;
    }

    setStatusMessage("Uploading file…");
    const safeBlob = await toUtf8Blob(selectedFile);
    const uploadRes = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "text/csv" },
      body: safeBlob,
    });

    if (uploadRes.ok) {
      setStatusMessage("Upload complete! Processing will start shortly.");
      setSelectedFile(null);
      setLoading(true); // trigger refresh of dataset list
    } else {
      setStatusMessage("Upload failed. Please try again.");
    }
  };

  return (
    <main className="min-h-screen bg-gray-900 text-white px-6 py-10">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <p className="text-sm text-gray-300">
          {authReady ? `Signed in as ${userEmail}` : "Checking auth…"}
        </p>
      </div>

      {/* Overview Section */}
      <section className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow mb-8">
        <h2 className="text-2xl font-semibold mb-4 text-gray-900">
          Dashboard Overview
        </h2>
        <ul className="list-disc list-inside space-y-2 text-gray-700">
          <li>
            <strong>Upload a CSV:</strong> Select a CSV file to upload. Then
            click the “Upload New Dataset” button. This may take a minute or two
            as the file is processed.
          </li>
          <li>
            <strong>Share or Unshare:</strong> Use the “Share” button to
            register your dataset with the Delta Sharing server, or “Unshare” to
            revoke access.
          </li>
          <li>
            <strong>Copy Notebook Snippet:</strong> Grab the generated code
            snippet to run in any Jupyter notebook. It sets up your Delta
            Sharing profile and loads the table with a single call.
            ************** PLEASE NOTE AFTER FIRST UPLOADING FILE, DUE TO
            PROCESSING OF DATA AND RESTARTING OF SERVER IT CAN TAKE UPTO 5
            MINUTES FOR IT TO WORK IN A NOTEBOOK. IF GETTING ERROR IN NOTEBOOK
            JUST WAIT LONGER. **************
          </li>
          <li>
            <strong>Query the data:</strong> After you run the snippet you can
            query the data however you prefer, but some simple examples are:
            <ul className="list-inside ml-4 space-y-1">
              <li>
                <code>df.head()</code> – view the first few rows
              </li>
              <li>
                <code>df.describe()</code> – summary statistics
              </li>
              <li>
                <code>df[df[&quot;column&quot;] &gt; value]</code> – filter rows
              </li>
              <li>
                <code>df.groupby(&quot;column&quot;).size()</code> – group
                counts
              </li>
              <li>
                <code>df[&quot;category&quot;].value_counts()</code> – category
                frequencies
              </li>
            </ul>
          </li>
        </ul>
      </section>

      {/* Upload Section */}
      <div className="mb-6 max-w-2xl mx-auto">
        <label
          htmlFor="file-upload"
          className="
            flex flex-col items-center justify-center
            w-full h-24 px-4 py-4
            border border-dashed border-gray-500
            rounded-lg cursor-pointer
            hover:bg-gray-100
            bg-white text-gray-700
          "
        >
          {selectedFile ? (
            <span className="text-lg font-medium">{selectedFile.name}</span>
          ) : (
            <>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="w-10 h-10 mb-1 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16V4h10v12m-5-5l5 5H7l5-5z"
                />
              </svg>
              <span className="text-sm">Click to select a CSV</span>
            </>
          )}
          <input
            id="file-upload"
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="hidden"
            disabled={!authReady}
          />
        </label>

        <button
          disabled={!authReady || !selectedFile}
          onClick={handleUpload}
          className={`mt-2 px-5 py-2 rounded text-white ${
            !authReady || !selectedFile
              ? "bg-gray-700 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          Upload New Dataset
        </button>

        {statusMessage && (
          <p className="text-sm text-gray-400 mt-2">{statusMessage}</p>
        )}
      </div>

      {/* Dataset List */}
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-extrabold mb-4 text-white">
          Your Datasets
        </h1>
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
                  <h2 className="text-lg font-semibold text-white">
                    {ds.filename}
                  </h2>
                  <p className="text-gray-400 text-sm">Status: {ds.status}</p>
                </div>
                <ShareActions
                  tableId={ds.tableId}
                  status={ds.status}
                  onStatusChange={(newStatus) =>
                    setDatasets((prev) =>
                      prev.map((d) =>
                        d.tableId === ds.tableId
                          ? { ...d, status: newStatus as Dataset["status"] }
                          : d
                      )
                    )
                  }
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
