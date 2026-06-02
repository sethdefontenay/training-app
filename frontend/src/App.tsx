import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./Layout";
import CheckIn from "./screens/CheckIn";
import Diabetes from "./screens/Diabetes";
import Home from "./screens/Home";
import Login from "./screens/Login";
import Measurements from "./screens/Measurements";
import Plan from "./screens/Plan";
import Shopping from "./screens/Shopping";
import Today from "./screens/Today";
import Workout from "./screens/Workout";

export default function App() {
  const { isAuthed } = useAuth();
  if (!isAuthed) return <Login />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/today" element={<Today />} />
        <Route path="/workout" element={<Workout />} />
        <Route path="/measurements" element={<Measurements />} />
        <Route path="/check-in" element={<CheckIn />} />
        <Route path="/shopping" element={<Shopping />} />
        <Route path="/diabetes" element={<Diabetes />} />
        <Route path="/plan" element={<Plan />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
