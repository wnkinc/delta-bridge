import React, { useState } from "react";

interface ShareResponse {
  profile: {
    shareCredentialsVersion: number;
    endpoint: string;
    bearerToken: string;
  };
  snippet: {
    tableUrl: string;
    notebookSnippet?: string;
  };
  status: string;
}

interface ShareActionsProps {
  tableId: string;
  status: "pending" | "converted" | "shared";
  onStatusChange: (newStatus: string) => void;
}

const ShareActions: React.FC<ShareActionsProps> = ({
  tableId,
  status,
  onStatusChange,
}) => {
  const [loading, setLoading] = useState(false);
  const [snippetText, setSnippetText] = useState<string>("");
  const [showModal, setShowModal] = useState(false);
  const [copied, setCopied] = useState(false); // new

  // helper to build the Python snippet
  const buildSnippet = (
    profile: ShareResponse["profile"],
    tableUrl: string
  ) => `!pip install delta-sharing
import json

profile = ${JSON.stringify(profile, null, 2)}

with open('share_creds.json','w') as f:
    json.dump(profile,f)

import delta_sharing

df = delta_sharing.load_as_pandas('share_creds.json#${tableUrl.replace(
    "share://",
    ""
  )}')
df.head()
`;

  // --- share
  const doShare = async () => {
    setLoading(true);
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/share`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tableId }),
    });
    const data: ShareResponse = await res.json();
    setLoading(false);

    if (res.ok) {
      onStatusChange("shared");
      const text =
        data.snippet.notebookSnippet ??
        buildSnippet(data.profile, data.snippet.tableUrl);
      setSnippetText(text);
      setShowModal(true);
      setCopied(false);
    }
  };

  // --- unshare
  const doUnshare = async () => {
    setLoading(true);
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/unshare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tableId }),
    });
    setLoading(false);
    if (res.ok) {
      onStatusChange("converted");
      setSnippetText("");
      setShowModal(false);
    }
  };

  // --- view snippet
  const doViewSnippet = async () => {
    setLoading(true);
    const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/snippet`);
    url.searchParams.set("tableId", tableId);
    const res = await fetch(url.toString(), {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    const payload: { notebookSnippet?: string; error?: string } =
      await res.json();
    setLoading(false);

    if (res.ok && payload.notebookSnippet) {
      setSnippetText(payload.notebookSnippet);
      setShowModal(true);
      setCopied(false);
    } else {
      console.error("Failed to load snippet:", payload.error);
      alert(
        payload.error || "Could not fetch snippet. Check console for details."
      );
    }
  };

  // --- copy handler
  const handleCopy = () => {
    navigator.clipboard.writeText(snippetText);
    setCopied(true);
    // clear after 2 seconds
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <>
      {status === "converted" && (
        <button
          disabled={loading}
          onClick={doShare}
          className="px-4 py-2 bg-green-600 rounded hover:bg-green-700 disabled:opacity-50"
        >
          {loading ? "Sharing..." : "Share"}
        </button>
      )}

      {status === "shared" && (
        <>
          <button
            disabled={loading}
            onClick={doUnshare}
            className="px-4 py-2 bg-red-600 rounded hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? "Unsharing..." : "Unshare"}
          </button>

          <button
            disabled={loading}
            onClick={doViewSnippet}
            className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700 ml-2 disabled:opacity-50"
          >
            {loading ? "Loading snippet..." : "View Snippet"}
          </button>
        </>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4">
          <div className="bg-gray-800 p-6 rounded max-w-lg w-full">
            <h3 className="text-xl font-semibold mb-4 text-white">Snippet</h3>
            <textarea
              readOnly
              className="w-full h-40 p-2 bg-gray-900 text-green-200 rounded"
              value={snippetText}
            />

            <div className="mt-4 flex items-center space-x-2 justify-end">
              <button
                onClick={handleCopy}
                className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700"
              >
                Copy to clipboard
              </button>
              {/* copied indicator */}
              {copied && (
                <span className="text-sm text-green-400">Copied!</span>
              )}

              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 bg-gray-600 rounded hover:bg-gray-500"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ShareActions;
