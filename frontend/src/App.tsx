import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./Layout";
import CheckIn from "./screens/CheckIn";
import Home from "./screens/Home";
import Login from "./screens/Login";
import Measurements from "./screens/Measurements";
import Plan from "./screens/Plan";
import Settings from "./screens/Settings";
import Shopping from "./screens/Shopping";
import Today from "./screens/Today";
import Workout from "./screens/Workout";
import WorkoutHistory from "./screens/WorkoutHistory";

// Code-split: these screens pull in Recharts (~350 KB), which the rest of the
// app doesn't need. Load them only when their route is opened (shared chunk).
const Diabetes = lazy(() => import("./screens/Diabetes"));
const ExerciseProgress = lazy(() => import("./screens/ExerciseProgress"));

export default function App() {
  const { isAuthed } = useAuth();
  if (!isAuthed) return <Login />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/today" element={<Today />} />
        <Route path="/workout" element={<Workout />} />
        <Route path="/history" element={<WorkoutHistory />} />
        <Route path="/measurements" element={<Measurements />} />
        <Route path="/check-in" element={<CheckIn />} />
        <Route path="/shopping" element={<Shopping />} />
        <Route
          path="/diabetes"
          element={
            <Suspense fallback={<p className="text-slate-400">Loading…</p>}>
              <Diabetes />
            </Suspense>
          }
        />
        <Route
          path="/exercises"
          element={
            <Suspense fallback={<p className="text-slate-400">Loading…</p>}>
              <ExerciseProgress />
            </Suspense>
          }
        />
        <Route path="/plan" element={<Plan />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
