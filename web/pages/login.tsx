import { useState } from "react";
import { useRouter } from "next/router";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
} from "firebase/auth";
import { auth } from "../utils/firebase";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [error, setError] = useState("");

  const handleAuth = async () => {
    try {
      if (isRegistering) {
        await createUserWithEmailAndPassword(auth, email, password);
      } else {
        await signInWithEmailAndPassword(auth, email, password);
      }
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Unknown error occurred.");
      }
    }
  };

  return (
    <main className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center px-6">
      <h1 className="text-2xl font-bold mb-4">
        {isRegistering ? "Sign Up" : "Log In"}
      </h1>
      <input
        type="email"
        placeholder="Email - fake is fine ;)"
        className="mb-2 p-2 rounded w-72 bg-white text-black"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <input
        type="password"
        placeholder="Password"
        className="mb-4 p-2 rounded w-72 bg-white text-black"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button
        onClick={handleAuth}
        className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded mb-2"
      >
        {isRegistering ? "Create Account" : "Log In"}
      </button>
      <button
        onClick={() => setIsRegistering(!isRegistering)}
        className="text-sm text-blue-400 underline"
      >
        {isRegistering
          ? "Already have an account? Log in"
          : "Need an account? Sign up"}
      </button>
      {error && <p className="text-red-400 mt-4">{error}</p>}
    </main>
  );
}
