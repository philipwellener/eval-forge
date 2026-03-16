import { Routes, Route, NavLink } from "react-router-dom";
import RunsList from "./pages/RunsList";
import RunDetail from "./pages/RunDetail";
import Compare from "./pages/Compare";

function App() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Top navigation */}
      <nav className="sticky top-0 z-50 border-b border-gray-800 bg-gray-950/90 backdrop-blur-sm">
        <div className="mx-auto flex h-12 max-w-screen-2xl items-center gap-8 px-4">
          <NavLink to="/" className="flex items-center gap-2 text-sm font-bold tracking-wide">
            <span className="text-cyan-400">Eval</span>
            <span className="text-emerald-400">Forge</span>
          </NavLink>

          <div className="flex items-center gap-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-gray-800 text-cyan-400"
                    : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/50"
                }`
              }
            >
              Runs
            </NavLink>
            <NavLink
              to="/compare"
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-gray-800 text-cyan-400"
                    : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/50"
                }`
              }
            >
              Compare
            </NavLink>
          </div>
        </div>
      </nav>

      {/* Page content */}
      <main className="flex-1">
        <div className="mx-auto max-w-screen-2xl p-4">
          <Routes>
            <Route path="/" element={<RunsList />} />
            <Route path="/runs/:id" element={<RunDetail />} />
            <Route path="/compare" element={<Compare />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default App;
