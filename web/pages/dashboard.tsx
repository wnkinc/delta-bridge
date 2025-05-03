import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { auth } from "@/utils/firebase";
import { onAuthStateChanged } from "firebase/auth";

export default function DashboardPage() {
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (!user) {
        router.push("/login");
      } else {
        setUserEmail(user.email);
        setLoading(false);
      }
    });
    return unsubscribe;
  }, [router]);

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <p>Loading...</p>
      </main>
    );
  }

  const mockDatasets = [
    {
      name: "Sales_Q1_2025.csv",
      status: "Converted",
      shared: true,
    },
    {
      name: "Website_Traffic_March.csv",
      status: "Uploaded",
      shared: false,
    },
  ];

  return (
    <main className="min-h-screen bg-gray-900 text-white px-6 py-10">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-extrabold">Your Datasets</h1>
        <p className="text-sm text-gray-300">Signed in as {userEmail}</p>
      </div>

      <button className="mb-6 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded transition">
        Upload New Dataset
      </button>

      <div className="grid gap-6">
        {mockDatasets.map((dataset, index) => (
          <div
            key={index}
            className="bg-gray-800 p-4 rounded shadow flex justify-between items-center"
          >
            <div>
              <h2 className="text-lg font-semibold">{dataset.name}</h2>
              <p className="text-gray-400 text-sm">
                Status: {dataset.status} •{" "}
                {dataset.shared ? "Shared" : "Not Shared"}
              </p>
            </div>
            <div className="space-x-2">
              {dataset.shared ? (
                <button className="bg-red-500 hover:bg-red-600 text-sm px-3 py-1 rounded">
                  Unshare
                </button>
              ) : (
                <button className="bg-green-600 hover:bg-green-700 text-sm px-3 py-1 rounded">
                  Share
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
