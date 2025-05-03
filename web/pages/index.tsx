import Link from "next/link";
import { useEffect, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "@/utils/firebase";

export default function HomePage() {
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUserEmail(user ? user.email : null);
    });
    return unsubscribe;
  }, []);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gray-900 text-white px-6">
      <h1 className="text-4xl font-extrabold mb-4 text-center">
        Welcome to DeltaBridge
      </h1>
      <p className="text-gray-300 text-lg max-w-xl text-center mb-8">
        Upload your data. Share it securely. Let anyone query it with a simple
        link and a notebook.
      </p>

      {userEmail ? (
        <Link href="/dashboard">
          <button className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded text-lg transition">
            Go to Dashboard
          </button>
        </Link>
      ) : (
        <div className="flex space-x-4">
          <Link href="/login">
            <button className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded text-lg transition">
              Log In
            </button>
          </Link>
          <Link href="/login">
            <button className="bg-gray-600 hover:bg-gray-700 text-white px-6 py-2 rounded text-lg transition">
              Sign Up
            </button>
          </Link>
        </div>
      )}
    </main>
  );
}
