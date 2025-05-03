// web/utils/firebase.ts
import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth } from "firebase/auth";

// 🔁 Replace these with your actual Firebase config values
const firebaseConfig = {
  apiKey: "AIzaSyCdRRum2ngZzu2BWiMicueZevNjL5cQhV8",
  authDomain: "delta-bridge-c31b8.firebaseapp.com",
  projectId: "delta-bridge-c31b8",
  storageBucket: "delta-bridge-c31b8.firebasestorage.app",
  messagingSenderId: "700224417497",
  appId: "1:700224417497:web:327fcb6302da91a62158c8",
};

const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
const auth = getAuth(app);

export { auth };
