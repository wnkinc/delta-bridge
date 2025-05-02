import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gray-900 text-white px-6">
      <h1 className="text-4xl font-extrabold mb-4 text-center">
        Welcome to DeltaBridge
      </h1>
      <p className="text-gray-300 text-lg max-w-xl text-center mb-8">
        Upload your data. Share it securely. Let anyone query it with a simple
        link and a notebook.
      </p>
      <Link href="/dashboard">
        <button className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded text-lg transition">
          Go to Dashboard
        </button>
      </Link>
    </main>
  );
}
