import React, { useState } from "react";

interface ShareResponse {
  profile: {
    shareCredentialsVersion: number;
    endpoint: string;
    bearerToken: string;
  };
  snippet: {
    tableUrl: string;
    ssmCommandId: string;
  };
  status: string;
}

interface ShareActionsProps {
  tableId: string;
  status: string; // "pending" | "converted" | "shared"
  onStatusChange: (newStatus: string) => void;
}

const ShareActions: React.FC<ShareActionsProps> = ({
  tableId,
  status,
  onStatusChange,
}) => {
  const [loading, setLoading] = useState(false);
  const [shareData, setShareData] = useState<ShareResponse | null>(null);
  const [showModal, setShowModal] = useState(false);

  const doShare = async () => {
    setLoading(true);
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/share`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tableId }),
    });
    const data = await res.json();
    setLoading(false);
    if (res.ok) {
      onStatusChange("shared");
      setShareData(data);
      setShowModal(true);
    }
  };

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
      // optionally clear shareData here if you want
    }
  };

  // Build code block using inline profile
  const snippetText = shareData
    ? `import delta_sharing

# inline credentials profile
profile = ${JSON.stringify(shareData.profile, null, 2)}

table_url = "${shareData.snippet.tableUrl}"

df = delta_sharing.load_as_pandas(table_url, profile=profile)
`
    : "";

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
          {/* New: let them pull up the snippet again */}
          {shareData && !showModal && (
            <button
              onClick={() => setShowModal(true)}
              className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700 ml-2"
            >
              View Snippet
            </button>
          )}
        </>
      )}

      {showModal && shareData && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4">
          <div className="bg-gray-800 p-6 rounded max-w-lg w-full">
            <h3 className="text-xl font-semibold mb-4 text-white">
              Share Snippet
            </h3>
            <textarea
              readOnly
              className="w-full h-40 p-2 bg-gray-900 text-green-200 rounded"
              value={snippetText}
            />
            <div className="mt-4 flex justify-end space-x-2">
              <button
                onClick={() => navigator.clipboard.writeText(snippetText)}
                className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700"
              >
                Copy to clipboard
              </button>
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
