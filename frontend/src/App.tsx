import { Header } from "./components/Header";
import { ThreatAnalyzer } from "./components/ThreatAnalyzer";
import { BrowsePanel } from "./components/BrowsePanel";

export function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex flex-col">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-5 gap-6 max-w-7xl">
        <div className="lg:col-span-3"><ThreatAnalyzer /></div>
        <div className="lg:col-span-2"><BrowsePanel /></div>
      </main>
      <footer className="text-center py-4 text-sm text-gray-500 tracking-wide border-t border-gray-800">
        Developed by <span className="text-gray-400 font-medium">Jialin</span>
      </footer>
    </div>
  );
}
