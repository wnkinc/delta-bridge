export default function DashboardPage() {
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
      <h1 className="text-3xl font-extrabold mb-6">Your Datasets</h1>

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
